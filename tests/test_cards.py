import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from cards42 import api, profile, render, service
from cards42.themes import THEMES

USER = json.loads((Path(__file__).parent / "fixtures" / "user.json").read_text())
XMLNS = "http://www.w3.org/2000/svg"


def card(theme, **kw):
    return render.render(profile.from_api(USER, **kw), THEMES[theme])


def test_twelve_themes():
    assert len(THEMES) == 12


@pytest.mark.parametrize("name", sorted(THEMES))
def test_theme_renders_valid_small_self_contained_svg(name):
    svg = card(name)
    root = ET.fromstring(svg)  # well-formed
    assert root.tag == f"{{{XMLNS}}}svg"
    assert len(svg) < 40_000
    assert "http" not in svg.replace(XMLNS, "").replace("http://www.w3.org/1999/xlink", "")  # no external refs
    assert "level 8 - 42%" in svg and "Madrid" in svg and "42cursus" in svg and "Learner" in svg


def test_render_is_deterministic():
    assert card("binary") == card("binary")


def test_profile_picks_main_cursus_and_primary_campus():
    p = profile.from_api(USER)
    assert (p.cursus, p.grade, p.level, p.percent, p.campus) == ("42cursus", "Learner", 8, 42, "Madrid")


def test_profile_edge_cases():
    p = profile.from_api({"login": "x", "cursus_users": None, "campus": None})
    assert (p.level, p.percent, p.cursus, p.grade, p.campus) == (0, 0, "-", "-", "-")
    p = profile.from_api({"login": "x", "cursus_users": [{"level": 8.996, "grade": None, "cursus": {"name": "c"}}]})
    assert (p.level, p.percent, p.grade) == (8, 99, "-")  # never shows 100%


def test_text_is_escaped():
    p = profile.Profile(login="a", campus="<script>alert(1)</script>", cursus="a&b", grade='"x"')
    svg = render.render(p, THEMES["black"])
    ET.fromstring(svg)
    assert "<script>" not in svg


def test_avatar_embedded_and_placeholder():
    assert "data:image/png;base64," in card("black", avatar=("image/png", b"\x89PNG"))
    assert ">S</text>" in card("black")  # placeholder initial


def test_profile_has_no_pii_fields():
    assert not {"email", "name", "displayname", "phone"} & set(profile.Profile.__dataclass_fields__)


@pytest.mark.parametrize("bad", ["", "../x", "a b", "a/b", "A" * 31, "-x", "x?y", "é"])
def test_invalid_login_rejected_before_api(bad, monkeypatch):
    monkeypatch.setattr(api, "fetch_user", lambda l: pytest.fail("API must not be called"))
    assert service.respond(bad)[0] == 400


def test_unknown_theme_400():
    assert service.respond("student", "nope")[0] == 400


def test_respond_ok_and_cache(monkeypatch):
    calls = []
    monkeypatch.setattr(api, "fetch_user", lambda l: calls.append(l) or USER)
    monkeypatch.setattr(api, "fetch_avatar", lambda u: None)
    service._cache.clear()
    for t in ("black", "water"):  # two themes, one login -> one API call
        status, ctype, body, cache = service.respond("Student", t)
        assert (status, ctype, cache) == (200, "image/svg+xml", 3600)
        ET.fromstring(body)
    assert calls == ["student"]


@pytest.mark.parametrize("exc,title", [(api.NotFound, "Unknown login"), (api.RateLimited, "Busy"), (api.ApiError, "Unavailable")])
def test_api_errors_become_200_cards(exc, title, monkeypatch):
    def boom(l):
        raise exc("x")
    monkeypatch.setattr(api, "fetch_user", boom)
    service._cache.clear()
    status, ctype, body, _ = service.respond("student")
    assert status == 200 and ctype == "image/svg+xml" and title in body
    ET.fromstring(body)


def test_avatar_host_whitelist(monkeypatch):
    monkeypatch.setattr(api, "_open", lambda *a, **k: pytest.fail("must not fetch"))
    for url in ("http://cdn.intra.42.fr/a.jpg", "https://evil.example/a.jpg", "https://42.fr.evil.com/a.jpg"):
        assert api.fetch_avatar(url) is None


def _http_error(code, retry_after="0"):
    import email.message
    import urllib.error
    h = email.message.Message()
    h["Retry-After"] = retry_after
    return urllib.error.HTTPError("http://x", code, "x", h, None)


def test_429_is_retried_then_succeeds(monkeypatch):
    import urllib.request
    calls = []

    def fake(req, timeout=8):
        calls.append(1)
        if len(calls) < 3:
            raise _http_error(429)
        return "response"
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    monkeypatch.setattr(api.time, "sleep", lambda s: None)
    assert api._open(urllib.request.Request("http://x")) == "response"
    assert len(calls) == 3


def test_429_gives_up_after_retries(monkeypatch):
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=8: (_ for _ in ()).throw(_http_error(429)))
    monkeypatch.setattr(api.time, "sleep", lambda s: None)
    with pytest.raises(api.RateLimited):
        api._open(urllib.request.Request("http://x"))


@pytest.fixture
def fake_store(monkeypatch):
    from cards42 import store
    data = {}
    monkeypatch.setattr(store, "get", lambda k: data.get(k))
    monkeypatch.setattr(store, "set", lambda k, v, ttl: data.__setitem__(k, v))
    service._cache.clear()
    return data


def test_shared_cache_avoids_api_across_instances(fake_store, monkeypatch):
    calls = []
    monkeypatch.setattr(api, "fetch_user", lambda l: calls.append(l) or USER)
    monkeypatch.setattr(api, "fetch_avatar", lambda u: ("image/png", b"\x89PNG"))
    first = service.get_profile("student")
    service._cache.clear()  # simulate a different cold instance: only the shared store remains
    second = service.get_profile("student")
    assert calls == ["student"] and second == first and second.avatar == ("image/png", b"\x89PNG")
    assert not any(w in json.dumps(list(fake_store.values())) for w in ("email", "phone", "displayname"))


def test_unknown_login_is_remembered(fake_store, monkeypatch):
    calls = []

    def nf(l):
        calls.append(l)
        raise api.NotFound(l)
    monkeypatch.setattr(api, "fetch_user", nf)
    for _ in range(3):
        service._cache.clear()
        with pytest.raises(api.NotFound):
            service.get_profile("nobody")
    assert calls == ["nobody"]  # one API call, then negative-cached


def test_corrupt_shared_entry_falls_back_to_api(fake_store, monkeypatch):
    fake_store["42cards:profile:v1:student"] = "{not json"
    monkeypatch.setattr(api, "fetch_user", lambda l: USER)
    monkeypatch.setattr(api, "fetch_avatar", lambda u: None)
    assert service.get_profile("student").level == 8


def test_store_is_best_effort(monkeypatch):
    from cards42 import store
    monkeypatch.delenv("KV_REST_API_URL", raising=False)
    monkeypatch.delenv("UPSTASH_REDIS_REST_URL", raising=False)
    assert store.get("k") is None and store.set("k", "v", 1) is None  # unconfigured: silent no-op
    monkeypatch.setenv("KV_REST_API_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("KV_REST_API_TOKEN", "t")
    assert store.get("k") is None  # unreachable: silent miss


def test_theme_all_is_one_lookup_and_all_valid(fake_store, monkeypatch):
    calls = []
    monkeypatch.setattr(api, "fetch_user", lambda l: calls.append(l) or USER)
    monkeypatch.setattr(api, "fetch_avatar", lambda u: None)
    status, ctype, body, cache = service.respond("student", "all")
    cards = json.loads(body)
    assert (status, ctype, cache) == (200, "application/json", 3600)
    assert sorted(cards) == sorted(THEMES) and calls == ["student"]
    for svg in cards.values():
        ET.fromstring(svg)


def test_theme_all_unknown_login_gives_error_cards(fake_store, monkeypatch):
    def nf(l):
        raise api.NotFound(l)
    monkeypatch.setattr(api, "fetch_user", nf)
    status, _, body, cache = service.respond("nobody", "all")
    cards = json.loads(body)
    assert status == 200 and len(cards) == 12 and cache == 600
    assert all("Unknown login" in svg for svg in cards.values())
