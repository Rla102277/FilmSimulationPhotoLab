#!/usr/bin/env python3
"""Extract TCP/PTP-IP sequences from pymobiledevice3's iOS PCAP-NG files."""

from __future__ import annotations

import argparse
import collections
import ipaddress
import pathlib
import struct


PTP_TYPES = {
    1: "InitCommandRequest",
    2: "InitCommandAck",
    3: "InitEventRequest",
    4: "InitEventAck",
    5: "InitFail",
    6: "OperationRequest",
    7: "OperationResponse",
    8: "Event",
    9: "StartData",
    10: "Data",
    11: "Cancel",
    12: "EndData",
    13: "ProbeRequest",
    14: "ProbeResponse",
}


def blocks(data: bytes):
    offset = 0
    byte_order = "<"
    while offset + 12 <= len(data):
        block_type, block_len = struct.unpack_from(byte_order + "II", data, offset)
        if block_type == 0x0A0D0D0A:
            bom = data[offset + 8 : offset + 12]
            byte_order = "<" if bom == b"\x4d\x3c\x2b\x1a" else ">"
            block_type, block_len = struct.unpack_from(byte_order + "II", data, offset)
        if block_len < 12 or offset + block_len > len(data):
            raise ValueError(f"invalid block at 0x{offset:x}: length {block_len}")
        yield byte_order, block_type, data[offset : offset + block_len]
        offset += block_len


def tcp_packets(path: pathlib.Path):
    for order, block_type, block in blocks(path.read_bytes()):
        if block_type != 6 or len(block) < 32:  # Enhanced Packet Block
            continue
        captured_len = struct.unpack_from(order + "I", block, 20)[0]
        frame = block[28 : 28 + captured_len]
        if len(frame) < 14 or struct.unpack_from("!H", frame, 12)[0] != 0x0800:
            continue
        ip = frame[14:]
        if len(ip) < 20 or ip[9] != 6:
            continue
        ip_header_len = (ip[0] & 0x0F) * 4
        total_len = struct.unpack_from("!H", ip, 2)[0]
        src = str(ipaddress.ip_address(ip[12:16]))
        dst = str(ipaddress.ip_address(ip[16:20]))
        tcp = ip[ip_header_len:total_len]
        if len(tcp) < 20:
            continue
        src_port, dst_port, sequence = struct.unpack_from("!HHI", tcp, 0)
        tcp_header_len = ((tcp[12] >> 4) & 0xF) * 4
        flags = tcp[13]
        payload = tcp[tcp_header_len:]
        yield (src, src_port, dst, dst_port, sequence, flags, payload)


def reassemble(chunks: list[tuple[int, bytes]]) -> bytes:
    if not chunks:
        return b""
    chunks.sort()
    output = bytearray()
    next_sequence = chunks[0][0]
    for sequence, payload in chunks:
        if not payload:
            continue
        if sequence > next_sequence:
            # Preserve a visible gap; PTP decoding restarts after it only manually.
            output.extend(b"\x00" * (sequence - next_sequence))
            next_sequence = sequence
        overlap = max(0, next_sequence - sequence)
        if overlap < len(payload):
            output.extend(payload[overlap:])
            next_sequence += len(payload) - overlap
    return bytes(output)


def decode_ptp(stream: bytes):
    offset = 0
    while offset + 8 <= len(stream):
        length, packet_type = struct.unpack_from("<II", stream, offset)
        if length < 8 or length > 64 * 1024 * 1024 or offset + length > len(stream):
            offset += 1
            continue
        packet = stream[offset : offset + length]
        details = ""
        if packet_type == 6 and length >= 18:
            phase = struct.unpack_from("<I", packet, 8)[0]
            opcode = struct.unpack_from("<H", packet, 12)[0]
            transaction = struct.unpack_from("<I", packet, 14)[0]
            params = [value[0] for value in struct.iter_unpack("<I", packet[18:])]
            details = f" phase={phase} op=0x{opcode:04x} tx={transaction} params={[hex(x) for x in params]}"
        elif packet_type == 7 and length >= 14:
            response = struct.unpack_from("<H", packet, 8)[0]
            transaction = struct.unpack_from("<I", packet, 10)[0]
            params = [value[0] for value in struct.iter_unpack("<I", packet[14:])]
            details = f" response=0x{response:04x} tx={transaction} params={[hex(x) for x in params]}"
        elif packet_type == 9 and length >= 20:
            transaction = struct.unpack_from("<I", packet, 8)[0]
            total = struct.unpack_from("<Q", packet, 12)[0]
            details = f" tx={transaction} total={total}"
        elif packet_type in (10, 12) and length >= 12:
            transaction = struct.unpack_from("<I", packet, 8)[0]
            details = f" tx={transaction} bytes={length - 12}"
        elif packet_type == 1 and length >= 28:
            guid = packet[8:24].hex()
            details = f" guid={guid}"
        elif packet_type == 2 and length >= 28:
            connection = struct.unpack_from("<I", packet, 8)[0]
            details = f" connection={connection}"
        elif packet_type == 3 and length >= 12:
            connection = struct.unpack_from("<I", packet, 8)[0]
            details = f" connection={connection}"
        yield offset, packet_type, PTP_TYPES.get(packet_type, "Unknown"), details
        offset += length


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture", type=pathlib.Path)
    parser.add_argument("--port", type=int, default=15740)
    args = parser.parse_args()

    directions: dict[tuple[str, int, str, int], list[tuple[int, bytes]]] = collections.defaultdict(list)
    for src, sport, dst, dport, sequence, _flags, payload in tcp_packets(args.capture):
        if args.port not in (sport, dport) or not payload:
            continue
        directions[(src, sport, dst, dport)].append((sequence, payload))

    for direction, chunks in sorted(directions.items()):
        stream = reassemble(chunks)
        print(f"\n{direction[0]}:{direction[1]} -> {direction[2]}:{direction[3]} ({len(stream)} bytes)")
        for offset, _packet_type, label, details in decode_ptp(stream):
            print(f"  +0x{offset:08x} {label}{details}")


if __name__ == "__main__":
    main()
