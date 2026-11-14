"""The demo video's script: what is said, what is shown, and when.

The video must be at most two minutes (the Junction guide). Every spoken number is on a slide
or in a caption card with its source in `data.py`, `viewer/traverse_story.py` or
`docs/demo-video/README.md`.

A shot is one page and a list of beats. A beat may speak a line (`vo`, starting `vo_at` seconds
in), run a snippet in the page when it starts (`js`) or at a time inside it (`at`), and ends
after `min` seconds and after its line (plus `pad`), or, with `until`, as soon after that as
the page says so. A line marked `over` runs on over the beats that follow. 3D shots drive the
real demo page through `window.LIGHTLAG_TRAVERSE_APP` (`A` in the snippets); drawn shots are
scenes of `film.html`.

Pictures are timed to the words: `Words.at(line, phrase)` is the moment the voice starts to say
`phrase`, as the voice model reports it (`build/voice/<line>.words.json`).
"""

from __future__ import annotations

from typing import Any, Dict, List

VOICE = {"voice": "af_heart", "speed": 1.12}
LIMIT_SECONDS = 119.0

# What the narrator says. Numbers are written out so the voice reads them as intended.
LINES: Dict[str, str] = {
    "a1": "Thirteen metres from home, carrying twenty-one samples, this rover's battery runs flat. "
          "Its autopilot was written by Claude Opus. Score for this site: zero.",
    "b1": "This is Light Lag Traverse, a reinforcement learning environment. An agent drives a rover across Mars-like "
          "ground, and every command lands three ticks late. The sun charges the battery; driving drains it. "
          "More targets than a day allows, three sites in a row, no reset. Every rule is public.",
    "c1": "Claude doesn't fail at coding. Within minutes, it writes a real autopilot. "
          "It fails at planning a whole day: the route, the battery, the way home.",
    "c2": "Here, at nine percent battery, our reference waits for the sun.",
    "c3": "Four ticks later, Claude's rover drives its battery to zero. Waiting six ticks would have brought it home.",
    "q1": "Claude's own report: the planner only counted time. Its program played all three sites in under a minute, "
          "before Claude checked a single result.",
    "r1": "The reference is a planner, not a model. It tracks the rover through the delay, learns how each terrain slips, "
          "and prices every leg of its route against the sun. It is always home before the day ends.",
    "s1": "Through Harbor and Open Code, the reference scores zero point four eight. Seven Claude runs, across Opus, "
          "Sonnet and Haiku, all score below zero point three. Three lost a rover. Doing nothing scores zero.",
    "m1": "Was that luck? On Modal, we replayed six of Claude's programs on three hundred fresh worlds. "
          "The reference won at least two hundred eighty-eight times, and never lost a rover.",
    "m2": "Also on Modal, a small policy trained from scratch improves from zero point zero nine to zero point three eight "
          "in development, still short of a greedy controller and the reference.",
    "e1": "One command reruns it all, and a live demo on Modal plays any world you pick. Can your agent make it home?",
}

# The same lines as they should read in subtitles: the same sentences and commas, figures as figures.
SUBTITLES: Dict[str, str] = {
    "a1": "Thirteen metres from home, carrying 21 samples, this rover's battery runs flat. "
          "Its autopilot was written by Claude Opus. Score for this site: zero.",
    "b1": "This is Lightlag Traverse, a reinforcement learning environment. An agent drives a rover across Mars-like "
          "ground, and every command lands three ticks late. The sun charges the battery; driving drains it. "
          "More targets than a day allows, three sites in a row, no reset. Every rule is public.",
    "c1": LINES["c1"], "c2": "Here, at 9% battery, our reference waits for the sun.", "c3": LINES["c3"], "q1": LINES["q1"],
    "r1": LINES["r1"],
    "s1": "Through Harbor and OpenCode, the reference scores 0.48. Seven Claude runs, across Opus, Sonnet and Haiku, "
          "all score below 0.3. Three lost a rover. Doing nothing scores zero.",
    "m1": "Was that luck? On Modal, we replayed six of Claude's programs on 300 fresh worlds. "
          "The reference won at least 288 times, and never lost a rover.",
    "m2": "Also on Modal, a small policy trained from scratch improves from 0.09 to 0.38 "
          "in development, still short of a greedy controller and the reference.",
    "e1": LINES["e1"],
}

LIVE_URL = "kristjansolvi03--lightlag-traverse-live-web.us-east.modal.run"

# Story mode takes this long from letting go of the reference's moment at site 3 (tick 93) to stopping on
# the Claude rover that runs flat (tick 97): four ticks at its slow speeds. Measured on the recording.
TRAVEL = 2.05


class Words:
    """When each word of each line is spoken, in seconds from the start of the line."""

    def __init__(self, words: Dict[str, List[Dict[str, Any]]]) -> None:
        self.words = words

    def at(self, line: str, phrase: str) -> float:
        text, index, seen = LINES[line], LINES[line].index(phrase), 0
        for word in self.words[line]:
            if seen >= index and word["t0"] is not None:
                return float(word["t0"])
            seen += len(word["w"]) + (1 if word["space"] else 0)
        raise ValueError("{!r} is not spoken in line {}: {!r}".format(phrase, line, text))


def shots(durations: Dict[str, float], words: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    say = Words(words)
    # seconds into its beat at which a phrase of the line is said, when the line starts `start` seconds in
    b = lambda phrase, lead=0.0: round(0.3 + say.at("b1", phrase) + lead, 2)          # noqa: E731  the task shot
    r = lambda phrase: round(0.4 + say.at("r1", phrase) - 0.1, 2)                     # noqa: E731  the reference slide
    flat = 0.5 + say.at("a1", "flat")                  # the cold open: the battery is flat on the word
    zero = say.at("c3", "zero")                        # why: the second battery is flat on the word
    return [
        # 1. Cold open: the judged run, site 1. Ride behind a rover whose autopilot Claude Opus wrote, at three
        #    ticks a second, timed so that tick 409, where its battery runs out 13 m from the lander, falls on "flat".
        {"name": "cold", "page": "campaign", "site": 1, "fade_in": 0.6, "beats": [
            {"vo": "a1", "vo_at": 0.5, "over": True, "until": "A.state.t >= 409",
             "js": "A.showTitle(false); A.HOLD.lost = 999; A.follow('campaign-agent-opus-2'); A.seek(%.2f); "
                   "A.setCam('chase'); A.view.k = 1; A.view.snap = true; A.setSpeed(2); A.setPlaying(true);" % (409 - 3 * flat),
             # for a viewer with the sound off: what this is, until the page's own card takes over
             "overlay": [
                 {"kind": "caption", "side": "left", "from": 0.7, "to": round(0.5 + say.at("a1", "this rover's") - 0.15, 2), "text": "HEADING HOME WITH 21 SAMPLES"},
                 {"kind": "caption", "side": "left", "from": round(0.5 + say.at("a1", "this rover's"), 2), "to": round(flat - 0.05, 2), "text": "BATTERY NEARLY EMPTY"},
             ]},
            # it stands there; then the camera rises and story mode shows how close home was. The mini-map goes
            # now, so that it is not still fading under the card that comes up in its corner.
            {"min": 0.9, "thump": 0.0, "js": "A.setPlaying(false); A.seek(409); document.getElementById('mini').style.opacity = '0';"},
            {"min": 3.0, "pad": 0.7, "js": "A.startStory();"},
        ]},
        # 2. The task: the first site from its first tick, the title over it, one caption per rule.
        {"name": "task", "page": "campaign", "site": 1, "chapter": "THE TASK", "beats": [
            {"vo": "b1", "vo_at": 0.3, "pad": 0.3,
             "js": "A.showTitle(false); A.seek(0); A.setCam('map'); A.setSpeed(4); A.setPlaying(true);",
             "overlay": [
                 {"kind": "title", "from": 0.0, "to": b("An agent drives", -0.1)},
                 {"kind": "caption", "from": b("An agent drives"), "to": b("and every command", -0.35), "text": "600 × 400 M OF CRATERS, SAND AND ROCK"},
                 # the two captions of the ride sit left of the mini-map the chase camera shows
                 {"kind": "caption", "side": "left", "from": b("and every command"), "to": b("The sun charges", -0.05), "text": "EVERY COMMAND LANDS 3 TICKS LATE"},
                 {"kind": "caption", "side": "left", "from": b("The sun charges"), "to": b("More targets", -0.25), "text": "BATTERY · SUN CHARGES, DRIVING DRAINS"},
                 {"kind": "caption", "from": b("More targets"), "to": b("three sites", -0.05), "text": "46 TARGETS · MORE THAN ONE DAY ALLOWS"},
                 {"kind": "caption", "from": b("three sites"), "to": b("Every rule", -0.05), "text": "3 SITES IN A ROW · NO RESET"},
                 {"kind": "caption", "from": b("Every rule"), "to": 99, "text": "EVERY RULE AND FORMULA IS PUBLIC · FIVE TOOLS"},
             ],
             "at": [
                 # ride behind a rover while the delay and the battery are explained: the ring it trails is its
                 # last position fix, 3 ticks old. The camera takes 1.1 s to fly in or out; the mini-map comes
                 # and goes half way through.
                 {"t": b("and every command", -0.9), "js": "A.setSpeed(2); A.setCam('chase');"},
                 {"t": b("More targets", -0.75), "js": "A.setCam('map'); A.setSpeed(4);"},
             ]},
        ]},
        # 3. Why Claude struggles: site 3. The reference waits for the sun at 9%; four ticks later a Claude rover
        #    runs flat. "Four ticks later" is said while those four ticks pass, and "zero" lands on the stop.
        {"name": "why", "page": "campaign", "site": 3, "chapter": "WHY CLAUDE STRUGGLES", "beats": [
            {"vo": "c1", "vo_at": 0.3, "pad": 0.1,
             "js": "A.showTitle(false); A.HOLD.ref_wait = 999; A.HOLD.lost = 999; A.seek(46); A.setCam('map'); A.setSpeed(4); A.setPlaying(true);",
             "at": [{"t": 1.4, "js": "A.startStory();"}],
             # the claim in writing; gone before the page's card for the reference comes up in the same place
             "overlay": [
                 {"kind": "caption", "from": 0.45, "to": round(0.3 + say.at("c1", "It fails") - 0.15, 2), "text": "CLAUDE WRITES A REAL AUTOPILOT WITHIN MINUTES"},
                 {"kind": "caption", "from": round(0.3 + say.at("c1", "It fails"), 2), "to": round(0.3 + durations["c1"] - 0.05, 2), "text": "IT FAILS AT PLANNING THE DAY: ROUTE, BATTERY, WAY HOME"},
             ],
             "until": "!!(A.story.active && A.story.active.kind === 'ref_wait')"},
            {"vo": "c2", "vo_at": 0.3, "pad": 0.35},
            {"vo": "c3", "vo_at": 0.0, "over": True, "at": [{"t": round(max(0.0, zero - TRAVEL), 2), "js": "A.story.hold = 0;"}],
             "until": "!!(A.story.active && A.story.active.kind === 'lost')"},
            {"min": 2.0, "pad": 1.0, "thump": 0.0},
        ]},
        # 4. Claude's own words about that failure.
        {"name": "quote", "page": "film", "scene": "quote", "beats": [{"vo": "q1", "vo_at": 0.4, "pad": 0.6}]},
        # 5. The reference.
        {"name": "reference", "page": "film", "scene": "reference", "beats": [
            {"vo": "r1", "vo_at": 0.4, "pad": 0.7,
             "cues": [r("It tracks"), r("learns how"), r("and prices"), r("It is always")]},
        ]},
        # 6. Results on the campaign.
        {"name": "results", "page": "film", "scene": "results", "beats": [
            {"vo": "s1", "vo_at": 0.4, "pad": 0.7, "min": 7.0, "cues": [round(0.4 + say.at("s1", "Doing nothing") - 0.15, 2)]}]},
        # 7. Modal: the 300-world comparison, then the learned policy.
        {"name": "farm", "page": "film", "scene": "farm", "beats": [{"vo": "m1", "vo_at": 0.4, "pad": 0.7, "min": 9.0}]},
        {"name": "learning", "page": "film", "scene": "learning", "beats": [{"vo": "m2", "vo_at": 0.4, "pad": 0.6}]},
        # 8. The end card.
        {"name": "end", "page": "film", "scene": "end", "fade_out": 0.8, "beats": [
            {"vo": "e1", "vo_at": 0.5, "pad": 1.4, "min": 6.0,
             "cues": [round(0.5 + say.at("e1", "and a live demo") - 0.1, 2), round(0.5 + say.at("e1", "Can your agent") - 0.15, 2)]}]},
    ]
