"""Optional shared cache over Upstash/Vercel-KV's REST API (stdlib only). Never raises: no store -> cache miss."""
import json
import os
import urllib.request


def _cfg():
    url = os.environ.get("KV_REST_API_URL") or os.environ.get("UPSTASH_REDIS_REST_URL")
    token = os.environ.get("KV_REST_API_TOKEN") or os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    return (url.rstrip("/"), token) if url and token else None


def _cmd(*args):
    cfg = _cfg()
    if not cfg:
        return None
    req = urllib.request.Request(
        cfg[0], data=json.dumps(args).encode(),
        headers={"Authorization": f"Bearer {cfg[1]}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=2) as r:
            return json.load(r).get("result")
    except Exception:  # cache is best-effort: any failure just means "not cached"
        return None


def get(key):
    return _cmd("GET", key)


def set(key, value, ttl):
    _cmd("SET", key, value, "EX", ttl)
