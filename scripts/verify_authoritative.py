#!/usr/bin/env python3
from pathlib import Path
import hashlib, zipfile, json, sys

ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'reference/leica/v1.2/Infinite_Arch_Leica_Looks_v1.2.zip'
EXPECTED='1932cb619aeabe3b63bf616f77ffeac94181fa92af2a189f865068aac8f1e83f'
if not P.exists():
    print('FAIL: authoritative archive missing:', P); sys.exit(2)
h=hashlib.sha256(P.read_bytes()).hexdigest()
print('Archive:', P)
print('Expected SHA-256:', EXPECTED)
print('Actual   SHA-256:', h)
if h != EXPECTED:
    print('FAIL: authoritative archive checksum mismatch'); sys.exit(3)
with zipfile.ZipFile(P) as z:
    m=json.loads(z.read('Infinite_Arch_Leica_Looks_v1.2/looks_manifest.json'))
print('PASS: archive checksum verified')
print('Looks:')
for x in m:
    print(f"  {x['id']}  {x['name']}  base={x['base_name']}  cube={x['cube_sha256'][:12]}…")
if [x['id'] for x in m] != list(range(1001,1010)):
    print('FAIL: expected IDs 1001-1009'); sys.exit(4)
print('PASS: authoritative manifest IDs verified')
