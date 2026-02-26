"""Standardized API response helpers."""

from __future__ import annotations

from typing import Any


def error_payload(
    *,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    request_id: str = "",
) -> dict[str, Any]:
    return {
        "ok": False,
        "error": str(message or "Request failed"),
        "error_message": str(message or "Request failed"),
        "error_code": str(code or "REQUEST_FAILED"),
        "code": str(code or "REQUEST_FAILED"),
        "message": str(message or "Request failed"),
        "details": details or {},
        "request_id": str(request_id or ""),
        "success": False,
    }


def success_payload(
    data: Any | None = None,
    *,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": True,
        "success": True,
    }
    if data is not None:
        payload["data"] = data
    if meta:
        payload["meta"] = meta
    return payload
