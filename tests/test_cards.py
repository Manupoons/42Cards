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
