#!/usr/bin/env python3
"""Read-only inventory tool for Leica Q3-family .lfu update packages.

This does not modify firmware or a camera. It reverses the package-wide byte
inversion used by the Q3/Q3 43 v4.1.1 files, lists the component table, and
compares stored SHA-256 values with package regions. A mismatch can mean that
Leica hashes a later decrypted/decompressed representation, not corruption.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import struct
import sys


TABLE_OFFSET = 0x2E0
RECORD_SIZE = 0x5C
MAX_RECORDS = 256


def decode_package(raw: bytes) -> bytes:
    if raw.startswith(b"UPD\0"):
        return raw
    decoded = bytes(value ^ 0xFF for value in raw)
    if decoded.startswith(b"UPD\0"):
        return decoded
    raise ValueError("not a recognized Q3-family UPD/LFU package")


def parse_records(decoded: bytes) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for index in range(MAX_RECORDS):
        start = TABLE_OFFSET + index * RECORD_SIZE
        record = decoded[start : start + RECORD_SIZE]
        if len(record) != RECORD_SIZE:
            break

        name_bytes = record[0x0C:0x18].split(b"\0", 1)[0]
        if not name_bytes:
            break
        try:
            name = name_bytes.decode("ascii")
        except UnicodeDecodeError:
            break
        if not all(character.isalnum() or character == "_" for character in name):
            break

        file_offset, size, target_offset, flags = struct.unpack_from("<IIII", record, 0x18)
        expected_digest = record[0x28:0x48]
        payload = decoded[file_offset : file_offset + size]
        actual_digest = hashlib.sha256(payload).digest()
        records.append(
            {
                "index": index,
                "name": name,
                "file_offset": file_offset,
                "size": size,
                "target_offset": target_offset,
                "flags": flags,
                "sha256": expected_digest.hex(),
                "package_region_digest_matches": len(payload) == size and actual_digest == expected_digest,
                "all_zero": bool(size) and not any(payload),
            }
        )
    return records


def inspect(path: pathlib.Path) -> dict[str, object]:
    raw = path.read_bytes()
    decoded = decode_package(raw)
    model_code = decoded[0x0C:0x1C].split(b"\0", 1)[0].decode("ascii", "replace")
    version_bytes = decoded[0x1C:0x20].hex()
    return {
        "file": str(path.resolve()),
        "file_size": len(raw),
        "lfu_sha256": hashlib.sha256(raw).hexdigest(),
        "model_code": model_code,
        "raw_version_bytes": version_bytes,
        "components": parse_records(decoded),
    }


def print_table(result: dict[str, object]) -> None:
    print(f"File: {result['file']}")
    print(f"LFU SHA-256: {result['lfu_sha256']}")
    print(f"Model code: {result['model_code']}")
    print(f"Version bytes: {result['raw_version_bytes']}")
    print()
    print(f"{'#':>2}  {'name':<12} {'file offset':>12} {'size':>12} {'target':>12}  hash*   zero")
    for component in result["components"]:
        print(
            f"{component['index']:>2}  {component['name']:<12} "
            f"0x{component['file_offset']:08x} 0x{component['size']:08x} "
            f"0x{component['target_offset']:08x}  "
            f"{'MATCH' if component['package_region_digest_matches'] else 'layered':<7} "
            f"{'yes' if component['all_zero'] else 'no'}"
        )
    print("\n* 'layered' means the stored digest likely applies after another transform;")
    print("  it is not, by itself, evidence that the official package is damaged.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("firmware", type=pathlib.Path, help="path to a Leica .lfu file")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = parser.parse_args()
    try:
        result = inspect(args.firmware)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_table(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
