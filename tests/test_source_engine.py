import io,json,zipfile
from pathlib import Path
import numpy as np
import pytest
from core.assets.inspect import inspect_source_asset
from core.color.cube import CubeLUT,parse_cube,sample_cube,serialize_leica_cube,parse_hald
from core.color.graph_compiler import evaluate_graph,compile_graph_cube
from core.color.source_transforms import table_data,sample_table,preset_transform,parse_preset,dcp_transform
from core.leica.authoritative import read_look_asset,load_authoritative_manifest


def graph(*nodes,**kwargs):return dict(nodes=[{'id':'input','type':'input'},*nodes,{'id':'output','type':'output'}],**kwargs)
def identity(size):return np.array([(r,g,b) for b in np.linspace(0,1,size) for g in np.linspace(0,1,size) for r in np.linspace(0,1,size)])


def test_nine_reference_looks_preserved_through_graph():
    for look in load_authoritative_manifest():
        data=read_look_asset(look['id'],'cube');cube=parse_cube(data)
        result,report=evaluate_graph(graph({'id':'film','type':'cube_lut','cube':data}))
        np.testing.assert_allclose(result.values,cube.values,atol=2e-7)
        assert report['ready']


def test_large_cube_indexing_and_domain_baking():
    values=identity(65);lut=CubeLUT('large',65,(0,0,0),(2,2,2),values)
    pts=np.array([[1,1,1],[.4,1.6,1.8],[2,0,2]])
    np.testing.assert_allclose(sample_cube(pts,lut),pts/2,atol=1e-8)
    baked=parse_cube(serialize_leica_cube(lut,1001,'Domain',0))
    np.testing.assert_allclose(sample_cube(pts/2,baked),pts/4,atol=1e-6)


def test_nonfinite_and_bad_domain_rejected():
    for header in ['DOMAIN_MIN 1 0 0\nDOMAIN_MAX 0 1 1\n','DOMAIN_MIN nan 0 0\n']:
        with pytest.raises(ValueError):parse_cube((header+'LUT_3D_SIZE 2\n'+'0 0 0\n'*8).encode())
    with pytest.raises(ValueError):parse_cube(('LUT_3D_SIZE 2\n'+'nan 0 0\n'*8).encode())


def test_dcp_storage_axes_encoding_and_wrap():
    t=np.zeros((2,4,3,3));t[...,1:]=1
    for v in range(2):
        for h in range(4):
            for s in range(3):t[v,h,s,0]=100*v+10*h+s
    tags={'ProfileHueSatMapDims':[4,3,2],'ProfileHueSatMapData1':t.ravel().tolist(),'ProfileHueSatMapEncoding':1}
    out,enc=table_data(tags)
    np.testing.assert_array_equal(out,t)
    samples=sample_table(np.array([[.5,1,1],[0,0,0],[.875,0,0]]),out,enc)
    np.testing.assert_allclose(samples[:,0],[122,0,15])


def test_real_dcp_profiles_not_identical_and_no_sensor_matrix():
    z=zipfile.ZipFile(Path(__file__).resolve().parents[1]/'attached_assets/0_ALL_DCP_CUBE_LIBRARY_1789502493370.zip');results=[]
    for stock in ['Fuji 400H L','Ultra 100 - L','Fuji Superia 1600 L']:
        name=next(n for n in z.namelist() if n.endswith(stock+'.dcp') and 'M9' in n)
        src=inspect_source_asset(name,z.read(name));component=src['components'][0]
        assert component['type']=='dcp_creative'
        assert all(not c['blendable'] for c in src['components'] if c['type']=='matrix')
        out=dcp_transform(identity(17),component);assert np.isfinite(out).all();results.append(out)
        relative={**component,'mode':'relative_display','baseline_tags':component['tags']}
        np.testing.assert_allclose(dcp_transform(identity(17),relative),identity(17),atol=1e-10)
    assert np.max(np.abs(results[0]-results[1]))>.01


def test_camera_matrices_and_unknown_nodes_cannot_silently_export():
    with pytest.raises(ValueError):compile_graph_cube(graph({'id':'camera','type':'matrix','matrix':np.eye(3).tolist(),'camera_dependent':True}))
    with pytest.raises(ValueError):compile_graph_cube(graph({'id':'grain','type':'grain'}))
    _,report=compile_graph_cube(graph({'id':'grain','type':'grain','enabled':False}))
    assert report['ready']


def test_mixture_is_not_sequential():
    inv=CubeLUT('inv',2,(0,0,0),(1,1,1),1-identity(2));data=serialize_leica_cube(inv,1001,'inv',0)
    result,_=evaluate_graph(graph({'id':'mix','type':'blend','branches':[{'weight':.7,'nodes':[]},{'weight':.3,'nodes':[{'type':'cube_lut','cube':data}]}]}))
    np.testing.assert_allclose(result.values,.7*identity(17)+.3*(1-identity(17)),atol=1e-7)


def test_preset_real_values_and_xmp_curves():
    xmp=b'<x xmlns:c="http://ns.adobe.com/camera-raw-settings/1.0/" xmlns:r="rdf"><d c:CameraProfile="Fuji 400H L" c:SaturationAdjustmentOrange="-40"><c:ToneCurvePV2012><r:Seq><r:li>0, 0</r:li><r:li>255, 255</r:li></r:Seq></c:ToneCurvePV2012></d></x>'
    settings=parse_preset(xmp,'xmp');assert settings['CameraProfile']=='Fuji 400H L';assert settings['ToneCurvePV2012']==[[0,0],[255,255]]
    color=np.array([[.8,.4,.1]]);out=preset_transform(color,settings)
    assert np.ptp(out)<np.ptp(color)


def test_hald_16bit_precision():
    import tifffile
    values=(identity(4)*65535).astype(np.uint16).reshape(8,8,3);values[1,1,0]=12345
    f=io.BytesIO();tifffile.imwrite(f,values,photometric='rgb')
    cube=parse_hald(f.getvalue());assert abs(cube.values[9,0]-12345/65535)<1e-8


def test_monochrome_preview_matches_export():
    g=graph({'id':'color','type':'temperature','params':{'value':.15}},base=1)
    cube,_=evaluate_graph(g);export=parse_cube(serialize_leica_cube(cube,1001,'mono',1))
    np.testing.assert_allclose(cube.values,export.values,atol=1e-6)
    np.testing.assert_allclose(cube.values[:,0],cube.values[:,2])


def test_grade_continuity_and_neutral_identity():
    from core.color.graph_compiler import _node_transform
    for center in [.35,.45,.65,.75]:
        p=np.repeat(np.array([[center-1e-5],[center+1e-5]]),3,axis=1)
        out,_,_=_node_transform(p,{'type':'shadow_grade','params':{'hue':205,'amount':.1}})
        assert np.max(abs(out[1]-out[0]))<.0001
    cube,_=evaluate_graph(graph());np.testing.assert_allclose(cube.values,identity(17))


def test_source_routes_preview_package_and_mixture(tmp_path,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from server.api import studio
    from server.auth import require_user
    from core.assets.library import SourceLibrary
    from core.color.cube import apply_cube_to_image
    from PIL import Image
    monkeypatch.setattr(studio,'library',SourceLibrary(tmp_path/'sources.sqlite'))
    app=FastAPI();app.include_router(studio.router,prefix='/api');app.dependency_overrides[require_user]=lambda:'local-validation'
    client=TestClient(app)
    z=zipfile.ZipFile(Path(__file__).resolve().parents[1]/'attached_assets/0_ALL_DCP_CUBE_LIBRARY_1789502493370.zip');name=next(n for n in z.namelist() if n.endswith('Fuji 400H L.dcp') and 'M9' in n)
    r=client.post('/api/studio/sources/bulk',files={'files':('400H.dcp',z.read(name),'application/octet-stream')});assert r.status_code==201,r.text
    source=studio.library.list()[0]
    ui={'name':'Engine integration','look_id':1007,'base':'Standard','controls':{},'layers':[{'id':'dcp','name':'400H','type':'dcp_creative','source_id':source['id'],'component_id':'CreativeInterpretation','strength':100},{'id':'out','type':'output','strength':100}]}
    exported=client.post('/api/studio/graph/cube',json=ui);assert exported.status_code==200,exported.text
    photo=io.BytesIO();Image.new('RGB',(16,16),(145,98,64)).save(photo,format='PNG')
    preview=client.post('/api/studio/graph/preview',data={'graph':json.dumps(ui)},files={'image':('photo.png',photo.getvalue(),'image/png')})
    assert preview.status_code==200,preview.text
    assert preview.content==apply_cube_to_image(photo.getvalue(),parse_cube(exported.content))
    package=client.post('/api/studio/graph/package',json=ui);assert package.status_code==200,package.text
    with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
        assert 'recipe.json' in archive.namelist()
        file=next(n for n in archive.namelist() if n.endswith('.CUBE'))
        np.testing.assert_allclose(parse_cube(archive.read(file)).values,parse_cube(exported.content).values,atol=1e-6)
    bad=json.loads(json.dumps(ui));bad['layers'][0].update(component_id='ColorMatrix1',type='matrix')
    assert client.post('/api/studio/graph/cube',json=bad).status_code==422
    hald=io.BytesIO();Image.fromarray((identity(4).reshape(8,8,3)*255).astype('uint8')).save(hald,format='PNG')
    r=client.post('/api/studio/sources/bulk',data={'interpretation':'hald'},files={'files':('identity.png',hald.getvalue(),'image/png')});assert r.status_code==201,r.text
    source=next(x for x in studio.library.list() if x['asset_type']=='hald')
    ui['layers'][0].update(type='cube_lut',source_id=source['id'],component_id='hald_lut')
    r=client.post('/api/studio/graph/cube',json=ui);assert r.status_code==200,r.text
    np.testing.assert_allclose(parse_cube(r.content).values,identity(17),atol=1e-6)


def test_assistant_schema_rejects_code_and_keeps_original():
    from server.api.creative_assistant import apply_edits
    g={'layers':[{'type':'output'}]};original=json.dumps(g)
    out=apply_edits(g,[{'type':'selective_color','params':{'hue':25,'saturation':-.2}}])
    assert json.dumps(g)==original and len(out['layers'])==2
    for edit in [{'type':'exec','params':{}},{'type':'selective_color','params':{'saturation':float('nan')}},{'type':'matrix','params':{'code':'x'}}]:
        with pytest.raises(ValueError):apply_edits(g,[edit])


def test_assistant_http_proposal_is_reviewable_and_compiled(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from server.api import creative_assistant as ca
    from server.auth import require_user
    monkeypatch.setenv('ANTHROPIC_API_KEY','local-fixture-key');monkeypatch.setenv('CREATIVE_ASSISTANT_MODEL','configured-model')
    class FakeResponse:
        def raise_for_status(self):pass
        def json(self):return {'content':[{'text':json.dumps({'summary':'Cooler shadows','edits':[{'type':'shadow_grade','params':{'hue':205,'amount':.08}}]})}]}
    class FakeClient:
        def __init__(self,*a,**k):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*a):pass
        async def post(self,url,**kwargs):
            assert kwargs['json']['model']=='configured-model'
            assert kwargs['json']['messages'][0]['content'][-1]['type']=='text'
            return FakeResponse()
    monkeypatch.setattr(ca.httpx,'AsyncClient',FakeClient)
    app=FastAPI();app.include_router(ca.router,prefix='/api');app.dependency_overrides[require_user]=lambda:'local-validation'
    graph={'name':'Proposal','base':'Standard','layers':[{'id':'out','type':'output','strength':100}],'controls':{}}
    response=TestClient(app).post('/api/studio/assistant/propose',json={'graph':graph,'instruction':'Cool the shadows'})
    assert response.status_code==200,response.text
    result=response.json();assert result['report']['ready'] and not result['applied'];assert len(result['graph']['layers'])==2
    assert len(graph['layers'])==1
