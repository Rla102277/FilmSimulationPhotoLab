#!/usr/bin/env python3
"""Read-only Leica Q3/Q3 43 Look-table probe for an iPhone Python app.

This sends only PTP/IP session setup plus Leica operation 0x9033. It contains
no 0x9035 upload implementation and does not change camera settings or Looks.
"""

from __future__ import annotations

import socket
import struct
import time


HOST = "192.168.54.1"
PORT = 15740
CONNECT_WINDOW_SECONDS = 90
MAX_PACKET = 16 * 1024 * 1024
WIDTHS = {1: 1, 2: 1, 3: 2, 4: 2, 5: 4, 6: 4, 7: 8, 8: 8, 9: 16, 10: 16}


def read_exact(sock: socket.socket, count: int) -> bytes:
    output = bytearray()
    while len(output) < count:
        chunk = sock.recv(count - len(output))
        if not chunk:
            raise ConnectionError("camera closed the connection")
        output.extend(chunk)
    return bytes(output)


def send_packet(sock: socket.socket, packet_type: int, body: bytes = b"") -> None:
    sock.sendall(struct.pack("<II", 8 + len(body), packet_type) + body)


def read_packet(sock: socket.socket) -> tuple[int, bytes]:
    length, packet_type = struct.unpack("<II", read_exact(sock, 8))
    if length < 8 or length > MAX_PACKET:
        raise ValueError(f"invalid PTP/IP packet length {length}")
    return packet_type, read_exact(sock, length - 8)


def connect() -> socket.socket:
    sock = socket.create_connection((HOST, PORT), timeout=3)
    sock.settimeout(10)
    return sock


def command_body(opcode: int, transaction: int, parameters: list[int]) -> bytes:
    return struct.pack("<IHI", 1, opcode, transaction) + b"".join(
        struct.pack("<I", value) for value in parameters
    )


def expect_ok(command: socket.socket, transaction: int) -> None:
    while True:
        packet_type, body = read_packet(command)
        if packet_type != 7 or len(body) < 6:
            continue
        response, response_transaction = struct.unpack_from("<HI", body)
        if response_transaction != transaction:
            continue
        if response != 0x2001:
            raise RuntimeError(
                f"camera returned 0x{response:04X} for transaction {transaction}"
            )
        return


def parse_fields(data: bytes):
    if len(data) < 4:
        raise ValueError("short Look table")
    field_count = struct.unpack_from("<I", data)[0]
    offset = 4
    fields = []
    for _ in range(field_count):
        if offset + 8 > len(data):
            raise ValueError("truncated Look field header")
        marker, prop, dtype = struct.unpack_from("<IHH", data, offset)
        offset += 8
        if dtype in WIDTHS:
            width = WIDTHS[dtype]
            raw = data[offset : offset + width]
            if len(raw) != width:
                raise ValueError("truncated scalar Look field")
            offset += width
            value = int.from_bytes(raw, "little") if width <= 8 else raw.hex()
        elif dtype == 0xFFFF:
            count = data[offset]
            offset += 1
            raw = data[offset : offset + count * 2]
            if len(raw) != count * 2:
                raise ValueError("truncated Look name")
            offset += count * 2
            value = raw[:-2].decode("utf-16le") if count else ""
        elif dtype == 0x4002:
            count = struct.unpack_from("<I", data, offset)[0]
            offset += 4 + count
            value = f"<{count} bytes>"
        elif dtype & 0x4000:
            count = struct.unpack_from("<I", data, offset)[0]
            offset += 4
            width = WIDTHS[dtype & 0x0FFF]
            offset += count * width
            value = f"<{count} elements>"
        else:
            raise ValueError(f"unknown Look field type 0x{dtype:04X}")
        if offset > len(data):
            raise ValueError("truncated Look field value")
        fields.append((marker, prop, value))
    return fields


def decode_looks(data: bytes) -> list[dict]:
    names = {0xD861: "id", 0xD862: "slot", 0xDC44: "name", 0xD864: "type", 0xD866: "base"}
    records = []
    current = {}
    for marker, prop, value in parse_fields(data):
        if prop == 0xD861 and current:
            records.append(current)
            current = {}
        if prop in names:
            current[names[prop]] = value
        current["marker"] = f"0x{marker:08X}"
    if current:
        records.append(current)
    return records


def run_probe() -> bytes:
    command = connect()
    print("  command TCP accepted")
    event = None
    try:
        init_body = bytes(16) + "OLS".encode("utf-16le") + struct.pack("<HH", 0, 1)
        send_packet(command, 1, init_body)
        packet_type, body = read_packet(command)
        if packet_type != 2 or len(body) < 4:
            raise RuntimeError("camera did not return InitCommandAck")
        connection_number = struct.unpack_from("<I", body)[0]
        print(f"  InitCommandAck connection={connection_number}")

        event = connect()
        print("  event TCP accepted")
        send_packet(event, 3, struct.pack("<I", connection_number))
        packet_type, _ = read_packet(event)
        if packet_type != 4:
            raise RuntimeError("camera did not return InitEventAck")
        print("  InitEventAck")

        # Every successful FOTOS trace from the Q3 and Q3 43 uses session 0x412.
        session_id = 0x412
        send_packet(command, 6, command_body(0x1002, 0, [session_id]))
        expect_ok(command, 0)
        print("  OpenSession 0x412 OK")
        send_packet(command, 6, command_body(0x9005, 1, [0xFF55]))
        expect_ok(command, 1)
        print("  Leica 0x9005 OK")

        transaction = 2
        send_packet(command, 6, command_body(0x9033, transaction, [0xFFFF, 0xFFFFFFFF]))
        print("  Leica Look read 0x9033 sent")
        result = bytearray()
        expected = None
        saw_end = False
        while True:
            packet_type, body = read_packet(command)
            if packet_type == 9 and len(body) >= 12:
                tx, expected = struct.unpack_from("<IQ", body)
                if tx != transaction:
                    expected = None
            elif packet_type in (10, 12) and len(body) >= 4:
                tx = struct.unpack_from("<I", body)[0]
                if tx == transaction:
                    result.extend(body[4:])
                    saw_end = saw_end or packet_type == 12
            elif packet_type == 7 and len(body) >= 6:
                response, tx = struct.unpack_from("<HI", body)
                if tx != transaction:
                    continue
                if response != 0x2001:
                    raise RuntimeError(f"0x9033 returned 0x{response:04X}")
                if not saw_end:
                    raise RuntimeError("0x9033 ended without Look-table data")
                if expected is not None and expected != len(result):
                    raise RuntimeError(
                        f"0x9033 declared {expected} bytes but sent {len(result)}"
                    )
                return bytes(result)
    finally:
        command.close()
        if event is not None:
            event.close()


def main() -> None:
    print("Q3 iPhone read-only handoff probe")
    print("Connect the Q3 in FOTOS, then leave/force-quit FOTOS and run this script.")
    print("Waiting for the camera's PTP listener; no Looks or settings will be changed.")
    deadline = time.monotonic() + CONNECT_WINDOW_SECONDS
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        print(f"attempt {attempt}")
        try:
            table = run_probe()
            with open("q3-look-table.bin", "wb") as output:
                output.write(table)
            print(f"SUCCESS: read {len(table)} Look-table bytes")
            for look in decode_looks(table):
                print(
                    f"slot={look.get('slot')} id={look.get('id')} "
                    f"name={look.get('name')} marker={look.get('marker')}"
                )
            print("Saved q3-look-table.bin")
            return
        except (OSError, ConnectionError, RuntimeError, ValueError) as error:
            print(f"  retrying: {error}")
            time.sleep(0.75)
    raise SystemExit("TIMEOUT: Q3 did not release/authorize the PTP listener")


if __name__ == "__main__":
    main()
