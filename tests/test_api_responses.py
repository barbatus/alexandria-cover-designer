from __future__ import annotations

from src import api_responses


def test_error_payload_shape():
    payload = api_responses.error_payload(
        code="INVALID_BOOK_NUMBER",
        message="Book number invalid",
        details={"received": "x"},
        request_id="req-1",
    )
    assert payload["ok"] is False
    assert payload["success"] is False
    assert payload["error"] == "Book number invalid"
    assert payload["error_message"] == "Book number invalid"
    assert payload["error_code"] == "INVALID_BOOK_NUMBER"
    assert payload["code"] == "INVALID_BOOK_NUMBER"
    assert payload["message"] == "Book number invalid"
    assert payload["request_id"] == "req-1"
    assert payload["details"]["received"] == "x"


def test_success_payload_with_data_and_meta():
    payload = api_responses.success_payload(data={"ok": True}, meta={"count": 1})
    assert payload["ok"] is True
    assert payload["success"] is True
    assert payload["data"]["ok"] is True
    assert payload["meta"]["count"] == 1


def test_success_payload_without_data():
    payload = api_responses.success_payload()
    assert payload == {"ok": True, "success": True}
