"""Read-only Kaspa wRPC JSON probe.

The target is fixed to 127.0.0.1:18210. Callers cannot supply a URL.
This module does not proxy the socket to a public client.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import socket
import struct
import time
from typing import Any

TARGET_HOST = "127.0.0.1"
TARGET_PORT = 18210
_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
_MAX_FRAME = 200_000
_TOKEN = re.compile(r"[A-Za-z0-9_.:-]{1,64}")


def probe_tn10_loopback(timeout_s: float = 1.0) -> dict[str, Any]:
    body: dict[str, Any] = {
        "target": f"{TARGET_HOST}:{TARGET_PORT}",
        "exposed_publicly": False,
        "proxied": False,
        "listening": False,
        "answered": False,
        "network_id": None,
        "is_synced": None,
        "has_utxo_index": None,
        "virtual_daa_score": None,
        "header_count": None,
        "block_count": None,
        "sync_note": None,
        "error": None,
    }
    deadline = time.monotonic() + max(0.3, timeout_s)
    try:
        sock = socket.create_connection(
            (TARGET_HOST, TARGET_PORT),
            timeout=min(0.4, timeout_s),
        )
    except ConnectionRefusedError:
        body["error"] = "not_listening"
        return body
    except OSError:
        body["error"] = "unreachable"
        return body
    body["listening"] = True
    try:
        leftover = _handshake(sock, deadline)
        server, leftover = _rpc(sock, 1, "getServerInfo", leftover, deadline)
        dag, _rest = _rpc(sock, 2, "getBlockDagInfo", leftover, deadline)
        body.update(summarize_wrpc(server, dag))
        body["answered"] = True
        body["error"] = None
    except Exception:
        body["answered"] = False
        body["error"] = "unreadable"
    finally:
        try:
            sock.close()
        except OSError:
            pass
    return body


def summarize_wrpc(server: Any, dag: Any) -> dict[str, Any]:
    server_obj = _params(server)
    dag_obj = _params(dag)
    headers = _count(dag_obj.get("headerCount", dag_obj.get("header_count")))
    blocks = _count(dag_obj.get("blockCount", dag_obj.get("block_count")))
    note = None
    if headers is not None and blocks is not None and headers - blocks > 100:
        note = "header count is ahead of block count"
    return {
        "network_id": _token(server_obj.get("networkId", server_obj.get("network_id"))),
        "is_synced": _flag(server_obj.get("isSynced", server_obj.get("is_synced"))),
        "has_utxo_index": _flag(server_obj.get("hasUtxoIndex", server_obj.get("has_utxo_index"))),
        "virtual_daa_score": _count(
            server_obj.get("virtualDaaScore", server_obj.get("virtual_daa_score"))
        ),
        "header_count": headers,
        "block_count": blocks,
        "sync_note": note,
    }


def _params(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    inner = payload.get("params")
    if isinstance(inner, dict):
        return inner
    result = payload.get("result")
    if isinstance(result, dict):
        return result
    return payload


def _token(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if _TOKEN.fullmatch(text):
        return text
    return None


def _flag(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _count(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value < 0 or value > 10**18:
        return None
    return value


def _remaining(deadline: float) -> float:
    left = deadline - time.monotonic()
    if left <= 0:
        raise TimeoutError
    return left


def _handshake(sock: socket.socket, deadline: float) -> bytes:
    key = base64.b64encode(os.urandom(16)).decode("ascii")
    expected = base64.b64encode(
        hashlib.sha1((key + _WS_GUID).encode("ascii")).digest()
    ).decode("ascii")
    request = (
        "GET / HTTP/1.1\r\n"
        f"Host: {TARGET_HOST}:{TARGET_PORT}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "\r\n"
    )
    sock.sendall(request.encode("ascii"))
    buf = b""
    while b"\r\n\r\n" not in buf:
        sock.settimeout(_remaining(deadline))
        chunk = sock.recv(4096)
        if not chunk:
            raise RuntimeError("closed")
        buf += chunk
        if len(buf) > 8192:
            raise RuntimeError("header")
    head, rest = buf.split(b"\r\n\r\n", 1)
    status = head.split(b"\r\n", 1)[0]
    if b" 101" not in status:
        raise RuntimeError("upgrade")
    if expected.encode("ascii") not in head:
        raise RuntimeError("accept")
    return rest


def _send_text(sock: socket.socket, text: str) -> None:
    payload = text.encode("utf-8")
    if len(payload) > 4096:
        raise RuntimeError("request")
    mask = os.urandom(4)
    header = bytearray([0x81, 0x80 | len(payload)])
    header.extend(mask)
    masked = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
    sock.sendall(bytes(header) + masked)


def _recv_text(sock: socket.socket, buf: bytes, deadline: float) -> tuple[str, bytes]:
    for _ in range(8):
        frame, buf = _read_frame(sock, buf, deadline)
        opcode, payload = frame
        if opcode == 0x9:
            _send_pong(sock, payload)
            continue
        if opcode == 0x8:
            raise RuntimeError("close")
        if opcode != 0x1:
            continue
        return payload.decode("utf-8", errors="replace"), buf
    raise RuntimeError("frame")


def _send_pong(sock: socket.socket, payload: bytes) -> None:
    if len(payload) > 125:
        payload = payload[:125]
    mask = os.urandom(4)
    header = bytearray([0x8A, 0x80 | len(payload)])
    header.extend(mask)
    masked = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
    sock.sendall(bytes(header) + masked)


def _read_exact(sock: socket.socket, buf: bytes, n: int, deadline: float) -> tuple[bytes, bytes]:
    while len(buf) < n:
        sock.settimeout(_remaining(deadline))
        chunk = sock.recv(min(65536, n - len(buf) + 1024))
        if not chunk:
            raise RuntimeError("closed")
        buf += chunk
        if len(buf) > _MAX_FRAME + 16:
            raise RuntimeError("size")
    return buf[:n], buf[n:]


def _read_frame(
    sock: socket.socket, buf: bytes, deadline: float
) -> tuple[tuple[int, bytes], bytes]:
    head, buf = _read_exact(sock, buf, 2, deadline)
    opcode = head[0] & 0x0F
    if (head[0] & 0x80) == 0:
        raise RuntimeError("fragment")
    masked = bool(head[1] & 0x80)
    length = head[1] & 0x7F
    if length == 126:
        raw, buf = _read_exact(sock, buf, 2, deadline)
        length = struct.unpack("!H", raw)[0]
    elif length == 127:
        raw, buf = _read_exact(sock, buf, 8, deadline)
        length = struct.unpack("!Q", raw)[0]
    if length > _MAX_FRAME:
        raise RuntimeError("size")
    mask = b""
    if masked:
        mask, buf = _read_exact(sock, buf, 4, deadline)
    payload, buf = _read_exact(sock, buf, length, deadline)
    if masked:
        payload = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
    return (opcode, payload), buf


def _rpc(
    sock: socket.socket,
    req_id: int,
    method: str,
    leftover: bytes,
    deadline: float,
) -> tuple[dict[str, Any], bytes]:
    _send_text(sock, json.dumps({"id": req_id, "method": method, "params": {}}))
    buf = leftover
    for _ in range(6):
        text, buf = _recv_text(sock, buf, deadline)
        try:
            body = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(body, dict) and body.get("id") == req_id:
            return body, buf
    raise RuntimeError("response")
