#!/usr/bin/env python3
"""Decode Leica 0x9033 Look tables from a PTP/IP PCAP-NG capture."""

from __future__ import annotations
import argparse, collections, pathlib, struct
from analyze_pcapng import tcp_packets, reassemble
from extract_look_uploads import packets


WIDTHS = {1:1, 2:1, 3:2, 4:2, 5:4, 6:4, 7:8, 8:8, 9:16, 10:16}


def parse_fields(data: bytes):
    count, = struct.unpack_from("<I", data); off = 4; fields = []
    for _ in range(count):
        marker, prop, dtype = struct.unpack_from("<IHH", data, off); off += 8
        value = None
        if dtype in WIDTHS:
            width = WIDTHS[dtype]; raw = data[off:off + width]; off += width
            value = int.from_bytes(raw, "little") if width <= 8 else raw
        elif dtype == 0xFFFF:
            n = data[off]; off += 1
            raw = data[off:off + n * 2]; off += n * 2
            value = raw[:-2].decode("utf-16le") if n else ""
        elif dtype == 0x4002:
            n, = struct.unpack_from("<I", data, off); off += 4 + n
            value = f"<{n} bytes>"
        elif dtype & 0x4000:
            n, = struct.unpack_from("<I", data, off); off += 4
            off += n * WIDTHS[dtype & 0x0FFF]
            value = f"<{n} elements>"
        else:
            raise ValueError(f"unknown type {dtype:#x}")
        fields.append((marker, prop, dtype, value))
    return fields, off


def looks(fields):
    records, current = [], {}
    names = {0xD861:"id", 0xD862:"slot", 0xDC44:"name", 0xD864:"type", 0xD866:"base"}
    for marker, prop, _dtype, value in fields:
        if prop == 0xD861 and current:
            records.append(current); current = {}
        if prop in names: current[names[prop]] = value
        current.setdefault("markers", set()).add(f"0x{marker:08X}")
    if current: records.append(current)
    return records


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("capture", type=pathlib.Path); args = ap.parse_args()
    client, server = collections.defaultdict(list), collections.defaultdict(list)
    for src, sport, dst, dport, seq, _flags, payload in tcp_packets(args.capture):
        if not payload: continue
        if dport == 15740: client[(src,sport,dst,dport)].append((seq,payload))
        if sport == 15740: server[(src,sport,dst,dport)].append((seq,payload))
    read_txs = set()
    for chunks in client.values():
        for kind, body in packets(reassemble(chunks)):
            if kind == 6 and len(body) >= 10:
                op, tx = struct.unpack_from("<HI", body, 4)
                if op == 0x9033: read_txs.add(tx)
    bodies = collections.defaultdict(bytearray)
    for chunks in server.values():
        for kind, body in packets(reassemble(chunks)):
            if kind in (10,12) and len(body) >= 4:
                tx, = struct.unpack_from("<I", body)
                if tx in read_txs: bodies[tx].extend(body[4:])
    for tx in sorted(read_txs):
        data = bytes(bodies[tx]); fields, used = parse_fields(data)
        print(f"tx={tx} bytes={len(data)} fields={len(fields)} parsed={used}")
        for rec in looks(fields): print("  " + " ".join(f"{k}={v}" for k,v in rec.items()))


if __name__ == "__main__": main()
