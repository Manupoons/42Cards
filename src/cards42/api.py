"""Minimal 42 API client (stdlib only): client-credentials token + public user data."""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://api.intra.42.fr"
MAX_AVATAR = 300_000
UA = "42Cards/1.0"  # Cloudflare in front of the 42 API rejects the default Python-urllib agent (error 1010)
IMAGE_TYPES = ("image/jpeg", "image/png", "image/gif", "image/webp")


class ApiError(Exception):
    pass


class NotFound(ApiError):
    pass


class RateLimited(ApiError):
    pass


_token = {"value": None, "exp": 0.0}


def _env(name):
    if os.environ.get(name):
        return os.environ[name]
    f = Path(__file__).resolve().parents[2] / ".env"  # local dev only
    if f.is_file():
        for line in f.read_text().splitlines():
            k, _, v = line.partition("=")
            if k.strip() == name:
                return v.strip().strip("\"'")
    return ""


def _open(req, timeout=8):
    req.add_header("User-Agent", UA)
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise NotFound(req.full_url) from e
        if e.code == 429:
            raise RateLimited(e.headers.get("Retry-After", "")) from e
        raise ApiError(f"HTTP {e.code}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise ApiError(str(e)) from e


def get_token(force=False):
    if not force and _token["value"] and time.time() < _token["exp"] - 60:
        return _token["value"]
    uid, secret = _env("FT_UID"), _env("FT_SECRET")
    if not uid or not secret:
        raise ApiError("FT_UID / FT_SECRET not set")
    body = urllib.parse.urlencode(
        {"grant_type": "client_credentials", "client_id": uid, "client_secret": secret}
    ).encode()
    with _open(urllib.request.Request(f"{BASE}/oauth/token", data=body)) as r:
        d = json.load(r)
    _token["value"] = d["access_token"]
    _token["exp"] = time.time() + d.get("expires_in", 7200)
    return _token["value"]


def fetch_user(login):
    """Raw /v2/users/{login} JSON. `login` must already be validated by the caller."""
    for attempt in (0, 1):
        req = urllib.request.Request(
            f"{BASE}/v2/users/{urllib.parse.quote(login)}",
            headers={"Authorization": f"Bearer {get_token(force=attempt == 1)}"},
        )
        try:
            with _open(req) as r:
                return json.load(r)
        except ApiError as e:
            if str(e) != "HTTP 401" or attempt:  # token expired/revoked: refresh once
                raise


def fetch_avatar(url):
    """(mime, bytes) for an https *.42.fr image, or None. Never raises."""
    try:
        u = urllib.parse.urlparse(url)
        if u.scheme != "https" or not (u.hostname or "").endswith(".42.fr"):
            return None
        with _open(urllib.request.Request(url)) as r:
            mime = r.headers.get_content_type()
            data = r.read(MAX_AVATAR + 1)
        if mime in IMAGE_TYPES and len(data) <= MAX_AVATAR:
            return mime, data
    except ApiError:
        pass
    return None
