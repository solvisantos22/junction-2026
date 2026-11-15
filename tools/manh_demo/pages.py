"""The two pages the film is recorded from, as copies made at build time.

Nothing of Kristján's is edited. The demo page (`viewer/traverse-campaign.html`) and the chart
scenes (`tools/demo_video/film.html`) are read, changed in memory in a few named places and
written to this tool's build folder; the add-ons (`tracker.js`, `scenes.js`) then draw on top.
Every change is checked to apply exactly as many times as expected, so if a page moves on in a
way the add-ons do not know, the build stops here instead of recording something half right.

What is changed:

- the demo page's script also hands out its camera, its rovers and a few helpers, so the
  add-on can tell where each rover is on screen;
- both pages put an open-licence typeface in front of their font lists. They ask for
  "DIN Condensed", which only macOS has; on Linux they would fall back to a much wider face
  and the layouts would not hold. Barlow Condensed is the closest free face, Inter stands in
  for the system sans and JetBrains Mono for the system mono (all SIL OFL 1.1, in `fonts/`).
"""

from __future__ import annotations

import base64
import os
import re
from pathlib import Path
from typing import Dict, Tuple

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
FONTS = HERE / "fonts"
CAMPAIGN = REPO / "viewer" / "traverse-campaign.html"
FILM = REPO / "tools" / "demo_video" / "film.html"

DISPLAY = '"Barlow Condensed", '
EXPORT = "window.LIGHTLAG_TRAVERSE_APP = { state, story, view,"
EXPORT_MORE = ("window.LIGHTLAG_TRAVERSE_APP = { THREE, camera, scene, renderer, ACTORS, REF, OTHERS, CFG, DATA, card, "
               "classAt, slopeAt, drawnHeight, P, short, roverParts, state, story, view,")


def swap(text: str, old: str, new: str, times: int, what: str) -> str:
    """Replace `old` by `new`, which must be there exactly `times` times (or, for 0, at least once)."""
    found = text.count(old)
    if found != times and not (times == 0 and found):
        raise SystemExit("manh_demo: expected {!r} {} time(s) in {}, found {}: the page has changed, "
                         "look at tools/manh_demo/pages.py".format(old[:60], times, what, found))
    return text.replace(old, new)


def patch_app(source: str) -> str:
    source = swap(source, EXPORT, EXPORT_MORE, 1, "the demo page's script")
    return swap(source, """const FONT = '"DIN Condensed",""", """const FONT = '""" + DISPLAY + """"DIN Condensed",""", 1, "the demo page's script")


def campaign_page(build: Path) -> Path:
    """The campaign demo page with its script's internals handed out and the film's typefaces."""
    html = CAMPAIGN.read_text(encoding="utf-8")
    block = re.search(r'(<script id="src-app" type="application/octet-stream">)([A-Za-z0-9+/=\s]+)(</script>)', html)
    if not block:
        raise SystemExit("manh_demo: the demo page no longer carries its script as `src-app`")
    app = patch_app(base64.b64decode(block.group(2)).decode("utf-8"))
    html = html[:block.start(2)] + base64.b64encode(app.encode("utf-8")).decode("ascii") + html[block.end(2):]
    html = swap(html, '--display: "DIN Condensed",', '--display: ' + DISPLAY + '"DIN Condensed",', 1, "the demo page's styles")
    # the cards' running text: the system sans on a Mac, Inter here
    html = swap(html, "font-family: ui-sans-serif, system-ui, -apple-system, sans-serif;",
                'font-family: "Inter", ui-sans-serif, system-ui, -apple-system, sans-serif;', 0, "the demo page's styles")
    out = build / "pages" / "traverse-campaign.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


def film_page(build: Path) -> Path:
    """Kristján's chart scenes with the film's typefaces."""
    html = FILM.read_text(encoding="utf-8")
    html = swap(html, """const DIN = '"DIN Condensed",""", """const DIN = '""" + DISPLAY + """"DIN Condensed",""", 1, "film.html")
    html = swap(html, """const SANS = '-apple-system,""", """const SANS = '"Inter", -apple-system,""", 1, "film.html")
    html = swap(html, """const MONO = '"SF Mono",""", """const MONO = '"JetBrains Mono", "SF Mono",""", 1, "film.html")
    # every block of a scene fades in through appear(): it tells the add-on when, so the sounds can be checked against the picture
    html = swap(html, "const appear = (t, at, len = 0.45) => ease((t - at) / len);",
                "const appear = (t, at, len = 0.45) => { if (window.__onset) window.__onset(at); return ease((t - at) / len); };", 1, "film.html")
    out = build / "pages" / "film.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


def overlay_script() -> str:
    """Kristján's film dressing for the demo page (title, captions, chapter chip, fade), with the film's typeface."""
    script = (REPO / "tools" / "demo_video" / "overlay.js").read_text(encoding="utf-8")
    return swap(script, 'font-family: "DIN Condensed",', 'font-family: ' + DISPLAY + '"DIN Condensed",', 1, "overlay.js")


def font_environment(build: Path) -> Dict[str, str]:
    """Environment for the browser: the system's fonts plus this tool's, through a fontconfig file of
    its own, so nothing is installed on the machine."""
    folder = build / "fontconfig"
    (folder / "cache").mkdir(parents=True, exist_ok=True)
    conf = folder / "fonts.conf"
    conf.write_text("""<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <include ignore_missing="yes">/etc/fonts/fonts.conf</include>
  <dir>{fonts}</dir>
  <cachedir>{cache}</cachedir>
</fontconfig>
""".format(fonts=FONTS, cache=folder / "cache"), encoding="utf-8")
    return {**os.environ, "FONTCONFIG_FILE": str(conf)}


def fonts() -> Tuple[str, ...]:
    return tuple(sorted(path.name for path in FONTS.glob("*.ttf")))


def svg_loader() -> str:
    """three.js's own SVG loader (`vendor/SVGLoader.js`, MIT, the version of the three.js in the repository) as the
    body of a function of THREE: its import and export lines are swapped for plain ones, so an add-on can use it
    with the page's own copy of three.js, which is loaded from a blob and cannot be imported by name."""
    source = (HERE / "vendor" / "SVGLoader.js").read_text(encoding="utf-8")
    head = re.match(r"import \{([^}]*)\} from 'three';", source, re.S)
    if not head:
        raise SystemExit("manh_demo: vendor/SVGLoader.js no longer starts with its import from three")
    body = "const {" + head.group(1) + "} = THREE;" + source[head.end():]
    return swap(body, "export { SVGLoader };", "return SVGLoader;", 1, "vendor/SVGLoader.js")
