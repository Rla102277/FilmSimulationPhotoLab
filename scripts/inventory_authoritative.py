#!/usr/bin/env python3
from pathlib import Path
import zipfile, hashlib
ROOT=Path(__file__).resolve().parents[1]
P=ROOT/'reference/leica/v1.2/Infinite_Arch_Leica_Looks_v1.2.zip'
OUT=ROOT/'docs/leica-v1.2-inventory-generated.md'
with zipfile.ZipFile(P) as z:
    lines=['# Generated Leica v1.2 Inventory','','| Member | Bytes | SHA-256 |','|---|---:|---|']
    for info in z.infolist():
        if info.is_dir():
            continue
        data=z.read(info.filename)
        lines.append(f"| `{info.filename}` | {len(data)} | `{hashlib.sha256(data).hexdigest()}` |")
OUT.write_text("\n".join(lines)+"\n", encoding="utf-8")
print(OUT)
