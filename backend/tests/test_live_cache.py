from app.services.live_cache import get_cached, set_cached


def test_cache_hit_and_expiry(monkeypatch):
    set_cached("k", {"ok": True})
    assert get_cached("k", ttl=10) == {"ok": True}
    assert get_cached("k", ttl=0) is None
