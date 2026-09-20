"""Source-aware artistic transforms. Not an Adobe raw-development implementation.

DCP table storage: V outer, H middle, S inner, three deltas per cell (Adobe DNG).
Display adaptations are deliberately labelled; sensor matrices never enter this path.
"""
import colorsys
import re
import xml.etree.ElementTree as ET
import numpy as np


def hsv(rgb):
    shape=rgb.shape
    return np.asarray([colorsys.rgb_to_hsv(*p) for p in np.clip(rgb,0,1).reshape(-1,3)]).reshape(shape)


def rgb(hsv_values):
    shape=hsv_values.shape
    return np.asarray([colorsys.hsv_to_rgb(p[0]%1,p[1],p[2]) for p in hsv_values.reshape(-1,3)]).reshape(shape)


def compress(values):
    y=np.clip(np.sum(values*np.array([.2126,.7152,.0722]),axis=-1,keepdims=True),0,1)
    c=values-y
    limits=np.where(c>0,(1-y)/np.maximum(c,1e-12),np.where(c<0,-y/np.minimum(c,-1e-12),1))
    return np.clip(y+c*np.minimum(1,limits.min(axis=-1,keepdims=True)),0,1)


def table_data(tags,look=False,illuminant=.5):
    key='ProfileLookTable' if look else 'ProfileHueSatMap'
    dims=tags.get(key+'Dims')
    if not isinstance(dims,list) or len(dims)!=3:raise ValueError(f'{key} dimensions are missing')
    h,s,v=map(int,dims)
    if h<1 or s<2 or v<1 or h*s*v>2000000:raise ValueError('Invalid DCP table dimensions')
    def get(name):
        a=np.asarray(tags.get(name,[]),dtype=float)
        if a.size!=h*s*v*3 or not np.isfinite(a).all():raise ValueError(f'Malformed {name}')
        a=a.reshape(v,h,s,3)
        if np.any(a[...,1:]<0):raise ValueError('Negative DCP saturation/value multiplier')
        return a
    t=get(key+'Data' if look else key+'Data1')
    if not look and key+'Data2' in tags:
        if not 0<=illuminant<=1:raise ValueError('Illuminant mix must be in 0..1')
        t=t*(1-illuminant)+get(key+'Data2')*illuminant
    encoding=int(tags.get(key+'Encoding',0))
    if encoding not in (0,1):raise ValueError('Unsupported DCP value encoding')
    return t,encoding


def sample_table(hsv_values,table,encoding):
    vcount,hcount,scount,_=table.shape
    h=hsv_values[...,0]%1;s=np.clip(hsv_values[...,1],0,1);v=np.clip(hsv_values[...,2],0,1)
    # The display adaptation treats input display V as the selected indexing domain.
    # Encoding 0 samples linear-light V; encoding 1 samples sRGB V.
    vi=np.where(v<=.04045,v/12.92,((v+.055)/1.055)**2.4) if encoding==0 else v
    q=np.stack([h*hcount,s*(scount-1),vi*(vcount-1)],axis=-1)
    lo=np.floor(q).astype(int);f=q-lo
    hi=lo+1;lo[...,0]%=hcount;hi[...,0]%=hcount
    for k,n in [(1,scount),(2,vcount)]:lo[...,k]=np.minimum(lo[...,k],n-1);hi[...,k]=np.minimum(hi[...,k],n-1)
    out=np.zeros_like(hsv_values,dtype=float)
    for vb in (0,1):
        for hb in (0,1):
            for sb in (0,1):
                bits=np.array([hb,sb,vb]);ix=np.where(bits,hi,lo);w=np.prod(np.where(bits,f,1-f),axis=-1)
                out+=table[ix[...,2],ix[...,0],ix[...,1]]*w[...,None]
    return out


def dcp_transform(values,node):
    tags=node['tags'];mode=node.get('mode','bounded_display');mix=float(node.get('illuminant_mix',.5));out=values.copy()
    if mode not in ('bounded_display','relative_display'):raise ValueError('DCP requires bounded_display or relative_display mode')
    baseline=node.get('baseline_tags')
    if mode=='relative_display' and not baseline:raise ValueError('Relative DCP interpretation requires a baseline profile')
    if baseline:
        for key in ('ColorMatrix1','ColorMatrix2'):
            if key in tags and key in baseline:
                x=np.asarray(tags[key]);y=np.asarray(baseline[key])
                if x.shape!=y.shape or not np.allclose(x,y,atol=1e-4):raise ValueError('Choose a baseline with matching camera calibration')
    found=False
    for look in (False,True):
        key='ProfileLookTableData' if look else 'ProfileHueSatMapData1'
        if key not in tags:continue
        found=True;t,encoding=table_data(tags,look,mix)
        # Smooth hue differences to avoid undersampling in a 17-grid LUT.
        t=sum(np.roll(t,k,axis=1)*w for k,w in [(-2,.1),(-1,.2),(0,.4),(1,.2),(2,.1)])
        hh=hsv(out);delta=sample_table(hh,t,encoding)
        if baseline:
            if key not in baseline:raise ValueError('Baseline must contain the same DCP table family')
            bt,be=table_data(baseline,look,mix);bt=sum(np.roll(bt,k,axis=1)*w for k,w in [(-2,.1),(-1,.2),(0,.4),(1,.2),(2,.1)])
            bd=sample_table(hh,bt,be);delta[...,0]=(delta[...,0]-bd[...,0]+180)%360-180;delta[...,1:]/=np.maximum(bd[...,1:],1e-6)
        # Explicit artistic bounds, not a claim to isolate camera calibration.
        hh[...,0]+=np.clip(delta[...,0],-8,8)*.65/360
        hh[...,1]*=1+.65*(np.clip(delta[...,1],.8,1.2)-1)
        hh[...,2]*=1+.45*(np.clip(delta[...,2],.8,1.2)-1)
        out=compress(rgb(hh))
    if not found:raise ValueError('DCP has no supported color tables; calibration-only profiles cannot define a creative Look')
    return out


def parse_preset(content,kind):
    text=content.decode('utf-8-sig');settings={}
    if kind=='lrtemplate':
        for key,value in re.findall(r'\b(\w+)\s*=\s*([^,\n{}]+)',text):
            value=value.strip().strip('"')
            try:settings[key]=float(value)
            except ValueError:settings[key]=value
        for key,body in re.findall(r'(ToneCurve\w*)\s*=\s*\{([^{}]+)\}',text):
            values=[float(n) for n in re.findall(r'-?\d+(?:\.\d+)?',body)]
            if len(values)%2==0:settings[key]=np.asarray(values).reshape(-1,2).tolist()
    else:
        root=ET.fromstring(text)
        for el in root.iter():
            for key,value in el.attrib.items():
                key=key.split('}')[-1]
                try:settings[key]=float(value)
                except ValueError:settings[key]=value
            key=el.tag.split('}')[-1]
            if key.startswith('ToneCurve'):
                points=[]
                for li in el.iter():
                    if li.tag.split('}')[-1]=='li' and li.text:
                        pair=re.findall(r'-?\d+(?:\.\d+)?',li.text)
                        if len(pair)==2:points.append([float(x) for x in pair])
                if points:settings[key]=points
    return settings


SECTORS={'Red':0,'Orange':.0833,'Yellow':.1667,'Green':.3333,'Aqua':.5,'Blue':.6667,'Purple':.7778,'Magenta':.9167}

def preset_transform(values,settings,curves=False):
    """Selected display HSL/curve interpretation, not Lightroom process emulation."""
    out=values.copy();hh=hsv(out);h,s,v=np.moveaxis(hh,-1,0)
    total=np.zeros_like(h);dh=total.copy();ds=total.copy();dv=total.copy()
    for name,c in SECTORS.items():
        weight=np.exp(-.5*(((h-c+.5)%1-.5)/.07)**2);total+=weight
        dh+=weight*float(settings.get('HueAdjustment'+name,0))*.32/360
        ds+=weight*float(settings.get('SaturationAdjustment'+name,0))*.4/100
        dv+=weight*float(settings.get('LuminanceAdjustment'+name,0))*.18/100
    hh[...,0]+=dh/total*s;hh[...,1]*=(1+ds/total)*(1+float(settings.get('Saturation',0))*.4/100);hh[...,2]+=dv/total*s*(1-v)
    out=compress(rgb(hh))
    if curves:
        for name,channels in [('ToneCurvePV2012',range(3)),('ToneCurvePV2012Red',[0]),('ToneCurvePV2012Green',[1]),('ToneCurvePV2012Blue',[2])]:
            if name in settings:
                pts=np.asarray(settings[name],float)/255
                if pts.ndim!=2 or pts.shape[1]!=2 or len(pts)<2 or not np.isfinite(pts).all() or np.any(np.diff(pts[:,0])<=0):raise ValueError('Malformed preset curve')
                for k in channels:out[...,k]=np.interp(out[...,k],pts[:,0],pts[:,1])
    return compress(out)


def selective(values,params):
    hh=hsv(values);center=float(params.get('hue',0))/360;width=max(.02,float(params.get('width',35))/360)
    mask=np.exp(-.5*(((hh[...,0]-center+.5)%1-.5)/width)**2)
    hh[...,0]+=mask*float(params.get('shift',0))/360*hh[...,1]
    hh[...,1]*=1+mask*float(params.get('saturation',0))
    hh[...,2]+=mask*float(params.get('luminance',0))*hh[...,1]*(1-hh[...,2])
    return compress(rgb(hh))
