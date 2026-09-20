#!/usr/bin/env python3
"""Print an ordered IPv4 TCP/UDP payload timeline from pymobiledevice3 PCAP-NG."""

from __future__ import annotations
import argparse
import ipaddress
import pathlib
import struct


def blocks(data: bytes):
    off, order = 0, "<"
    while off + 12 <= len(data):
        kind, size = struct.unpack_from(order + "II", data, off)
        if kind == 0x0A0D0D0A:
            order = "<" if data[off + 8:off + 12] == b"\x4d\x3c\x2b\x1a" else ">"
            kind, size = struct.unpack_from(order + "II", data, off)
        if size < 12 or off + size > len(data):
            raise ValueError(f"bad block at {off:#x}")
        yield order, kind, data[off:off + size]
        off += size


def printable(data: bytes, limit: int = 180) -> str:
    text = "".join(chr(b) if 32 <= b < 127 else "." for b in data[:limit])
    return text + ("..." if len(data) > limit else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("capture", type=pathlib.Path)
    ap.add_argument("--host", default="192.168.54.")
    args = ap.parse_args()
    first_ts = None
    for order, kind, block in blocks(args.capture.read_bytes()):
        if kind != 6 or len(block) < 32:
            continue
        ts_hi, ts_lo, caplen = struct.unpack_from(order + "III", block, 12)
        timestamp = ((ts_hi << 32) | ts_lo) / 1_000_000
        first_ts = timestamp if first_ts is None else first_ts
        frame = block[28:28 + caplen]
        if len(frame) < 34 or struct.unpack_from("!H", frame, 12)[0] != 0x0800:
            continue
        ip = frame[14:]
        ihl, total, proto = (ip[0] & 15) * 4, struct.unpack_from("!H", ip, 2)[0], ip[9]
        src, dst = str(ipaddress.ip_address(ip[12:16])), str(ipaddress.ip_address(ip[16:20]))
        if not (src.startswith(args.host) or dst.startswith(args.host)):
            continue
        transport = ip[ihl:total]
        if proto == 6 and len(transport) >= 20:
            sport, dport = struct.unpack_from("!HH", transport)
            thl = ((transport[12] >> 4) & 15) * 4
            payload = transport[thl:]
            label = "TCP"
        elif proto == 17 and len(transport) >= 8:
            sport, dport = struct.unpack_from("!HH", transport)
            payload, label = transport[8:], "UDP"
        else:
            continue
        if not payload:
            continue
        delta = timestamp - first_ts
        print(f"{delta:10.6f} {label} {src}:{sport} -> {dst}:{dport} {len(payload):6d} {printable(payload)}")


if __name__ == "__main__":
    main()
