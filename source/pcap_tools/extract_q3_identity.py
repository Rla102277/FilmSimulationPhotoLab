#!/usr/bin/env python3
"""Extract link, DHCP, and Bonjour identity clues from an iOS PCAP-NG capture."""

from __future__ import annotations

import argparse
import ipaddress
import pathlib
import struct

from analyze_pcapng import blocks


def mac(value: bytes) -> str:
    return ":".join(f"{byte:02x}" for byte in value)


def strings(value: bytes, minimum: int = 4) -> list[str]:
    found: list[str] = []
    current = bytearray()
    for byte in value:
        if 32 <= byte < 127:
            current.append(byte)
        else:
            if len(current) >= minimum:
                found.append(current.decode("ascii"))
            current.clear()
    if len(current) >= minimum:
        found.append(current.decode("ascii"))
    return found


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=pathlib.Path)
    args = parser.parse_args()

    seen_dhcp: set[tuple[str, str, int]] = set()
    seen_mdns: set[bytes] = set()
    first_timestamp: float | None = None

    for order, kind, block in blocks(args.capture.read_bytes()):
        if kind != 6 or len(block) < 32:
            continue
        interface, ts_hi, ts_lo, captured = struct.unpack_from(order + "IIII", block, 8)
        timestamp = ((ts_hi << 32) | ts_lo) / 1_000_000
        first_timestamp = timestamp if first_timestamp is None else first_timestamp
        frame = block[28:28 + captured]
        if len(frame) < 42 or struct.unpack_from("!H", frame, 12)[0] != 0x0800:
            continue
        ethernet_src, ethernet_dst = mac(frame[6:12]), mac(frame[0:6])
        ip = frame[14:]
        ihl = (ip[0] & 15) * 4
        total = struct.unpack_from("!H", ip, 2)[0]
        if ip[9] != 17:
            continue
        src = str(ipaddress.ip_address(ip[12:16]))
        dst = str(ipaddress.ip_address(ip[16:20]))
        udp = ip[ihl:total]
        if len(udp) < 8:
            continue
        sport, dport = struct.unpack_from("!HH", udp)
        payload = udp[8:]
        delta = timestamp - first_timestamp

        if {sport, dport} == {67, 68} and len(payload) >= 44:
            xid = struct.unpack_from("!I", payload, 4)[0]
            client_mac = mac(payload[28:34])
            key = (src, dst, xid)
            if key not in seen_dhcp:
                seen_dhcp.add(key)
                print(
                    f"{delta:9.6f} if={interface} DHCP {src}:{sport} -> {dst}:{dport} "
                    f"eth={ethernet_src}->{ethernet_dst} xid=0x{xid:08x} chaddr={client_mac}"
                )

        if (sport == 5353 or dport == 5353) and src in {"192.168.54.10", "169.254.231.135"}:
            if payload in seen_mdns:
                continue
            seen_mdns.add(payload)
            clues = [
                text for text in strings(payload)
                if any(word in text for word in ("identifier=", "authTag=", "_ptp", "_remotepairing", "supportsRP", "iPhone", "rp"))
            ]
            if clues:
                print(
                    f"{delta:9.6f} if={interface} mDNS {src} "
                    f"eth={ethernet_src}->{ethernet_dst} {' | '.join(clues)}"
                )


if __name__ == "__main__":
    main()
