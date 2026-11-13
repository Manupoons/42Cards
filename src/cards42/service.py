"""Request logic shared by the Vercel handler and the CLI. Returns (status, content_type, body, cache_seconds)."""
import re
import sys
import time

from . import api, profile, render
from .themes import DEFAULT, THEMES

LOGIN_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,29}$")  # validated before it ever reaches the API URL
SVG = "image/svg+xml"
TTL, MAX_CACHE = 600, 256
_cache = {}  # login -> (expires, Profile); saves API calls when someone tries several themes


def get_profile(login):
    hit = _cache.get(login)
    if hit and hit[0] > time.time():
        return hit[1]
    user = api.fetch_user(login)
    url = profile.avatar_url(user)
    p = profile.from_api(user, api.fetch_avatar(url) if url else None)
    if len(_cache) >= MAX_CACHE:
        _cache.clear()
    _cache[login] = (time.time() + TTL, p)
    return p


def respond(login, theme_name=None):
    login = (login or "").strip().lower()
    theme_name = theme_name or DEFAULT
    if not LOGIN_RE.match(login):
        return 400, "text/plain", "invalid login", 0
    if theme_name not in THEMES:
        return 400, "text/plain", "unknown theme. available: " + ", ".join(sorted(THEMES)), 0
    theme = THEMES[theme_name]
    # Errors are 200 SVG cards (an image in a README must not render as a broken image).
    try:
        return 200, SVG, render.render(get_profile(login), theme), 3600
    except api.NotFound:
        return 200, SVG, render.render_message(theme, "Unknown login", f"No 42 user '{login}'"), 600
    except api.RateLimited as e:
        print(f"cards42: rate limited (retry-after={e})", file=sys.stderr)
        return 200, SVG, render.render_message(theme, "Busy", "42 API rate limit, retry soon"), 60
    except api.ApiError as e:
        print(f"cards42: api error: {e}", file=sys.stderr)  # shows in Vercel logs; never includes credentials
        return 200, SVG, render.render_message(theme, "Unavailable", "42 API error, retry soon"), 60
