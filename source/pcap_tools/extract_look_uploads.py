#!/usr/bin/env python3
"""Extract and summarize Leica 0x9035 payloads from an iOS PCAP-NG capture."""

from __future__ import annotations
import argparse
import collections
import pathlib
import struct

from analyze_pcapng import tcp_packets, reassemble


def packets(stream: bytes):
    off = 0
    while off + 8 <= len(stream):
        size, kind = struct.unpack_from("<II", stream, off)
        if size < 8 or size > 64 * 1024 * 1024 or off + size > len(stream):
            off += 1
            continue
        yield kind, stream[off + 8:off + size]
        off += size


def parse_look(data: bytes):
    names = {0xD861: "lookID", 0xDC44: "name", 0xDC86: "icon", 0xD860: "cube",
             0xD864: "type", 0xD866: "baseStyle"}
    off = 0
    count, = struct.unpack_from("<I", data, off); off += 4
    values = {}
    for _ in range(count):
        marker, code, dtype = struct.unpack_from("<IHH", data, off); off += 8
        if marker not in (0x20000014, 0x20000015):
            raise ValueError(f"bad marker {marker:#x} at {off - 8:#x}")
        values.setdefault("recordMarkers", set()).add(f"0x{marker:08X}")
        if dtype == 0x0006:
            value, = struct.unpack_from("<I", data, off); off += 4
        elif dtype == 0xFFFF:
            units = data[off]; off += 1
            raw = data[off:off + units * 2]; off += units * 2
            value = raw[:-2].decode("utf-16le") if units else ""
        elif dtype == 0x4002:
            size, = struct.unpack_from("<I", data, off); off += 4
            value = data[off:off + size]; off += size
        else:
            raise ValueError(f"unsupported datatype {dtype:#x}")
        values[names.get(code, f"0x{code:04X}")] = value
    if off != len(data):
        values["trailingBytes"] = len(data) - off
    return values


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("capture", type=pathlib.Path)
    ap.add_argument("--out-dir", type=pathlib.Path)
    args = ap.parse_args()
    flows = collections.defaultdict(list)
    for src, sport, dst, dport, seq, _flags, payload in tcp_packets(args.capture):
        if dport == 15740 and payload:
            flows[(src, sport, dst, dport)].append((seq, payload))
    for flow, chunks in sorted(flows.items()):
        current = set()
        bodies = collections.defaultdict(bytearray)
        totals = {}
        for kind, body in packets(reassemble(chunks)):
            if kind == 6 and len(body) >= 10:
                op, tx = struct.unpack_from("<HI", body, 4)
                if op == 0x9035:
                    current.add(tx)
            elif kind == 9 and len(body) >= 12:
                tx, total = struct.unpack_from("<IQ", body)
                if tx in current: totals[tx] = total
            elif kind in (10, 12) and len(body) >= 4:
                tx, = struct.unpack_from("<I", body)
                if tx in current: bodies[tx].extend(body[4:])
        for tx in sorted(current):
            blob = bytes(bodies[tx])
            values = parse_look(blob)
            print(f"tx={tx} payload={len(blob)} declared={totals.get(tx)}")
            for key, value in values.items():
                print(f"  {key}={len(value)} bytes" if isinstance(value, bytes) else f"  {key}={value}")
            if args.out_dir:
                args.out_dir.mkdir(parents=True, exist_ok=True)
                stem = f"tx{tx}_{values.get('name', 'unknown')}"
                (args.out_dir / f"{stem}.payload").write_bytes(blob)
                if isinstance(values.get("cube"), bytes): (args.out_dir / f"{stem}.CUBE").write_bytes(values["cube"])
                if isinstance(values.get("icon"), bytes): (args.out_dir / f"{stem}.bmp").write_bytes(values["icon"])


if __name__ == "__main__":
    main()
