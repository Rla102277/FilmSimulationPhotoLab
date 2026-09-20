#!/usr/bin/env python3
"""Controlled official-Bleach upload test for an owned Leica Q3/Q3 43.

The script validates captured, unmodified Leica Bleach assets; inherits the
surviving FOTOS session; reads the Look table; performs at most one 0x9035
attempt; and reads the table again. It never retries an ambiguous write.
"""

from __future__ import annotations

import hashlib
import pathlib
import socket
import struct
import sys
import time
import traceback


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


def command_body(
    opcode: int, transaction: int, parameters: list[int], phase: int = 1
) -> bytes:
    return struct.pack("<IHI", phase, opcode, transaction) + b"".join(
        struct.pack("<I", value) for value in parameters
    )


def read_response(command: socket.socket, transaction: int) -> int:
    while True:
        packet_type, body = read_packet(command)
        if packet_type != 7 or len(body) < 6:
            continue
        response, response_transaction = struct.unpack_from("<HI", body)
        if response_transaction != transaction:
            continue
        return response


def expect_ok(command: socket.socket, transaction: int) -> None:
    response = read_response(command, transaction)
    if response != 0x2001:
        raise RuntimeError(
            f"camera returned 0x{response:04X} for transaction {transaction}"
        )


RESPONSE_NAMES = {
    0x2001: "OK",
    0x2002: "GeneralError",
    0x2003: "SessionNotOpen",
    0x2004: "InvalidTransactionID",
    0x2005: "OperationNotSupported",
    0x200F: "AccessDenied",
    0x201E: "SessionAlreadyOpen",
}


class AbortBeforeWrite(RuntimeError):
    """A verified safety condition that must not be retried."""


def response_name(code: int) -> str:
    return RESPONSE_NAMES.get(code, "UnknownResponse")


def read_data_operation(
    command: socket.socket,
    opcode: int,
    transaction: int,
    parameters: list[int],
    label: str,
) -> tuple[int, bytes]:
    send_packet(command, 6, command_body(opcode, transaction, parameters))
    print(f"  {label} sent: op=0x{opcode:04X} tx={transaction}")
    result = bytearray()
    expected = None
    packet_counts = {9: 0, 10: 0, 12: 0, 7: 0}
    while True:
        packet_type, body = read_packet(command)
        if packet_type in packet_counts:
            packet_counts[packet_type] += 1
        if packet_type == 9 and len(body) >= 12:
            tx, declared = struct.unpack_from("<IQ", body)
            if tx == transaction:
                expected = declared
                print(f"    StartData declared={declared}")
        elif packet_type in (10, 12) and len(body) >= 4:
            tx = struct.unpack_from("<I", body)[0]
            if tx == transaction:
                result.extend(body[4:])
                if packet_type == 12:
                    print(f"    EndData accumulated={len(result)}")
        elif packet_type == 7 and len(body) >= 6:
            response, tx = struct.unpack_from("<HI", body)
            if tx != transaction:
                continue
            print(
                f"    response=0x{response:04X} {response_name(response)} "
                f"bytes={len(result)} packets={packet_counts}"
            )
            if expected is not None and expected != len(result):
                raise RuntimeError(
                    f"{label}: declared {expected} bytes but received {len(result)}"
                )
            return response, bytes(result)


def run_read_suite(command: socket.socket, first_transaction: int) -> bytes:
    response, device_info = read_data_operation(
        command, 0x1001, first_transaction, [], "standard DeviceInfo read"
    )
    if response != 0x2001:
        raise RuntimeError(
            f"DeviceInfo returned 0x{response:04X} {response_name(response)}"
        )
    if len(device_info) < 100:
        raise RuntimeError(f"DeviceInfo returned only {len(device_info)} bytes")
    print(f"  DeviceInfo PASS ({len(device_info)} bytes)")

    response, look_table = read_data_operation(
        command,
        0x9033,
        first_transaction + 1,
        [0xFFFF, 0xFFFFFFFF],
        "Leica Look-table read",
    )
    if response != 0x2001:
        raise RuntimeError(
            f"0x9033 returned 0x{response:04X} {response_name(response)}"
        )
    if not look_table:
        raise RuntimeError("0x9033 returned OK without Look-table data")
    return look_table


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


BLEACH_CUBE_SHA256 = "c2a58164e543704189ef84d8c9b28f4deaac226bde94a3134f69a72a583f50f6"
BLEACH_ICON_SHA256 = "1d8b2d6c9e66506cf02c81f7a28f77fa5a2cf9b108128a9a279e963bea4e0288"


def load_and_validate_assets() -> tuple[bytes, bytes]:
    folder = pathlib.Path(__file__).resolve().parent
    cube_path = folder / "Bleach.CUBE"
    icon_path = folder / "Bleach.bmp"
    cube = cube_path.read_bytes()
    icon = icon_path.read_bytes()
    cube_hash = hashlib.sha256(cube).hexdigest()
    icon_hash = hashlib.sha256(icon).hexdigest()
    print(f"asset CUBE: {len(cube)} bytes sha256={cube_hash}")
    print(f"asset icon: {len(icon)} bytes sha256={icon_hash}")
    if len(cube) != 132912 or cube_hash != BLEACH_CUBE_SHA256:
        raise SystemExit("ABORT: Bleach.CUBE is not the captured official Leica asset")
    if len(icon) != 2224 or icon_hash != BLEACH_ICON_SHA256:
        raise SystemExit("ABORT: Bleach.bmp is not the captured official Leica asset")
    text = cube[:400].decode("ascii", errors="replace")
    required = ("#Unique Leica Look ID: 22", 'TITLE "Bleach"', "LUT_3D_SIZE 17")
    if not all(value in text for value in required):
        raise SystemExit("ABORT: official Bleach CUBE metadata did not validate")
    if icon[:2] != b"BM":
        raise SystemExit("ABORT: official Bleach icon is not a BMP")
    print("asset validation PASS: official unmodified Leica Bleach ID 22")
    return cube, icon


def field_prefix(marker: int, prop: int, dtype: int) -> bytes:
    return struct.pack("<IHH", marker, prop, dtype)


def uint32_field(marker: int, prop: int, value: int) -> bytes:
    return field_prefix(marker, prop, 0x0006) + struct.pack("<I", value)


def string_field(marker: int, prop: int, value: str) -> bytes:
    units = value.encode("utf-16le")
    count = len(units) // 2 + 1
    return field_prefix(marker, prop, 0xFFFF) + bytes([count]) + units + b"\x00\x00"


def byte_array_field(marker: int, prop: int, value: bytes) -> bytes:
    return field_prefix(marker, prop, 0x4002) + struct.pack("<I", len(value)) + value


def next_record_marker(look_table: bytes) -> int:
    fields = parse_fields(look_table)
    markers = [marker for marker, _prop, _value in fields]
    if not markers or min(markers) < 0x2000000F or max(markers) >= 0x20FFFFFF:
        raise RuntimeError("Look table has no valid Leica record markers")
    return max(markers) + 1


def build_bleach_payload(cube: bytes, icon: bytes, marker: int) -> bytes:
    payload = b"".join(
        (
            struct.pack("<I", 6),
            uint32_field(marker, 0xD861, 22),
            string_field(marker, 0xDC44, "Bleach"),
            byte_array_field(marker, 0xDC86, icon),
            byte_array_field(marker, 0xD860, cube),
            uint32_field(marker, 0xD864, 2),
            uint32_field(marker, 0xD866, 0),
        )
    )
    if len(payload) != 135223:
        raise RuntimeError(f"payload length is {len(payload)}, expected 135223")
    fields = parse_fields(payload)
    decoded = decode_looks(payload)
    if len(fields) != 6 or len(decoded) != 1 or decoded[0].get("id") != 22:
        raise RuntimeError("locally built Bleach payload did not decode correctly")
    print(
        f"payload validation PASS: {len(payload)} bytes, marker=0x{marker:08X}, "
        f"sha256={hashlib.sha256(payload).hexdigest()}"
    )
    return payload


def upload_once(command: socket.socket, transaction: int, payload: bytes) -> int:
    print(f"WRITE START: one 0x9035 attempt tx={transaction} bytes={len(payload)}")
    send_packet(command, 6, command_body(0x9035, transaction, [], phase=2))
    send_packet(command, 9, struct.pack("<IQ", transaction, len(payload)))
    offset = 0
    chunk_size = 1000
    next_progress = 25
    while len(payload) - offset > chunk_size:
        chunk = payload[offset : offset + chunk_size]
        send_packet(command, 10, struct.pack("<I", transaction) + chunk)
        offset += len(chunk)
        progress = offset * 100 // len(payload)
        if progress >= next_progress:
            print(f"  upload progress {progress}%")
            next_progress += 25
    send_packet(command, 12, struct.pack("<I", transaction) + payload[offset:])
    print("  EndData sent; waiting for camera response")
    response = read_response(command, transaction)
    print(f"WRITE RESULT: 0x{response:04X} {response_name(response)}")
    return response


def open_surviving_fotos_session() -> tuple[socket.socket, socket.socket]:
    command = connect()
    print("command TCP accepted")
    event = None
    try:
        init_body = bytes(16) + "OLS".encode("utf-16le") + struct.pack("<HH", 0, 1)
        send_packet(command, 1, init_body)
        packet_type, body = read_packet(command)
        if packet_type != 2 or len(body) < 4:
            raise RuntimeError("camera did not return InitCommandAck")
        connection_number = struct.unpack_from("<I", body)[0]
        print(f"InitCommandAck connection={connection_number}")
        event = connect()
        print("event TCP accepted")
        send_packet(event, 3, struct.pack("<I", connection_number))
        packet_type, _ = read_packet(event)
        if packet_type != 4:
            raise RuntimeError("camera did not return InitEventAck")
        print("InitEventAck")
        send_packet(command, 6, command_body(0x1002, 0, [0x412]))
        response = read_response(command, 0)
        print(f"OpenSession response=0x{response:04X} {response_name(response)}")
        if response != 0x201E:
            raise AbortBeforeWrite(
                "ABORT BEFORE WRITE: surviving authenticated FOTOS session was not present"
            )
        print("surviving FOTOS session confirmed")
        return command, event
    except Exception:
        command.close()
        if event is not None:
            event.close()
        raise


def main() -> None:
    print("Q3 iPhone controlled official Bleach upload test")
    print(f"Python {sys.version.split()[0]} · target {HOST}:{PORT}")
    cube, icon = load_and_validate_assets()
    print("This will make exactly one write attempt only after a successful pre-read.")
    confirmation = input("Type UPLOAD to arm the official Bleach test: ").strip()
    if confirmation != "UPLOAD":
        raise SystemExit("NOT ARMED: no camera connection or write attempted")
    print("ARMED. Beginning the surviving-session takeover now.")
    deadline = time.monotonic() + CONNECT_WINDOW_SECONDS
    attempt = 0
    command = None
    event = None
    while time.monotonic() < deadline:
        attempt += 1
        print(f"attempt {attempt}")
        try:
            command, event = open_surviving_fotos_session()
            selected_base = None
            before = None
            for base in (0x10000, 0x20000, 0x7F000000):
                try:
                    print(f"pre-write read using transaction base {base}")
                    before = run_read_suite(command, base)
                    selected_base = base
                    break
                except RuntimeError as error:
                    print(f"transaction base {base} failed before write: {error}")
            if selected_base is None or before is None:
                raise AbortBeforeWrite("ABORT BEFORE WRITE: no transaction base passed")

            before_looks = decode_looks(before)
            print(f"PRE-WRITE TABLE: {len(before)} bytes, {len(before_looks)} Looks")
            for look in before_looks:
                print(
                    f"slot={look.get('slot')} id={look.get('id')} "
                    f"name={look.get('name')} marker={look.get('marker')}"
                )
            if any(look.get("id") == 22 for look in before_looks):
                raise AbortBeforeWrite(
                    "ABORT BEFORE WRITE: Bleach ID 22 is already installed"
                )
            if len(before_looks) >= 8:
                raise AbortBeforeWrite(
                    "ABORT BEFORE WRITE: no empty downloadable-Look capacity"
                )

            marker = next_record_marker(before)
            payload = build_bleach_payload(cube, icon, marker)
            upload_transaction = selected_base + 2
            try:
                response = upload_once(command, upload_transaction, payload)
            except Exception as error:
                print(
                    "AMBIGUOUS WRITE STATE: connection failed after WRITE START. "
                    "DO NOT RUN AGAIN until the Leica Looks menu is inspected."
                )
                print(f"write exception: {type(error).__name__} {error!r}")
                traceback.print_exc(limit=3)
                command.close()
                event.close()
                return

            if response not in (0x2001, 0x200F):
                print("Unexpected response. Do not rerun until the camera menu is inspected.")

            try:
                post_response, after = read_data_operation(
                    command,
                    0x9033,
                    upload_transaction + 1,
                    [0xFFFF, 0xFFFFFFFF],
                    "post-write Leica Look-table read",
                )
                if post_response == 0x2001:
                    after_looks = decode_looks(after)
                    print(f"POST-WRITE TABLE: {len(after)} bytes, {len(after_looks)} Looks")
                    for look in after_looks:
                        print(
                            f"slot={look.get('slot')} id={look.get('id')} "
                            f"name={look.get('name')} marker={look.get('marker')}"
                        )
                    installed = any(
                        look.get("id") == 22 and look.get("name") == "Bleach"
                        for look in after_looks
                    )
                    print(f"FINAL VERDICT: Bleach installed={installed}")
                else:
                    print(
                        f"post-write read returned 0x{post_response:04X} "
                        f"{response_name(post_response)}"
                    )
            except Exception as error:
                print(f"post-write verification failed: {type(error).__name__} {error!r}")
            print("TEST COMPLETE. Do not run this script a second time.")
            command.close()
            event.close()
            return
        except AbortBeforeWrite as error:
            print(str(error))
            if command is not None:
                command.close()
            if event is not None:
                event.close()
            raise SystemExit("SAFE STOP: no upload was attempted")
        except (OSError, ConnectionError, RuntimeError, ValueError) as error:
            errno_value = getattr(error, "errno", None)
            print(
                f"retrying before any write: type={type(error).__name__} "
                f"errno={errno_value!r} detail={error!r}"
            )
            traceback.print_exc(limit=2)
            if command is not None:
                command.close()
                command = None
            if event is not None:
                event.close()
                event = None
            time.sleep(0.75)
        finally:
            # Kept open through post-write verification, then closed here.
            pass
    raise SystemExit("TIMEOUT BEFORE WRITE: no upload was attempted")


if __name__ == "__main__":
    main()
