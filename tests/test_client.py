import json

import pytest
import respx
from httpx import Response

from fellowai.client import (
    AuthError,
    BadRequestError,
    FellowClient,
    NotFoundError,
    RateLimitError,
    ServerError,
)


def _client() -> FellowClient:
    return FellowClient(subdomain="test", api_key="key-abc")


@respx.mock
def test_get_me_success():
    respx.get("https://test.fellow.app/api/v1/me").mock(
        return_value=Response(200, json={
            "user": {"id": "u1", "email": "x@y.com", "full_name": "X Y"},
            "workspace": {"id": "w1", "name": "wsname", "subdomain": "test"},
        })
    )
    me = _client().get_me()
    assert me["user"]["email"] == "x@y.com"
    assert me["workspace"]["subdomain"] == "test"


@respx.mock
def test_auth_header_sent():
    route = respx.get("https://test.fellow.app/api/v1/me").mock(
        return_value=Response(200, json={"user": {}, "workspace": {}})
    )
    _client().get_me()
    assert route.calls[0].request.headers["X-API-KEY"] == "key-abc"


@respx.mock
def test_401_raises_auth_error():
    respx.get("https://test.fellow.app/api/v1/me").mock(
        return_value=Response(401, json={"detail": "Unauthorized"})
    )
    with pytest.raises(AuthError, match="Unauthorized"):
        _client().get_me()


@respx.mock
def test_404_raises_not_found():
    respx.get("https://test.fellow.app/api/v1/recording/x").mock(
        return_value=Response(404, json={"detail": "Recording not found"})
    )
    with pytest.raises(NotFoundError, match="Recording not found"):
        _client().get_recording("x")


@respx.mock
def test_400_simple_detail_raises_bad_request():
    respx.get("https://test.fellow.app/api/v1/recording/x").mock(
        return_value=Response(400, json={"detail": "Invalid recording ID format"})
    )
    with pytest.raises(BadRequestError, match="Invalid recording ID format"):
        _client().get_recording("x")


@respx.mock
def test_400_structured_validation_raises_bad_request_with_locations():
    respx.post("https://test.fellow.app/api/v1/recordings").mock(
        return_value=Response(400, json={
            "message": "Request could not be completed due to validation errors.",
            "errors": [{"location": "page_size", "message": "Input should be less than or equal to 50"}],
        })
    )
    with pytest.raises(BadRequestError) as exc:
        list(_client().list_recordings(page_size=49))
    assert "page_size" in str(exc.value)
    assert "less than or equal to 50" in str(exc.value)


@respx.mock
def test_429_raises_rate_limit_error():
    respx.get("https://test.fellow.app/api/v1/me").mock(
        return_value=Response(429, json={"detail": "rate_limited"})
    )
    with pytest.raises(RateLimitError):
        _client().get_me()


@respx.mock
def test_500_raises_server_error():
    respx.get("https://test.fellow.app/api/v1/me").mock(
        return_value=Response(500, text="Internal Server Error")
    )
    with pytest.raises(ServerError):
        _client().get_me()


@respx.mock
def test_pagination_walks_cursors_until_null():
    # Page 1: returns cursor "p2", 2 items
    # Page 2: returns cursor null, 1 item
    route = respx.post("https://test.fellow.app/api/v1/recordings")
    route.mock(side_effect=[
        Response(200, json={
            "recordings": {
                "page_info": {"cursor": "p2", "page_size": 2},
                "data": [{"id": "r1"}, {"id": "r2"}],
            }
        }),
        Response(200, json={
            "recordings": {
                "page_info": {"cursor": None, "page_size": 2},
                "data": [{"id": "r3"}],
            }
        }),
    ])
    items = list(_client().list_recordings(page_size=2))
    assert [i["id"] for i in items] == ["r1", "r2", "r3"]
    assert len(route.calls) == 2
    import json
    assert json.loads(route.calls[1].request.read()) == {"pagination": {"cursor": "p2", "page_size": 2}}


@respx.mock
def test_pagination_honors_limit():
    route = respx.post("https://test.fellow.app/api/v1/recordings")
    route.mock(side_effect=[
        Response(200, json={
            "recordings": {
                "page_info": {"cursor": "p2", "page_size": 10},
                "data": [{"id": f"r{i}"} for i in range(10)],
            }
        }),
    ])
    items = list(_client().list_recordings(limit=3, page_size=10))
    assert len(items) == 3
    assert len(route.calls) == 1  # didn't fetch the second page


def test_client_validates_page_size_bounds():
    with pytest.raises(ValueError, match="page_size"):
        list(_client().list_recordings(page_size=51))
    with pytest.raises(ValueError, match="page_size"):
        list(_client().list_recordings(page_size=0))


@respx.mock
def test_subdomain_returns_html_raises_auth_error():
    # Wrong-subdomain probe returned HTML at 200 — we treat as auth failure.
    respx.get("https://wrong.fellow.app/api/v1/me").mock(
        return_value=Response(200, html="<!doctype html><html>...</html>")
    )
    client = FellowClient(subdomain="wrong", api_key="x")
    with pytest.raises(AuthError, match="subdomain"):
        client.get_me()


@respx.mock
def test_retries_on_429_then_succeeds(monkeypatch: pytest.MonkeyPatch):
    sleeps: list[float] = []
    monkeypatch.setattr("fellowai.client.time.sleep", lambda s: sleeps.append(s))
    respx.get("https://test.fellow.app/api/v1/me").mock(side_effect=[
        Response(429, json={"detail": "rate_limited"}, headers={"Retry-After": "1"}),
        Response(200, json={"user": {}, "workspace": {}}),
    ])
    _client().get_me()
    assert sleeps == [1.0]


@respx.mock
def test_retries_on_500_with_exponential_backoff(monkeypatch: pytest.MonkeyPatch):
    sleeps: list[float] = []
    monkeypatch.setattr("fellowai.client.time.sleep", lambda s: sleeps.append(s))
    respx.get("https://test.fellow.app/api/v1/me").mock(side_effect=[
        Response(500, text="bad"),
        Response(500, text="bad"),
        Response(200, json={"user": {}, "workspace": {}}),
    ])
    _client().get_me()
    assert sleeps == [1.0, 2.0]


@respx.mock
def test_gives_up_after_max_retries(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("fellowai.client.time.sleep", lambda s: None)
    respx.get("https://test.fellow.app/api/v1/me").mock(
        return_value=Response(500, text="bad"),
    )
    with pytest.raises(ServerError):
        _client().get_me()


# Filter/include whitelists

ALLOWED_RECORDING_FILTERS = {
    "event_guid", "created_at_start", "created_at_end",
    "updated_at_start", "updated_at_end", "channel_id", "title",
}
ALLOWED_RECORDING_INCLUDES = {"transcript", "ai_notes", "media_url"}
ALLOWED_ACTION_ITEM_FILTERS = {
    "scope", "completed", "archived", "ai_detected", "ai_suggestion_accepted_by_user",
}


def test_rejects_unknown_recording_filter():
    with pytest.raises(ValueError, match="Unknown filter"):
        list(_client().list_recordings(filters={"titel": "x"}))


def test_rejects_unknown_recording_include():
    with pytest.raises(ValueError, match="Unknown include"):
        list(_client().list_recordings(include={"transcrip": True}))


def test_rejects_unknown_action_item_filter():
    with pytest.raises(ValueError, match="Unknown filter"):
        list(_client().list_action_items(filters={"compleeted": True}))


@respx.mock
def test_list_notes():
    respx.post("https://test.fellow.app/api/v1/notes").mock(
        return_value=Response(200, json={
            "notes": {
                "page_info": {"cursor": None, "page_size": 20},
                "data": [{"id": "n1", "title": "T"}],
            }
        }),
    )
    items = list(_client().list_notes())
    assert items == [{"id": "n1", "title": "T"}]


@respx.mock
def test_get_note():
    respx.get("https://test.fellow.app/api/v1/note/abc").mock(
        return_value=Response(200, json={"note": {"id": "abc"}})
    )
    note = _client().get_note("abc")
    assert note["id"] == "abc"


@respx.mock
def test_list_action_items_sends_filters_and_order():
    route = respx.post("https://test.fellow.app/api/v1/action_items").mock(
        return_value=Response(200, json={
            "action_items": {
                "page_info": {"cursor": None, "page_size": 20},
                "data": [],
            }
        }),
    )
    list(_client().list_action_items(
        filters={"scope": "assigned_to_me", "completed": False},
        order_by="due_date",
    ))
    sent = json.loads(route.calls[0].request.read())
    assert sent["filters"] == {"scope": "assigned_to_me", "completed": False}
    assert sent["order_by"] == "due_date"


@respx.mock
def test_get_action_item():
    respx.get("https://test.fellow.app/api/v1/action_item/x").mock(
        return_value=Response(200, json={"action_item": {"id": "x", "status": "Incomplete"}})
    )
    item = _client().get_action_item("x")
    assert item["status"] == "Incomplete"


@respx.mock
def test_set_action_item_completed_true():
    route = respx.post("https://test.fellow.app/api/v1/action_item/x/complete").mock(
        return_value=Response(200, json={"action_item": {"id": "x", "status": "Done"}})
    )
    result = _client().set_action_item_completed("x", True)
    assert result["status"] == "Done"
    assert json.loads(route.calls[0].request.read()) == {"completed": True}


@respx.mock
def test_set_action_item_completed_false():
    route = respx.post("https://test.fellow.app/api/v1/action_item/x/complete").mock(
        return_value=Response(200, json={"action_item": {"id": "x", "status": "Incomplete"}})
    )
    _client().set_action_item_completed("x", False)
    assert json.loads(route.calls[0].request.read()) == {"completed": False}


@respx.mock
def test_archive_action_item():
    route = respx.post("https://test.fellow.app/api/v1/action_item/x/archive").mock(
        return_value=Response(200, json={"action_item": {"id": "x", "status": "Archived"}})
    )
    result = _client().archive_action_item("x")
    assert result["status"] == "Archived"
    assert json.loads(route.calls[0].request.read()) == {}


def test_rejects_unknown_action_item_order():
    with pytest.raises(ValueError, match="order_by"):
        list(_client().list_action_items(order_by="alphabetical"))
