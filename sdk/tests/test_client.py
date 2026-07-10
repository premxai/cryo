"""Unit tests for CryoClient over httpx MockTransport (no network)."""

import json

import httpx
import pytest
from cryo_search import CryoClient, CryoError

SEARCH_BODY = {
    "results": [
        {
            "id": "doc1",
            "url": "https://example.com/2019/essay",
            "title": "Essay",
            "text": "snippet",
            "score": 0.9,
            "published_year": 2019,
            "domain": "example.com",
            "content_type": "blog",
            "human_score": 0.91,
            "cryo_certified": True,
        }
    ],
    "total": 1,
    "search_time_ms": 12,
    "request_id": "r1",
}

ANSWER_BODY = {
    "answer": "The old web was personal [1].",
    "citations": [
        {
            "index": 1,
            "id": "doc1",
            "url": "https://example.com/2019/essay",
            "archive_url": "https://web.archive.org/web/20190101/https://example.com/2019/essay",
            "timestamp": "20190101120000",
            "human_score": 0.91,
            "cryo_certified": True,
        }
    ],
    "model": "claude-test",
    "cached": False,
}


def _client(handler) -> CryoClient:
    return CryoClient(
        api_key="cryo_sk_test",
        base_url="https://api.test",
        transport=httpx.MockTransport(handler),
        max_retries=1,
    )


def test_search_parses_results_and_sends_auth():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=SEARCH_BODY)

    results = _client(handler).search("old web", num_results=3, domain="example.com")
    assert captured["auth"] == "Bearer cryo_sk_test"
    assert captured["body"]["num_results"] == 3
    assert captured["body"]["domain"] == "example.com"
    assert results[0].cryo_certified is True
    assert results[0].human_score == 0.91


def test_answer_parses_citations():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=ANSWER_BODY)

    result = _client(handler).answer("what was the old web like?")
    assert result.answer.startswith("The old web")
    assert result.citations[0].archive_url.startswith("https://web.archive.org")


def test_error_envelope_raises_cryo_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"error": {"type": "invalid_api_key", "message": "bad key", "request_id": "r"}},
        )

    with pytest.raises(CryoError) as exc:
        _client(handler).search("x")
    assert exc.value.status_code == 401
    assert exc.value.type == "invalid_api_key"


def test_retry_on_429_honors_retry_after(monkeypatch):
    calls = {"n": 0}
    sleeps = []
    monkeypatch.setattr("cryo_search.client.time.sleep", lambda s: sleeps.append(s))

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "3"},
                json={"error": {"type": "rate_limited", "message": "slow down", "request_id": "r"}},
            )
        return httpx.Response(200, json=SEARCH_BODY)

    results = _client(handler).search("retry me")
    assert calls["n"] == 2
    assert sleeps == [3.0]
    assert len(results) == 1


def test_list_domain_and_usage_shapes():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/list-domain":
            return httpx.Response(
                200,
                json={
                    "domain": "example.com",
                    "pages": [
                        {
                            "url": "https://example.com/a.html",
                            "timestamp": "20190101000000",
                            "in_corpus": True,
                        }
                    ],
                    "total": 1,
                    "request_id": "r",
                },
            )
        return httpx.Response(
            200,
            json={
                "month": "2026-07",
                "quota": 1000,
                "used": 10,
                "remaining": 990,
                "by_endpoint": {"search": 10},
            },
        )

    client = _client(handler)
    pages = client.list_domain("example.com")
    assert pages[0].in_corpus is True
    usage = client.usage()
    assert usage.remaining == 990
