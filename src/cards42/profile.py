"""Public-only profile model. Email and real name are deliberately not represented."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    login: str
    campus: str = "-"
    cursus: str = "-"
    grade: str = "-"
    level: int = 0
    percent: int = 0
    kind: str = "student"
    avatar: tuple | None = None  # (mime, bytes)


def avatar_url(user):
    img = user.get("image") or {}
    return (img.get("versions") or {}).get("medium") or img.get("link") or user.get("image_url")


def _main_cursus(user):
    cu = [c for c in user.get("cursus_users") or [] if isinstance(c, dict)]
    main = [c for c in cu if (c.get("cursus") or {}).get("slug") == "42cursus"]
    return (main or sorted(cu, key=lambda c: c.get("level") or 0, reverse=True) or [None])[0]


def _campus(user):
    campuses = {c.get("id"): c.get("name") for c in user.get("campus") or [] if isinstance(c, dict)}
    for cu in user.get("campus_users") or []:
        if cu.get("is_primary") and cu.get("campus_id") in campuses:
            return campuses[cu["campus_id"]]
    return next(iter(campuses.values()), None) or "-"


def from_api(user, avatar=None):
    c = _main_cursus(user)
    level = float((c or {}).get("level") or 0)
    return Profile(
        login=user["login"],
        campus=_campus(user),
        cursus=((c or {}).get("cursus") or {}).get("name") or "-",
        grade=(c or {}).get("grade") or "-",
        level=int(level),
        percent=min(99, round((level - int(level)) * 100)),
        kind=user.get("kind") or "student",
        avatar=avatar,
    )
