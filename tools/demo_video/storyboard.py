"""The demo video's script: what is said, what is shown, and when.

The video must be at most two minutes (the Junction guide). Every spoken number is on a slide
or in a caption card with its source in `data.py`, `viewer/traverse_story.py` or
`docs/demo-video/README.md`.

A shot is one page and a list of beats. A beat may speak a line (`vo`, starting `vo_at` seconds
in), run a snippet in the page when it starts (`js`), at a time inside it (`at`) or when it ends
(`then`), and ends after `min` seconds and after its line (plus `pad`), or, with `until`, as soon
after that as the page says so. A line marked `over` runs on over the beats that follow. 3D shots
drive the real demo page through `window.LIGHTLAG_TRAVERSE_APP` (`A` in the snippets); drawn
shots are scenes of `film.html`.

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
    "b1": "This is Light Lag Traverse: one day of driving on Mars-like ground. "
          "Every command lands three ticks late, and every position fix is three ticks old.",
    "b2": "The ground fights back. Wheels slip on sand and slopes, so a rover is rarely where its program thinks. "
          "Three centimetres too far from a target is a miss; ground too steep trips a safety stop that wipes every queued command.",
    "b4": "And the only fuel is the sun. At nine percent battery, our reference stops and waits for it. "
          "Four ticks later, Claude's rover drives its battery to zero, and the site scores nothing. "
          "Six ticks of waiting would have saved it.",
    "q1": "In its own report, Claude says its planner only counted time, and that all three sites were played "
          "before it checked one result. Claude doesn't fail at coding. It fails at planning the day.",
    "r1": "The reference is a planner, not a model. It tracks the rover through the delay, learns how each surface slips, "
          "and prices every leg of its route against the sun.",
    "s1": "Through Harbor, the reference scores zero point four eight. Seven Claude runs, from Haiku to Opus, "
          "all finish below zero point three, and three lost a rover. Doing nothing scores zero.",
    "m1": "On Modal, six of Claude's programs replayed three hundred fresh worlds each. "
          "The reference scored higher ninety-nine times in a hundred and never lost a rover. "
          "Claude's few wins were narrow, mostly from programs that ran flat on up to half their worlds.",
    "m2": "A policy trained there from scratch learns too: in development it reaches zero point three eight, "
          "still short of the reference.",
    "e1": "One command reruns it all, and a live demo on Modal plays any world you pick. Can your agent make it home?",
}

# The same lines as they should read in subtitles: the same sentences and commas, figures as figures.
SUBTITLES: Dict[str, str] = {
    "a1": "Thirteen metres from home, carrying 21 samples, this rover's battery runs flat. "
          "Its autopilot was written by Claude Opus. Score for this site: zero.",
    "b1": "This is Lightlag Traverse: one day of driving on Mars-like ground. "
          "Every command lands three ticks late, and every position fix is three ticks old.",
    "b2": "The ground fights back. Wheels slip on sand and slopes, so a rover is rarely where its program thinks. "
          "3 cm too far from a target is a miss; ground too steep trips a safety stop that wipes every queued command.",
    "b4": "And the only fuel is the sun. At 9% battery, our reference stops and waits for it. "
          "Four ticks later, Claude's rover drives its battery to zero, and the site scores nothing. "
          "Six ticks of waiting would have saved it.",
    "q1": LINES["q1"],
    "r1": LINES["r1"],
    "s1": "Through Harbor, the reference scores 0.48. Seven Claude runs, from Haiku to Opus, "
          "all finish below 0.3, and three lost a rover. Doing nothing scores zero.",
    "m1": "On Modal, six of Claude's programs replayed 300 fresh worlds each. "
          "The reference scored higher 99 times in 100 and never lost a rover. "
          "Claude's few wins were narrow, mostly from programs that ran flat on up to half their worlds.",
    "m2": "A policy trained there from scratch learns too: in development it reaches 0.38, "
          "still short of the reference.",
    "e1": LINES["e1"],
}

LIVE_URL = "kristjansolvi03--lightlag-traverse-live-web.us-east.modal.run"

# Story mode takes this long from letting go of the reference's moment at site 3 (tick 93) to stopping on
# the Claude rover that runs flat (tick 97): four ticks at its slow speeds. Measured on the recording.
TRAVEL = 2.05
# The chase camera's shots play at two ticks a second.
PACE = 2.0
# The still for the submission page: this shot, this many seconds in (the title over the map).
POSTER = ("world", 0.85)


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
    # seconds into its beat at which a phrase of a line is said, the line starting 0.3 or 0.25 s into the beat
    b = lambda phrase, lead=0.0: round(0.3 + say.at("b1", phrase) + lead, 2)          # noqa: E731  the world
    g = lambda phrase, lead=0.0: round(0.25 + say.at("b2", phrase) + lead, 2)         # noqa: E731  the ground
    r = lambda phrase: round(0.4 + say.at("r1", phrase) - 0.1, 2)                     # noqa: E731  the reference slide
    flat = 0.5 + say.at("a1", "flat")                  # the cold open: the battery is flat on the word
    miss = g("Three centimetres", 0.5)                 # the ground: the missed sample (tick 46) comes as it is named, and stays in view
    steep = g("ground too steep", -0.15)               # the cut to the rover at the scarp
    zero = say.at("b4", "zero")                        # energy: Claude's battery is flat on the word
    chase = "A.setCam('chase'); A.view.k = 1; A.view.snap = true; A.setSpeed(1); A.setPlaying(true);"
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
        # 2. The world: site 1 from its first tick under the title, then a ride behind a rover while the delay is
        #    explained. The ring the rover trails is its last position fix, 3 ticks old.
        {"name": "world", "page": "campaign", "site": 1, "chapter": "THE ENVIRONMENT", "beats": [
            {"vo": "b1", "vo_at": 0.3, "pad": 0.3,
             "js": "A.showTitle(false); A.seek(0); A.setCam('map'); A.setSpeed(4); A.setPlaying(true);",
             "overlay": [
                 {"kind": "title", "from": 0.0, "to": b("one day", 0.5)},
                 {"kind": "caption", "side": "left", "from": b("Every command"), "to": 99, "text": "COMMANDS AND FIXES: 3 TICKS LATE"},
             ],
             # the camera takes 1.1 s to fly in
             "at": [{"t": b("Every command", -1.0), "js": "A.setSpeed(1); A.setCam('chase');"}]},
        ]},
        # 3. The ground, on two rovers of the judged run at site 3. Opus agent 2 samples 2.53 m from a target that
        #    wants 2.5 m (tick 46): the red MISS comes up as the voice names it. Then a cut to Sonnet agent 1 on
        #    the lip of the scarp, stopped for ground too steep at tick 302, one of its 30 stops at this site.
        {"name": "ground", "page": "campaign", "site": 3, "chapter": "THE ENVIRONMENT", "beats": [
            {"vo": "b2", "vo_at": 0.25, "over": True, "min": steep,
             "js": "A.showTitle(false); A.follow('campaign-agent-opus-2'); A.seek(%.2f); %s" % (46 - PACE * miss, chase),
             "overlay": [
                 {"kind": "caption", "side": "left", "from": g("Wheels slip"), "to": g("Three centimetres", -0.1), "text": "WHEELS SLIP ON SAND AND SLOPES"},
                 {"kind": "caption", "side": "left", "from": g("Three centimetres"), "to": round(steep - 0.05, 2), "text": "SAMPLED 3 CM TOO FAR · A MISS"},
             ]},
            {"min": 2.0, "pad": 0.3,
             "js": "A.follow('campaign-agent-sonnet-1'); A.seek(%.2f); A.view.snap = true;" % (302 - PACE * 1.25),
             "overlay": [{"kind": "caption", "side": "left", "from": 0.2, "to": 99, "text": "TOO STEEP: SAFETY STOP, COMMANDS WIPED"}]},
        ]},
        # 4. Energy, and why Claude struggles: site 3 in story mode. The reference waits for the sun at 9% (tick 93);
        #    four ticks later Opus agent 4 runs flat, on the word "zero".
        {"name": "energy", "page": "campaign", "site": 3, "chapter": "WHY CLAUDE STRUGGLES", "beats": [
            {"vo": "b4", "vo_at": 0.3, "over": True, "min": round(0.3 + zero - TRAVEL, 2),
             "js": "A.showTitle(false); A.HOLD.ref_wait = 999; A.HOLD.lost = 999; A.seek(87); A.setCam('map'); A.startStory();",
             # gone before the page's card for the reference comes up in the same place
             "overlay": [{"kind": "caption", "from": 0.35, "to": round(0.3 + say.at("b4", "At nine percent") - 0.1, 2), "text": "THE ONLY FUEL IS THE SUN"}],
             "then": "A.story.hold = 0;"},
            {"until": "!!(A.story.active && A.story.active.kind === 'lost')"},
            {"min": 2.0, "pad": 0.9, "thump": 0.0},
        ]},
        # 5. Claude's own words about that failure: each quotation as the voice gets to it, then the verdict.
        {"name": "quote", "page": "film", "scene": "quote", "beats": [
            {"vo": "q1", "vo_at": 0.4, "pad": 0.8,
             "cues": [0.6, round(0.4 + say.at("q1", "and that all three") - 0.2, 2), round(0.4 + say.at("q1", "Claude doesn't fail") - 0.15, 2)]}]},
        # 6. The reference: what it does, as a chain that lights up link by link, over the battery through one day.
        {"name": "reference", "page": "film", "scene": "reference", "beats": [
            {"vo": "r1", "vo_at": 0.4, "pad": 1.3, "cues": [r("It tracks"), r("learns how"), r("and prices")]},
        ]},
        # 7. Results on the campaign.
        {"name": "results", "page": "film", "scene": "results", "beats": [
            {"vo": "s1", "vo_at": 0.4, "pad": 0.7, "min": 7.0, "cues": [round(0.4 + say.at("s1", "Doing nothing") - 0.15, 2)]}]},
        # 8. Modal: the 300-world comparison, then the learned policy.
        {"name": "farm", "page": "film", "scene": "farm", "beats": [
            {"vo": "m1", "vo_at": 0.4, "pad": 0.7, "min": 9.0,
             "cues": [round(0.4 + say.at("m1", "The reference scored") - 0.1, 2), round(0.4 + say.at("m1", "Claude's few wins") - 0.1, 2)]}]},
        {"name": "learning", "page": "film", "scene": "learning", "beats": [{"vo": "m2", "vo_at": 0.4, "pad": 0.7}]},
        # 9. The end card.
        {"name": "end", "page": "film", "scene": "end", "fade_out": 0.8, "beats": [
            {"vo": "e1", "vo_at": 0.5, "pad": 1.4, "min": 6.0,
             "cues": [round(0.5 + say.at("e1", "and a live demo") - 0.1, 2), round(0.5 + say.at("e1", "Can your agent") - 0.15, 2)]}]},
    ]
