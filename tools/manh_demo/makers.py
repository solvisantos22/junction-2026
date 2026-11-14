"""Who made each AI model on screen, and the logo tile that says so at a glance.

A viewer should not have to read a label to know which lab's model is driving a rover. Every
run whose label names a model gets its maker's mark on a small light tile: over the rover in
the top-down shots, on the card that explains a failure, in the standings and beside the model
names on the charts.

The demos to come will show models from Anthropic, Google DeepMind and OpenAI side by side
(Manh, 15 November 2026), so all three are registered here although this cut only has Claude.
To add a maker: one entry in `MAKERS` and its mark in `logos/`.

The marks are the Simple Icons paths (CC0-1.0, https://simpleicons.org, package 16.37.0),
unchanged. The logos themselves are trademarks of their owners and are used only to name the
maker of the model shown.
"""

from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Any, Dict, Optional

HERE = Path(__file__).resolve().parent
LOGOS = HERE / "logos"

# `words` are matched as whole words in a run's label, in lower case; `ink` is the mark's colour
# and `tile` the square it sits on, chosen to stand out from rust-coloured ground.
MAKERS: Dict[str, Dict[str, Any]] = {
    "anthropic": {
        "name": "Anthropic", "family": "Claude", "mark": "claude.svg", "ink": "#D97757", "tile": "#F4F1E8",
        "words": ("claude", "opus", "sonnet", "haiku", "anthropic"),
    },
    "openai": {
        "name": "OpenAI", "family": "GPT", "mark": "openai.svg", "ink": "#0D0D0D", "tile": "#FFFFFF",
        "words": ("openai", "gpt", "chatgpt", "codex", "o1", "o3", "o4"),
    },
    "google-deepmind": {
        "name": "Google DeepMind", "family": "Gemini", "mark": "deepmind.svg", "ink": "#4285F4", "tile": "#FFFFFF",
        "words": ("gemini", "deepmind", "google", "gemma"),
    },
}

# The reference is a planner, not a model: it gets a tile of its own colour and a route, not a logo.
REFERENCE = {"name": "Reference", "family": "Planner", "ink": "#1A120F", "tile": "#FFB224"}
ROUTE = ('<path d="M5 18.5 9.5 9l5 5.5L19 5.5" fill="none" stroke="{ink}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>'
         '<circle cx="5" cy="18.5" r="2.3" fill="{ink}"/><circle cx="19" cy="5.5" r="2.3" fill="{ink}"/>')


def maker_of(label: str) -> Optional[str]:
    """The maker whose model a run label names ("Opus 5.5 · agent 2" -> "anthropic"), or None."""
    words = set(re.findall(r"[a-z]+\d*", label.lower()))
    for key, maker in MAKERS.items():
        if words & set(maker["words"]):
            return key
    return None


def mark_path(maker: str) -> str:
    """The `d` of the maker's mark, on Simple Icons' 24 by 24 grid."""
    svg = (LOGOS / MAKERS[maker]["mark"]).read_text(encoding="utf-8")
    found = re.search(r'<path d="([^"]+)"', svg)
    if not found:
        raise ValueError("no path in {}".format(MAKERS[maker]["mark"]))
    return found.group(1)


def tile_svg(maker: Optional[str], size: int = 96) -> str:
    """A rounded square with the maker's mark on it; `None` is the reference's route tile."""
    spec = MAKERS[maker] if maker else REFERENCE
    inner = ('<path d="{}" fill="{}"/>'.format(mark_path(maker), spec["ink"]) if maker else ROUTE.format(ink=spec["ink"]))
    # the mark keeps a fifth of the tile as margin on every side
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="{s}" height="{s}" viewBox="0 0 40 40">'
            '<rect x="1" y="1" width="38" height="38" rx="8.5" fill="{tile}" stroke="rgba(0,0,0,.55)" stroke-width="1.6"/>'
            '<g transform="translate(8 8)">{inner}</g></svg>').format(s=size, tile=spec["tile"], inner=inner)


def data_url(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def for_page() -> Dict[str, Any]:
    """What the page add-ons need: a tile per maker (and the reference's), and how to name each."""
    tiles = {key: {"name": spec["name"], "family": spec["family"], "tile": data_url(tile_svg(key)),
                   "words": list(spec["words"])} for key, spec in MAKERS.items()}
    tiles["reference"] = {"name": REFERENCE["name"], "family": REFERENCE["family"], "tile": data_url(tile_svg(None)), "words": []}
    return tiles
