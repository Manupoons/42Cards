import json
import sys
import threading
import urllib.request
from http.server import HTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api.card import handler  # noqa: E402
from cards42 import api, service  # noqa: E402

USER = json.loads((Path(__file__).parent / "fixtures" / "user.json").read_text())


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setattr(api, "fetch_user", lambda l: USER)
    monkeypatch.setattr(api, "fetch_avatar", lambda u: None)
    service._cache.clear()
    srv = HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def get(url):
    try:
        return urllib.request.urlopen(url)
    except urllib.error.HTTPError as e:
        return e


def test_card_headers(server):
    r = get(f"{server}/?login=student&theme=water")
    assert r.status == 200 and r.headers["Content-Type"].startswith("image/svg+xml")
    assert "s-maxage=3600" in r.headers["Cache-Control"]
    assert "default-src 'none'" in r.headers["Content-Security-Policy"]
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert b"level 8 - 42%" in r.read()


def test_bad_input_is_400_and_not_cached(server):
    for q in ("login=../etc", "login=student&theme=nope", ""):
        r = get(f"{server}/?{q}")
        assert r.status == 400 and r.headers["Cache-Control"] == "no-store"
