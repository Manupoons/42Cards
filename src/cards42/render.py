"""Profile + theme -> pure-SVG card (450x275). No HTML/foreignObject, no external refs."""
import base64
import random
from xml.sax.saxutils import escape

from .profile import Profile

W, H = 450, 275
FONT = "Segoe UI,Helvetica,Arial,sans-serif"
CSS = (
    "@keyframes d{from{opacity:0;transform:translateY(-12px)}to{opacity:1;transform:none}}"
    "@keyframes u{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}"
    "@keyframes g{from{transform:scaleX(0)}to{transform:scaleX(1)}}"
    ".d{animation:d .8s ease both}.u{animation:u .8s ease both}"
    ".g{transform-box:fill-box;transform-origin:left;animation:g .9s ease both}"
    "@media(prefers-reduced-motion:reduce){*{animation:none!important}}"
)


def _wave(y, amp, color, op):
    return (f'<path d="M0 {y}C75 {y - amp} 150 {y + amp} 225 {y}S375 {y - amp} 450 {y}V{H}H0Z" '
            f'fill="{color}" opacity="{op}"/>')


def _art(theme):
    name = theme.get("art")
    if not name:
        return ""
    if name in ("binary", "greenbinary"):
        rnd = random.Random(name)  # deterministic: same card every render
        rows = "".join(
            f'<text x="0" y="{14 + i * 14.5:.1f}" textLength="{W}" lengthAdjust="spacing">'
            f'{"".join(rnd.choice("01") for _ in range(54))}</text>' for i in range(19))
        art = f'<g font-family="monospace" font-size="13" fill="{theme["art_color"]}" opacity=".16">{rows}</g>'
    elif name == "water":
        art = "".join(_wave(y, 22, c, .35) for y, c in ((150, "#4aa3df"), (185, "#2f7fc1"), (222, "#1b5a9b")))
    elif name == "colorfulwaves":
        art = "".join(_wave(y, 24, c, .3) for y, c in
                      ((120, "#ff6b6b"), (160, "#feca57"), (200, "#48dbfb"), (240, "#1dd1a1")))
    elif name == "levi":
        art = ('<defs><pattern id="st" width="14" height="14" patternUnits="userSpaceOnUse" '
               'patternTransform="rotate(35)"><rect width="5" height="14" fill="#fff" opacity=".06"/></pattern></defs>'
               f'<rect width="{W}" height="{H}" fill="url(#st)"/>'
               f'<polygon points="300,0 450,0 450,110" fill="{theme["accent"]}" opacity=".18"/>')
    else:
        return ""
    # dark veil keeps text readable on busy backgrounds
    return art + f'<rect width="{W}" height="{H}" fill="#000" opacity=".28"/>'


def _frame(theme, inner):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}" font-weight="700" fill="{theme["text"]}">'
        f'<style>{CSS}</style>'
        f'<clipPath id="bg"><rect width="{W}" height="{H}" rx="10"/></clipPath>'
        f'<g clip-path="url(#bg)"><rect width="{W}" height="{H}" fill="{theme["bg"]}"/>{_art(theme)}</g>'
        f'{inner}</svg>'
    )


def _avatar(p, theme):
    if p.avatar:
        mime, data = p.avatar
        href = f"data:{mime};base64,{base64.b64encode(data).decode()}"
        return ('<clipPath id="av"><rect x="20" y="58" width="75" height="75" rx="10"/></clipPath>'
                f'<image x="20" y="58" width="75" height="75" preserveAspectRatio="xMidYMid slice" '
                f'clip-path="url(#av)" xlink:href="{href}"/>')
    return (f'<rect x="20" y="58" width="75" height="75" rx="10" fill="{theme["accent"]}" opacity=".3"/>'
            f'<text x="57.5" y="106" font-size="34" text-anchor="middle">{escape(p.login[:1].upper())}</text>')


def render(p: Profile, theme: dict) -> str:
    rows = (("campus:", p.campus), ("cursus:", p.cursus), ("grade:", p.grade))
    table = "".join(
        f'<text x="115" y="{76 + i * 24}" font-size="15">{k}</text>'
        f'<text x="185" y="{76 + i * 24}" font-size="15" fill="{theme["accent"]}">{escape(v[:24])}</text>'
        for i, (k, v) in enumerate(rows))
    fill_w = round(410 * p.percent / 100)
    tag = escape(p.kind.upper()[:12])
    tag_w = 9 * len(tag) + 16
    inner = (
        f'<text class="d" x="20" y="38" font-size="18">{escape(p.login)}\'s Profile</text>'
        f'{_avatar(p, theme)}{table}'
        f'<clipPath id="bar"><rect x="20" y="152" width="410" height="38" rx="10"/></clipPath>'
        f'<rect x="20" y="152" width="410" height="38" rx="10" fill="{theme["track"]}"/>'
        f'<rect class="g" x="20" y="152" width="{fill_w}" height="38" fill="{theme["accent"]}" clip-path="url(#bar)"/>'
        f'<text x="225" y="177" font-size="15" text-anchor="middle" stroke="#000" stroke-opacity=".45" '
        f'stroke-width="3" paint-order="stroke">level {p.level} - {p.percent}%</text>'
        f'<g class="u"><rect x="20" y="212" width="{tag_w}" height="24" rx="5" fill="#e0e5e9"/>'
        f'<text x="{20 + tag_w / 2}" y="229" font-size="13" text-anchor="middle" fill="#000">{tag}</text>'
        f'<text x="430" y="230" font-size="14" text-anchor="end">42 {escape(p.campus.upper()[:18])}</text></g>'
    )
    return _frame(theme, inner)


def render_message(theme: dict, title: str, text: str) -> str:
    inner = (f'<text x="20" y="38" font-size="18">{escape(title)}</text>'
             f'<text x="20" y="90" font-size="15" fill="{theme["accent"]}">{escape(text)}</text>')
    return _frame(theme, inner)
