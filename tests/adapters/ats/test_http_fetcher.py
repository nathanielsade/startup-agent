import httpx

from startup_agent.adapters.ats.http_fetcher import HttpJsonFetcher


def test_fetcher_returns_parsed_json():
    def handler(request):
        return httpx.Response(200, json={"ok": True})
    client = httpx.Client(transport=httpx.MockTransport(handler))
    fetch = HttpJsonFetcher(client=client, backoff=0.0)
    assert fetch("https://example.test/api")["ok"] is True


def test_fetcher_retries_then_succeeds():
    calls = {"n": 0}
    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(500)
        return httpx.Response(200, json={"ok": True})
    client = httpx.Client(transport=httpx.MockTransport(handler))
    fetch = HttpJsonFetcher(client=client, retries=3, backoff=0.0)
    assert fetch("https://example.test/api")["ok"] is True
    assert calls["n"] == 3


def test_fetcher_raises_after_exhausting_retries():
    def handler(request):
        return httpx.Response(503)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    fetch = HttpJsonFetcher(client=client, retries=2, backoff=0.0)
    import pytest
    with pytest.raises(httpx.HTTPError):
        fetch("https://example.test/api")
