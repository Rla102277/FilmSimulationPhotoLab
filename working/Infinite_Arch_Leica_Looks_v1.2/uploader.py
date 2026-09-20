#!/usr/bin/env python3
"""Infinite Arch Leica Q3/Q3 43 — Final 9-Look installer.

Default behavior is immediate install; no confirmation prompt.
Run after Leica FOTOS establishes the authenticated Q3 Wi-Fi session and is force-quit.

Per-Look Leica base:
  D866=0 -> Standard
  D866=1 -> Monochrome

The camera's downloadable Look capacity has been empirically observed at 9:
the previous live probe accepted the 9th Look and rejected the 10th.

The installer writes one Look at a time and verifies exact ID/name/type/base
through Leica op 0x9033 after each accepted 0x9035 write.
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, socket, struct, time

HOST="192.168.54.1"
PORT=15740
CONNECT_WINDOW_SECONDS=90
MAX_PACKET=16*1024*1024
MAX_DOWNLOADABLE_LOOKS=9
WIDTHS={1:1,2:1,3:2,4:2,5:4,6:4,7:8,8:8,9:16,10:16}
RESP={0x2001:"OK",0x2002:"GeneralError",0x2003:"SessionNotOpen",0x2004:"InvalidTransactionID",
      0x2005:"OperationNotSupported",0x200E:"StoreReadOnly",0x200F:"AccessDenied",
      0x2019:"DeviceBusy",0x201D:"InvalidParameter",0x201E:"SessionAlreadyOpen"}

class AbortBeforeWrite(RuntimeError): pass
def rn(x): return RESP.get(x,"UnknownResponse")

def read_exact(s,n):
    out=bytearray()
    while len(out)<n:
        c=s.recv(n-len(out))
        if not c: raise ConnectionError("camera closed the connection")
        out.extend(c)
    return bytes(out)

def send_packet(s,t,b=b""):
    s.sendall(struct.pack("<II",8+len(b),t)+b)

def read_packet(s):
    n,t=struct.unpack("<II",read_exact(s,8))
    if n<8 or n>MAX_PACKET: raise ValueError(f"invalid PTP/IP packet length {n}")
    return t,read_exact(s,n-8)

def connect():
    s=socket.create_connection((HOST,PORT),timeout=3); s.settimeout(12); return s

def cb(op,tx,params,phase=1):
    return struct.pack("<IHI",phase,op,tx)+b"".join(struct.pack("<I",x) for x in params)

def read_response(s,tx):
    while True:
        t,b=read_packet(s)
        if t==7 and len(b)>=6:
            code,rtx=struct.unpack_from("<HI",b)
            if rtx==tx: return code

def read_data(s,op,tx,params,label):
    send_packet(s,6,cb(op,tx,params)); out=bytearray(); expected=None
    while True:
        t,b=read_packet(s)
        if t==9 and len(b)>=12:
            rtx,decl=struct.unpack_from("<IQ",b)
            if rtx==tx: expected=decl
        elif t in (10,12) and len(b)>=4:
            rtx=struct.unpack_from("<I",b)[0]
            if rtx==tx: out.extend(b[4:])
        elif t==7 and len(b)>=6:
            code,rtx=struct.unpack_from("<HI",b)
            if rtx!=tx: continue
            if expected is not None and expected!=len(out):
                raise RuntimeError(f"{label}: declared {expected}, got {len(out)}")
            print(f"{label}: 0x{code:04X} {rn(code)} bytes={len(out)}")
            return code,bytes(out)

def parse_fields(data):
    if len(data)<4: raise ValueError("short Look table")
    count=struct.unpack_from("<I",data)[0]; off=4; fields=[]
    for _ in range(count):
        if off+8>len(data): raise ValueError("truncated field header")
        marker,prop,dtype=struct.unpack_from("<IHH",data,off); off+=8
        if dtype in WIDTHS:
            w=WIDTHS[dtype]; raw=data[off:off+w]
            if len(raw)!=w: raise ValueError("truncated scalar")
            off+=w; val=int.from_bytes(raw,"little") if w<=8 else raw.hex()
        elif dtype==0xFFFF:
            if off>=len(data): raise ValueError("truncated string")
            n=data[off]; off+=1; raw=data[off:off+n*2]
            if len(raw)!=n*2: raise ValueError("truncated string body")
            off+=n*2; val=raw[:-2].decode("utf-16le") if n else ""
        elif dtype==0x4002:
            if off+4>len(data): raise ValueError("truncated byte array")
            n=struct.unpack_from("<I",data,off)[0]; off+=4+n; val=f"<{n} bytes>"
        elif dtype&0x4000:
            if off+4>len(data): raise ValueError("truncated array")
            n=struct.unpack_from("<I",data,off)[0]; off+=4
            w=WIDTHS[dtype&0x0FFF]; off+=n*w; val=f"<{n} elements>"
        else:
            raise ValueError(f"unknown field type 0x{dtype:04X}")
        if off>len(data): raise ValueError("truncated field")
        fields.append((marker,prop,val))
    return fields

def decode(data):
    keys={0xD861:"id",0xD862:"slot",0xDC44:"name",0xD864:"type",0xD866:"base"}
    rec=[]; cur={}
    for m,p,v in parse_fields(data):
        if p==0xD861 and cur:
            rec.append(cur); cur={}
        if p in keys: cur[keys[p]]=v
        cur["marker"]=m
    if cur: rec.append(cur)
    return rec

def next_marker(table):
    ms=[m for m,_,_ in parse_fields(table)]
    if not ms: raise RuntimeError("no Leica Look markers")
    return max(ms)+1

def fp(m,p,d): return struct.pack("<IHH",m,p,d)
def u32(m,p,v): return fp(m,p,6)+struct.pack("<I",v)
def st(m,p,v):
    raw=v.encode("utf-16le"); n=len(raw)//2+1
    return fp(m,p,0xFFFF)+bytes([n])+raw+b"\0\0"
def ba(m,p,v): return fp(m,p,0x4002)+struct.pack("<I",len(v))+v

def payload(L,cube,icon,m):
    return b"".join((struct.pack("<I",6),u32(m,0xD861,L["id"]),st(m,0xDC44,L["name"]),
                     ba(m,0xDC86,icon),ba(m,0xD860,cube),u32(m,0xD864,2),u32(m,0xD866,L["base"])))

def upload_once(s,tx,p,name):
    print(f"WRITE START {name}: tx={tx} bytes={len(p)}")
    send_packet(s,6,cb(0x9035,tx,[],2)); send_packet(s,9,struct.pack("<IQ",tx,len(p)))
    off=0
    while len(p)-off>12288:
        c=p[off:off+12288]; send_packet(s,10,struct.pack("<I",tx)+c); off+=len(c)
    send_packet(s,12,struct.pack("<I",tx)+p[off:])
    code=read_response(s,tx)
    print(f"WRITE RESULT {name}: 0x{code:04X} {rn(code)}")
    return code

def cube_rows(text):
    rows=[]
    for line in text.splitlines():
        p=line.split()
        if len(p)==3:
            try: rows.append(tuple(float(x) for x in p))
            except ValueError: pass
    return rows

def validate(root,manifest):
    ids=set(); names=set(); icons=set(); out=[]
    for L in manifest:
        if not L.get("enabled",True): continue
        if L["id"] in ids or L["name"] in names: raise SystemExit("duplicate ID/name in pack")
        ids.add(L["id"]); names.add(L["name"])
        cube=(root/L["cube"]).read_bytes(); icon=(root/L["icon"]).read_bytes()
        if len(cube)!=L["cube_bytes"] or hashlib.sha256(cube).hexdigest()!=L["cube_sha256"]:
            raise SystemExit(f"{L['name']}: CUBE integrity failure")
        ih=hashlib.sha256(icon).hexdigest()
        if len(icon)!=2224 or ih!=L["icon_sha256"] or ih in icons:
            raise SystemExit(f"{L['name']}: icon integrity/uniqueness failure")
        icons.add(ih)
        if icon[:2]!=b"BM": raise SystemExit(f"{L['name']}: icon format failure")
        w,h=struct.unpack_from("<ii",icon,18); bits=struct.unpack_from("<H",icon,28)[0]
        if (w,h,bits)!=(180,90,1): raise SystemExit(f"{L['name']}: icon geometry failure")
        mode="Monochrome" if L["base"]==1 else "Standard"
        text=cube.decode("ascii")
        req=[f"#Unique Leica Look ID: {L['id']}",f"#Based Filmstyle Mode: {mode}",
             f'TITLE "{L["name"]}"',"LUT_3D_SIZE 17","DOMAIN_MIN 0.0 0.0 0.0","DOMAIN_MAX 1.0 1.0 1.0"]
        if any(x not in text for x in req): raise SystemExit(f"{L['name']}: metadata failure")
        rows=cube_rows(text)
        if len(rows)!=4913: raise SystemExit(f"{L['name']}: expected 4913 rows")
        mono=all(abs(r-g)<1e-9 and abs(g-b)<1e-9 for r,g,b in rows)
        if mono!=bool(L["mono"]): raise SystemExit(f"{L['name']}: mono flag mismatch")
        print(f"PASS ID={L['id']} {mode:<10} {L['name']} {'BW' if mono else 'COLOR'}")
        out.append((L,cube,icon))
    if len(out)!=MAX_DOWNLOADABLE_LOOKS:
        raise SystemExit(f"expected {MAX_DOWNLOADABLE_LOOKS} Looks, got {len(out)}")
    return out

def open_fotos():
    cmd=connect(); evt=None
    try:
        init=bytes(16)+"OLS".encode("utf-16le")+struct.pack("<HH",0,1)
        send_packet(cmd,1,init); t,b=read_packet(cmd)
        if t!=2 or len(b)<4: raise RuntimeError("no InitCommandAck")
        conn=struct.unpack_from("<I",b)[0]
        evt=connect(); send_packet(evt,3,struct.pack("<I",conn)); t,_=read_packet(evt)
        if t!=4: raise RuntimeError("no InitEventAck")
        send_packet(cmd,6,cb(0x1002,0,[0x412]))
        code=read_response(cmd,0); print(f"OpenSession: 0x{code:04X} {rn(code)}")
        if code!=0x201E: raise AbortBeforeWrite("surviving authenticated FOTOS session not present")
        return cmd,evt
    except:
        cmd.close()
        if evt: evt.close()
        raise

def pre_read(cmd):
    for base in (0x10000,0x20000,0x7F000000):
        try:
            code,di=read_data(cmd,0x1001,base,[],"DeviceInfo")
            if code!=0x2001 or len(di)<100: raise RuntimeError("DeviceInfo failed")
            code,tab=read_data(cmd,0x9033,base+1,[0xFFFF,0xFFFFFFFF],"Look table")
            if code!=0x2001 or not tab: raise RuntimeError("Look table failed")
            return base,tab
        except RuntimeError as e:
            print("pre-read base failed:",e)
    raise AbortBeforeWrite("no transaction base passed")

def downloadable_count(records):
    return sum(1 for r in records if r.get("type")==2)

def verify(cmd,tx,L):
    for attempt in range(1,5):
        if attempt>1: time.sleep(0.45)
        code,tab=read_data(cmd,0x9033,tx,[0xFFFF,0xFFFFFFFF],f"verify {L['name']} {attempt}/4"); tx+=1
        if code==0x2019: continue
        if code!=0x2001: return False,tab,tx
        rec=decode(tab)
        ok=any(r.get("id")==L["id"] and r.get("name")==L["name"] and r.get("type")==2 and r.get("base")==L["base"] for r in rec)
        return ok,tab,tx
    return False,b"",tx

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--list",action="store_true",help="validate only; no camera connection/write")
    args=ap.parse_args()
    root=pathlib.Path(__file__).resolve().parent
    manifest=json.loads((root/"looks_manifest.json").read_text())
    assets=validate(root,manifest)
    if args.list:
        print("VALIDATION ONLY — no camera connection or write."); return

    print("AUTO-INSTALL: 9-Look final Infinite Arch set.")
    print("If different downloadable Looks already occupy the camera's nine slots, remove them in FOTOS first.")
    deadline=time.monotonic()+CONNECT_WINDOW_SECONDS; last=None
    while time.monotonic()<deadline:
        cmd=evt=None
        try:
            cmd,evt=open_fotos()
            base,tab=pre_read(cmd); tx=base+2
            rec=decode(tab)
            print(f"CURRENT DOWNLOADABLE COUNT: {downloadable_count(rec)}")
            byname={L["name"]:(L,c,i) for L,c,i in assets}
            installed=[]
            for L in manifest:
                if any(r.get("id")==L["id"] and r.get("name")==L["name"] and r.get("type")==2 and r.get("base")==L["base"] for r in rec):
                    installed.append(L["name"])
            foreign=[r for r in rec if r.get("type")==2 and r.get("name") not in installed]
            if foreign:
                print("SAFE STOP: non-matching downloadable Looks are already installed:")
                for r in foreign:
                    print(f"  slot={r.get('slot')} id={r.get('id')} base={r.get('base')} name={r.get('name')}")
                print("Remove downloaded Looks in FOTOS, reconnect, force-quit FOTOS, then rerun.")
                return
            missing=[L for L in manifest if L["name"] not in installed]
            if not missing:
                print("SUCCESS: all 9 final IA Looks are installed."); return
            if downloadable_count(rec)+len(missing)>MAX_DOWNLOADABLE_LOOKS:
                raise AbortBeforeWrite("not enough downloadable slots for the final nine")

            current=tab
            for L in missing:
                L,cube,icon=byname[L["name"]]
                marker=next_marker(current)
                p=payload(L,cube,icon,marker)
                try:
                    code=upload_once(cmd,tx,p,L["name"]); tx+=1
                except Exception as e:
                    print("AMBIGUOUS WRITE STATE — inspect camera before rerun.")
                    print(repr(e)); return
                if code!=0x2001:
                    print(f"STOP: {L['name']} rejected with 0x{code:04X} {rn(code)}"); return
                ok,current,tx=verify(cmd,tx,L)
                if not ok:
                    print(f"STOP: {L['name']} was accepted but exact ID/name/base did not verify."); return
                print(f"VERIFIED {L['name']} — downloadable count: {downloadable_count(decode(current))}")

            print("SUCCESS: all 9 final IA Looks installed and verified.")
            return

        except AbortBeforeWrite as e:
            print("SAFE STOP:",e); return
        except (OSError,ConnectionError,RuntimeError,ValueError) as e:
            msg=repr(e)
            if msg!=last: print("waiting before any write:",msg); last=msg
            time.sleep(.55)
        finally:
            if cmd:
                try: cmd.close()
                except: pass
            if evt:
                try: evt.close()
                except: pass

    print("TIMEOUT BEFORE WRITE: no upload was attempted.")

if __name__=="__main__":
    main()
