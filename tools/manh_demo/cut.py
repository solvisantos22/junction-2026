"""manh_demo_1: what this cut does differently from Kristján's storyboard.

The story, the narration, the numbers and the shots are his (`tools/demo_video/storyboard.py`)
and are read from there every time, so a change to his script carries over. This file only
adds to it:

- the top-down moment of the opening shot is held a little longer, so the logo trackers have
  about two seconds over the rovers as they leave the lander, before the camera drops in;
- a few sounds that belong to a moment of a shot (the title, a camera move, a hard cut);
- the length: the film is stretched on its last card to `TARGET_SECONDS`, which a player shows
  as 1:59, one second inside the Junction's two-minute limit.
"""

from __future__ import annotations

from typing import Any, Dict, List

from tools.demo_video import storyboard as base

NAME = "manh_demo_1"
TARGET_SECONDS = 119.1          # a player shows 1:59 whether it rounds down or to the nearest second
LIMIT_SECONDS = 119.4           # never over this; the Junction's limit is 120

LINES, SUBTITLES, VOICE, POSTER, LIVE_URL = base.LINES, base.SUBTITLES, base.VOICE, base.POSTER, base.LIVE_URL

# Draft pieces: short clips of their own, recorded with `make piece --name ...` and looked at one by one. They are
# not in the film; the team picks among them first (Manh, 15 November: "a bunch of small clips ... we select").
PIECES: Dict[str, Dict[str, Any]] = {
    # three labs, three tiers, nine models, rolled out from the fastest tier to the flagships
    "lineup": {"page": "film", "scene": "lineup", "fade_out": 0.4, "beats": [{"min": 8.6}]},
    # what the models are measured against: the reference (a model-based planner) and the team's own RL agent
    "drivers": {"page": "film", "scene": "drivers", "fade_out": 0.4, "beats": [{"min": 9.0}]},
    # the opening: Mars from orbit, a dive through the dust, a landing beside the rover on the real map, a rise to the overview, the title (`intro.js`)
    "intro": {"page": "campaign", "site": 1, "addon": "intro.js", "addon_settings": {"orbit": 9.0, "dive": 2.6, "land": 3.2, "rise": 2.4},
              "vacuum": [0.0, 10.4], "fade_in": 0.9, "fade_out": 0.5, "beats": [
        {"min": 11.6, "trackers": False, "js": "A.showTitle(false); A.seek(0); A.setCam('map'); A.setPlaying(false);",
         "sfx": [{"t": 0.4, "kind": "hit_soft"}, {"t": 8.7, "kind": "riser", "len": 2.9}]},
        {"min": 5.6, "trackers": False, "sfx": [{"t": 0.0, "kind": "whoosh", "len": 2.2}]},
        {"min": 4.4, "trackers": False, "js": "A.setSpeed(4); A.setPlaying(true);",
         "overlay": [{"kind": "title", "from": 0.1, "to": 3.9}], "sfx": [{"t": 0.15, "kind": "hit"}]},
    ]},
    # four drafts of a 3D icon floating over the rover, in a studio with three of the film's rovers (`icons.js`)
    "icons": {"page": "campaign", "site": 1, "addon": "icons.js", "addon_settings": {"show": 5.0}, "vacuum": [0.0, 20.4], "fade_in": 0.5, "fade_out": 0.4, "beats": [
        {"min": 20.0, "trackers": False, "js": "A.showTitle(false); A.seek(210); A.setCam('map'); A.setPlaying(false);",
         "sfx": [{"t": 0.25 + 5.0 * k, "kind": "chime_soft", "step": k} for k in range(4)]},
    ]},
    # the same four drafts with the labs' own logos (Anthropic, Google DeepMind, OpenAI) instead of the model families' marks
    "icons_labs": {"page": "campaign", "site": 1, "addon": "icons.js", "addon_settings": {"show": 5.0, "company": True}, "vacuum": [0.0, 20.4], "fade_in": 0.5, "fade_out": 0.4, "beats": [
        {"min": 20.0, "trackers": False, "js": "A.showTitle(false); A.seek(210); A.setCam('map'); A.setPlaying(false);",
         "sfx": [{"t": 0.25 + 5.0 * k, "kind": "chime_soft", "step": k} for k in range(4)]},
    ]},
    # the four drafts over the real environment (`icons_scene.js`): for each kind, three seconds behind a driving rover,
    # then three and a half from above with every rover on the map. The same two moments each time, to compare fairly.
    "icons_scene": {"page": "campaign", "site": 1, "addon": "icons_scene.js", "addon_settings": {"show": 6.4}, "fade_in": 0.4, "fade_out": 0.4, "beats": [
        beat for k in range(4) for beat in (
            {"min": 3.0, "trackers": False, "js": "A.showTitle(false); A.follow('campaign-agent-sonnet-2'); A.seek(47); A.setCam('chase'); A.view.k = 1; A.view.snap = true; A.setSpeed(1); A.setPlaying(true);", "sfx": [{"t": 0.2, "kind": "chime_soft", "step": k}]},
            {"min": 3.4, "trackers": False, "js": "A.setCam('map'); A.view.k = 0; A.view.snap = true; A.seek(150); A.setSpeed(3); A.setPlaying(true);"})
    ]},
    # Kristján's two Modal scenes and his end card, to show Modal's name in its green with its mark
    "modal_farm": {"page": "film", "scene": "farm", "fade_out": 0.4, "beats": [{"min": 9.0, "cues": [4.6, 6.4]}]},
    "modal_learning": {"page": "film", "scene": "learning", "fade_out": 0.4, "beats": [{"min": 7.0}]},
    "modal_end": {"page": "film", "scene": "end", "fade_out": 0.6, "beats": [{"min": 7.0, "cues": [2.6, 4.2]}]},
}

TITLE_LEAD = 0.25               # the title lands on its own before the narrator names it
MAP_HOLD = 0.5                  # the camera drops in this much later than in Kristján's cut


def only(items: List[Dict[str, Any]], what: str, **match: Any) -> Dict[str, Any]:
    found = [item for item in items if all(item.get(key) == value for key, value in match.items())]
    if len(found) != 1:
        raise SystemExit("manh_demo: expected one {} in Kristján's storyboard, found {}: look at tools/manh_demo/cut.py".format(what, len(found)))
    return found[0]


def shots(durations: Dict[str, float], words: Dict[str, List[Dict[str, Any]]], stretch: float = 0.0) -> List[Dict[str, Any]]:
    """Kristján's shots with this cut's additions. `stretch` lengthens the last card (see `make.fit`)."""
    plan = base.shots(durations, words)
    say = base.Words(words)
    by = {shot["name"]: shot for shot in plan}

    # The cold open: "zero" rings for a moment before the cut; the camera rising to the map is heard.
    cold = by["cold"]["beats"]
    cold[-1]["pad"] = cold[-1].get("pad", 0.0) + 0.3
    cold[-1].setdefault("sfx", []).append({"t": 0.0, "kind": "whoosh", "len": 1.3})

    # The world: the title first, then the map with the trackers up while the rovers leave the lander,
    # then the camera drops in behind one of them as the delay is explained.
    world = only(by["world"]["beats"], "narrated beat of the world shot", vo="b1")
    world["vo_at"] = world.get("vo_at", 0.0) + TITLE_LEAD
    start = world["vo_at"]
    title = only(world["overlay"], "title cue", kind="title")
    title["to"] = round(start + say.at("b1", "one day") - 0.1, 2)
    caption = only(world["overlay"], "caption", kind="caption")
    caption["from"] = round(start + say.at("b1", "Every command"), 2)
    if len(world.get("at", [])) != 1:
        raise SystemExit("manh_demo: the world shot no longer has one timed camera change")
    world["at"][0]["t"] = round(start + say.at("b1", "Every command") - 1.0 + MAP_HOLD, 2)
    world["sfx"] = [{"t": 0.05, "kind": "hit"}, {"t": world["at"][0]["t"], "kind": "whoosh", "len": 1.2}]

    # The ground: the hard cut to the second rover is marked by a short breath of air.
    ground = by["ground"]["beats"]
    ground[1].setdefault("sfx", []).append({"t": 0.0, "kind": "cut"})

    # The end card holds until the film is exactly as long as it should be.
    end = by["end"]["beats"][-1]
    end["pad"] = round(end.get("pad", 0.0) + stretch, 3)
    return plan


# ---------------------------------------------------------------- the second draft: script v2, compiled from the pieces
# Manh, 15 November about 05:20: "compile it onto a next draft demo", and a little later: the replay should carry all
# the different agents, as a story from the light models to the heavy ones. The words follow docs/manh-demo/script-v2.md
# (plain, a cliffhanger after every beat), spoken by the placeholder voice until the team records its own. The pictures
# are the pieces he has seen one by one: the opening from orbit, the lineup, the floating marks and the score-cards,
# the card for the reference and the trained agent, and Kristján's planner, 300-world and end scenes. New here: a
# replay with one rover per model (`makers.CAST`) and a chart of every run of all nine (`scenes.js`, `tiers`).
#
# The ladder, one failure per tier and three labs between them, every one a moment of a saved run:
#   FAST      GPT-6 Luna, site 3: samples 2.53 m from a rock that needs 2.5 m (tick 104); 8 misses and 1 sample there
#   BALANCED  Claude Sonnet 5.5, site 3: onto the scarp at tick 302; 30 safety stops there
#   FLAGSHIP  Claude Opus 5.5, site 1: battery flat at tick 409, 13 m from the lander, 21 samples on board
# and then the reason, on Gemini 4 Argon at site 3: flat at tick 62, where the reference waits for the sun at tick 93.
# What line n8 and n11 say about the scores is checked against the runs at every build (`makers.tier_table`).
NAME2 = "manh_demo_2"
VOICE2 = {"voice": "af_heart", "speed": 1.12}
LINES2: Dict[str, str] = {
    "n1": "Imagine driving a car that obeys you three seconds late. That is every day on Mars. So who do you trust to drive?",
    "n2": "We built that day. One rover, one day of sunlight, rocks to collect, and one rule: be home before the battery dies.",
    "n3": "Then we handed the keys to nine AI models from three labs. Surely one of them makes it home?",
    "n4": "Mars doesn't play fair. A fast one reaches for a rock and misses, by three centimetres. No points. Nine tries, one rock.",
    "n5": "A bigger one drives onto a slope too steep. The rover freezes and forgets its orders. Thirty times.",
    "n6": "And a flagship: thirteen metres from home, twenty-one samples on board. It will not make it.",
    "n6b": "Nothing broke. So what went wrong?",
    "n6c": "Its own report says why: the planner counted time, never the battery. "
           "And it played all three maps without checking one result.",
    "n7": "The sun. It's the only fuel. This rover drove until its battery was flat.",
    "n7b": "Our driver saw its battery fall, stopped, and waited for light. So how did all nine do?",
    "n8": "On three maps in a row, none beat our driver. The best run came within a hair. "
          "Ours brought home forty-eight percent, and never lost a rover. So what is it?",
    "n9": "Not an AI. A planner: plain code that works out the whole day before the wheels turn. Lucky maps?",
    "n10": "So we replayed every model's best program on three hundred fresh worlds, on Modal. "
           "The planner won ninety-five times in a hundred. Can a machine learn it instead?",
    "n11": "We trained a small one from scratch: from eight percent to thirty-six on unseen worlds, still short of the planner. "
           "Even a model trained to pick the planner's strategy gained less than half a point.",
    "n12": "AI can write the code. It can't yet plan the day. Can your agent make it home?",
}
SUBTITLES2: Dict[str, str] = {
    **LINES2,
    "n4": "Mars doesn't play fair. A fast one reaches for a rock and misses, by 3 centimetres. No points. 9 tries, 1 rock.",
    "n5": "A bigger one drives onto a slope too steep. The rover freezes and forgets its orders. 30 times.",
    "n6": "And a flagship: 13 metres from home, 21 samples on board. It will not make it.",
    "n8": "On three maps in a row, none beat our driver. The best run came within a hair. "
          "Ours brought home 48%, and never lost a rover. So what is it?",
    "n10": "So we replayed every model's best program on 300 fresh worlds, on Modal. "
           "The planner won 95 times in 100. Can a machine learn it instead?",
    "n11": "We trained a small one from scratch: from 8% to 36% on unseen worlds, still short of the planner. "
           "Even a model trained to pick the planner's strategy gained less than half a point.",
}
# What lines n8, n10 and n11 say in words, as `makers.tier_table`, `makers.worlds_table` and Kristján's numbers for
# the learning slide count it; the build stops if the runs say otherwise.
SAID2 = {"tiers": {"reference_percent": 48}, "worlds": {"percent": 95, "worlds": 300, "reference_lost": 0},
         "final": {"initial_percent": 8, "ppo_percent": 36, "gain_under_half_a_point": True}}
DIVE2, LAND2, RISE2 = 2.4, 3.0, 2.4
FAST, MID, FLAGSHIP, FLAT = "campaign-agent-gpt-6-luna-1", "campaign-agent-sonnet-1", "campaign-agent-opus-2", "campaign-agent-gemini-4-argon-1"
STORY_LEAD = 11.8               # ticks before a moment at which story mode is started, to arrive on a word (see shots2)


def shots2(durations: Dict[str, float], words: Dict[str, List[Dict[str, Any]]], stretch: float = 0.0) -> List[Dict[str, Any]]:
    """The second draft, shot by shot. `stretch` lengthens the last card (see `make.fit`)."""
    say = base.Words(words)                                # reads the lines the build has switched to (LINES2)
    at = lambda line, phrase, lead=0.0: round(say.at(line, phrase) + lead, 2)          # noqa: E731
    chase = "A.setCam('chase'); A.view.k = 1; A.view.snap = true; A.setSpeed(1); A.setPlaying(true);"
    orbit = round(max(4.4, 0.6 + at("n1", "So who") - 0.25), 2)      # the fall begins on the question
    miss = round(0.3 + at("n4", "misses") + 0.35, 2)                 # the sample fails as "misses" is said
    stop = round(0.3 + at("n5", "The rover freezes") + 0.2, 2)       # the first safety stop on "freezes"
    flat = round(0.4 + at("n6", "It will not make it") + 0.95, 2)    # the battery is flat as the sentence ends
    return [
        # 1. The opening: Mars from orbit while the viewer is put in the driver's seat; the fall on the question; the landing
        #    on our own map and the rise to the overview while the game is explained; the title.
        {"name": "v2_intro", "page": "campaign", "site": 1, "addon": "intro.js",
         "addon_settings": {"orbit": orbit, "dive": DIVE2, "land": LAND2, "rise": RISE2, "words": [0.4, 1.3, 1.6]},
         "vacuum": [0.0, round(orbit + DIVE2 - 0.2, 2)], "fade_in": 0.6, "beats": [
            {"min": round(orbit + DIVE2, 2), "vo": "n1", "vo_at": 0.6, "over": True, "trackers": False,
             "js": "A.showTitle(false); A.seek(0); A.setCam('map'); A.setPlaying(false);",
             "sfx": [{"t": 0.4, "kind": "hit_soft"}, {"t": round(orbit - 0.3, 2), "kind": "riser", "len": DIVE2 + 0.3}]},
            {"min": LAND2 + RISE2, "vo": "n2", "vo_at": 0.4, "over": True, "trackers": False, "sfx": [{"t": 0.0, "kind": "whoosh", "len": 2.2}]},
            {"min": 3.0, "pad": 0.45, "trackers": False, "js": "A.setSpeed(4); A.setPlaying(true);",
             "overlay": [{"kind": "title", "from": 0.1, "to": 99}], "sfx": [{"t": 0.15, "kind": "hit"}]},
        ]},
        # 2. Who drives: three labs, three tiers, nine models.
        {"name": "v2_lineup", "page": "film", "scene": "lineup", "beats": [{"vo": "n3", "vo_at": 0.4, "pad": 0.5, "min": 5.6}]},
        # 3. The ladder. A fast model: behind GPT-6 Luna at site 3 as it samples 3 cm too far from a rock.
        {"name": "v2_fast", "page": "campaign", "site": 3, "beats": [
            {"vo": "n4", "vo_at": 0.3, "pad": 0.7,
             "js": "A.showTitle(false); A.follow('%s'); A.seek(%.2f); %s" % (FAST, 104 - base.PACE * miss, chase),
             "overlay": [
                 {"kind": "caption", "side": "left", "from": round(miss + 0.25, 2), "to": round(0.3 + at("n4", "Nine tries") - 0.1, 2), "text": "3 CM TOO FAR · NO POINTS"},
                 {"kind": "caption", "side": "left", "from": round(0.3 + at("n4", "Nine tries"), 2), "to": 99, "text": "9 TRIES · 1 ROCK"},
             ]},
        ]},
        #    A balanced one: Claude Sonnet 5.5 at the scarp of the same site, stopped by the tilt limit again and again.
        {"name": "v2_mid", "page": "campaign", "site": 3, "beats": [
            {"vo": "n5", "vo_at": 0.3, "pad": 0.7,
             "js": "A.showTitle(false); A.follow('%s'); A.seek(%.2f); %s" % (MID, 302 - base.PACE * stop, chase),
             "overlay": [{"kind": "caption", "side": "left", "from": round(stop + 0.25, 2), "to": 99, "text": "TOO STEEP · 30 SAFETY STOPS"}],
             "sfx": [{"t": 0.0, "kind": "cut"}]},
        ]},
        #    A flagship: behind Claude Opus 5.5 at site 1, timed so that its battery runs out as "it will not make it"
        #    ends; then the camera rises and the score-card says what happened.
        {"name": "v2_flagship", "page": "campaign", "site": 1, "beats": [
            {"vo": "n6", "vo_at": 0.4, "over": True, "until": "A.state.t >= 409",
             "js": "A.showTitle(false); A.HOLD.lost = 999; A.follow('%s'); A.seek(%.2f); "
                   "A.setCam('chase'); A.view.k = 1; A.view.snap = true; A.setSpeed(2); A.setPlaying(true);" % (FLAGSHIP, 409 - 3 * flat),
             "overlay": [{"kind": "caption", "side": "left", "from": round(0.4 + at("n6", "thirteen metres"), 2), "to": round(flat - 0.05, 2),
                          "text": "13 M FROM HOME · 21 SAMPLES ON BOARD"}],
             "sfx": [{"t": 0.0, "kind": "cut"}]},
            {"min": 0.9, "thump": 0.0, "js": "A.setPlaying(false); A.seek(409); document.getElementById('mini').style.opacity = '0';"},
            {"vo": "n6b", "vo_at": 0.8, "min": 3.6, "pad": 0.5, "js": "A.startStory();", "sfx": [{"t": 0.0, "kind": "whoosh", "len": 1.3}]},
        ]},
        #    What it says itself: Kristján's "In Claude's own words" (that same run's closing report), without his verdict line,
        #    which this film keeps for its end.
        {"name": "v2_quote", "page": "film", "scene": "quote", "beats": [
            {"vo": "n6c", "vo_at": 0.4, "pad": 0.6, "cues": [0.5, round(0.4 + at("n6c", "And it played") - 0.2, 2), 99.0]}]},
        # 4. Why: the sun. Site 3 from above in story mode: Gemini 4 Argon runs flat at tick 62; a cut to tick 93, where the
        #    reference stops and waits for light.
        {"name": "v2_energy", "page": "campaign", "site": 3, "beats": [
            {"vo": "n7", "vo_at": 0.3, "over": True, "until": "!!(A.story.active && A.story.active.kind === 'lost')",
             "js": "A.showTitle(false); A.HOLD.lost = 999; A.HOLD.ref_wait = 999; A.follow('%s'); A.seek(%.2f); A.setCam('map'); A.startStory();" % (FLAT, 62 - STORY_LEAD),
             "overlay": [{"kind": "caption", "from": 0.35, "to": round(0.3 + at("n7", "This rover") - 0.1, 2), "text": "THE ONLY FUEL IS THE SUN"}]},
            {"min": 2.4, "thump": 0.0},
            # a hard cut: the first card goes with the picture it belongs to, without its fade
            {"vo": "n7b", "vo_at": 0.35, "over": True, "until": "!!(A.story.active && A.story.active.kind === 'ref_wait')",
             "js": "A.card.style.transition = 'none'; A.stopStory(); A.seek(90.4); A.startStory();",
             "at": [{"t": 0.2, "js": "A.card.style.transition = '';"}], "sfx": [{"t": 0.0, "kind": "cut"}]},
            {"min": 3.0, "pad": 0.6},
        ]},
        # 5. Every run of all nine models against the planner.
        {"name": "v2_tiers", "page": "film", "scene": "tiers", "beats": [
            {"vo": "n8", "vo_at": 0.4, "pad": 0.8, "min": 8.0,
             "cues": [round(0.4 + at("n8", "The best run") - 0.1, 2), round(0.4 + at("n8", "Ours") - 0.1, 2)]}]},
        # 6. What our driver is (Kristján's scene, with the method behind each of its four links named above it), and the
        #    300 fresh worlds on Modal: his chart's look, with every model's
        #    best program in it instead of Claude's six (Manh: "it's only Claude? ... such that it includes all the models").
        {"name": "v2_reference", "page": "film", "scene": "planner", "beats": [
            {"vo": "n9", "vo_at": 0.4, "pad": 0.9,
             "cues": [round(0.4 + at("n9", "Not an AI") + 0.1, 2), round(0.4 + at("n9", "A planner") - 0.1, 2),
                      round(0.4 + at("n9", "plain code") - 0.1, 2), round(0.4 + at("n9", "before the wheels") - 0.1, 2)]}]},
        {"name": "v2_farm", "page": "film", "scene": "worlds", "beats": [
            {"vo": "n10", "vo_at": 0.4, "pad": 0.6, "min": 9.0,
             "cues": [round(0.4 + at("n10", "The planner won") - 0.1, 2), round(0.4 + at("n10", "Can a machine") - 0.1, 2)]}]},
        # 7. The models that learn (Kristján's slide of his third cut: Sölvi's final controllers on held-out worlds and on the
        #    campaign, then the model that picks the planner's strategy), and the end card.
        {"name": "v2_learning", "page": "film", "scene": "learning3", "beats": [
            {"vo": "n11", "vo_at": 0.4, "pad": 0.8,
             "cues": [round(0.4 + at("n11", "still short") - 0.15, 2), round(0.4 + at("n11", "Even a model") - 0.15, 2)]}]},
        {"name": "v2_end", "page": "film", "scene": "end", "fade_out": 0.8, "beats": [
            {"vo": "n12", "vo_at": 0.5, "pad": round(1.2 + stretch, 3), "min": 6.0,
             "cues": [round(0.5 + at("n12", "It can't yet") - 0.1, 2), round(0.5 + at("n12", "Can your agent") - 0.15, 2)]}]},
    ]


# For the narration kit (`make kit --film 2`): what the picture does at a moment of a shot, so that whoever records
# the narration can land the same words on it. `cues` name a chart scene's cues in order (None: not shown), `events`
# the first time something happens to the followed rover (as the recorder's telemetry calls it), `parts` the opening.
SYNC2: Dict[str, Dict[str, Any]] = {
    "v2_intro": {"parts": {"dive": "the camera starts to fall towards Mars (on \"So who\")", "title": "the title LIGHTLAG TRAVERSE comes up"}},
    "v2_fast": {"events": {"miss": "MISS appears over the rover (on \"misses\")"}},
    "v2_mid": {"events": {"stop": "STOPPED appears over the rover (on \"freezes\")"}},
    "v2_flagship": {"events": {"dead": "the battery runs flat and the picture dips (as \"It will not make it\" ends)", "card": "the score-card comes up"}},
    "v2_quote": {"cues": ["the first quotation comes up", "the second quotation comes up (on \"And it played\")", None]},
    "v2_energy": {"events": {"dead": "the rover's battery runs flat (on \"flat\")", "gold": "the planner's card WAITS FOR THE SUN comes up"}},
    "v2_tiers": {"cues": ["a ring marks the best single run (on \"The best run\")", "the planner's label lights up (on \"Ours\")"]},
    "v2_reference": {"cues": ["the first link lights (on \"Not an AI\")", "the second link lights (on \"A planner\")",
                              "the third link lights (on \"plain code\")", "the last link lights (on \"before the wheels\")"]},
    "v2_farm": {"cues": ["the totals come up (on \"The planner won\")", "the small note comes up (on \"Can a machine\")"]},
    "v2_learning": {"cues": ["the campaign row comes up (on \"still short\")", "the panel about the planner itself comes up (on \"Even a model\")"]},
    "v2_end": {"cues": ["the live-demo line comes up (on \"It can't yet\")", "the question comes up (on \"Can your agent\")"]},
}


# ---------------------------------------------------------------- the long film: the same story in about ten minutes
# Manh, 15 November about 07:15: "a 10 minute demo of essentially the same idea except it's more in depth, and it's
# not as rushed": what happens and why, how the models compare and why each lab did as it did, the reference in
# detail and why it is a fair one to measure against, and the learned agent as a baseline. Same pictures and the same
# kind of words as the two-minute draft, at a calmer pace (the voice a little slower, longer pauses), with three
# slides of its own (`scenes.js`: rules, outcomes, why). The claims about the labs are the tier comparison's
# (docs/tier-comparison.md) and are counted from the saved runs; `SAID3` holds what the narration states in numbers.
NAME3 = "manh_demo_long"
VOICE3 = {"voice": "af_heart", "speed": 0.96}
LINES3: Dict[str, str] = {
    "a1": "Imagine driving a car where everything you see happened three seconds ago, and the car obeys you three seconds late. "
          "On Mars, that is every day. A signal from Earth takes minutes to arrive, so a rover cannot be steered. It has to be trusted. "
          "So who do you trust to drive?",
    "a2": "We built that day. One rover, one day of sunlight, and a map full of rocks worth collecting. "
          "And one rule above all: be home before the battery dies.",
    "b1": "This is Lightlag Traverse. Six hundred metres of craters, sand and bedrock. Thirty-eight targets at sunrise, more appearing "
          "through the day, and never enough time to reach them all. Every rover starts at the lander with a full battery, "
          "and four hundred and twenty steps of daylight.",
    "b2": "The driver gets five tools: read the rules, read the map, read the telemetry, send commands, and let time pass. Then come the catches.",
    "b3": "Commands land late. The news from the rover is already old. Wheels slip, differently on every surface. "
          "Ground that is too steep stops the rover and wipes its orders. The only fuel is the sun.",
    "b4": "And the score is unforgiving. Come home, and keep everything. Stop short, and keep half. Run flat, and keep nothing.",
    "c1": "Then we handed the keys to nine AI models from three labs: Anthropic, Google and OpenAI. From each lab, the fast model, "
          "the everyday one, and the flagship.",
    "c2": "Each gets the same task, the same five tools, and forty-five minutes to write its own autopilot. No practice run. "
          "Three maps in a row. Surely one of them makes it home?",
    "d1": "Start with a fast one. GPT-6 Luna reaches for a rock, and misses. By three centimetres. The rover has to stand within "
          "two and a half metres when the command lands, and the command lands late. Nine tries on this map. One rock.",
    "d2": "A bigger one. Claude Sonnet drives onto a slope too steep. The rover freezes, and every order it was carrying is wiped. "
          "It sends new ones, and freezes again. Thirty times on this one map. When the day ends it is seventy-two metres from home, "
          "and its samples count half.",
    "d3": "And a flagship. Claude Opus has had a good day: twenty-one samples on board, thirteen metres from the lander. It will not make it.",
    "d3b": "Battery flat. Zero points for the whole map. Nothing broke. So what went wrong?",
    "d4": "Ask the model. Its own closing report says the route planner only counted time. It never checked whether the battery would last.",
    "d4b": "And its autopilot played all three maps in forty-five seconds, without checking a single result in between. "
           "It did not fail at coding. It failed at planning the day.",
    "d5": "And it is not one lab's problem. Here Google's Gemini 4 Argon drives its battery flat, sixteen metres from the lander, "
          "with most of the day still ahead.",
    "d5b": "A wait of four steps for the sun would have saved it.",
    "d5c": "On the same map, our own driver sees its battery fall to nine percent, stops, and waits for light.",
    "d6": "Not every run fails. This is the one that came within a hair: Gemini 4 Carbon, on its second run. On this map it brings home "
          "twenty-six samples, as many as our planner, and is back at the lander before dark. So the task can be done. "
          "The same model's third run never left the lander.",
    "e1": "So how did all nine do? Twenty-five live runs, three maps each. A dot is one run. The bar is the model's average. "
          "The gold line is our driver: forty-eight percent of everything on the maps, brought home.",
    "e1b": "No run crosses it. One comes within a hair: Google's flagship, Gemini 4 Carbon, at forty-seven point three. "
           "On average, Gemini 4 Hydrogen and GPT-6.1 Sol lead. Claude Sonnet and Opus sit in the middle. "
           "And at the bottom, the models that missed, or never moved.",
    "e2": "Look closer, and every lab fails in its own way. Gemini is all or nothing. When its agents drive, they drive best. "
          "But three of nine runs never left the lander: the agent used up its forty-five minutes before its program drove a metre.",
    "e2b": "OpenAI's flagship, GPT-6.1 Sol, is the steadiest of all nine: never lost, never idle. But on the first map it ended "
           "every run away from the lander, and kept half. Its smaller models come home with little on board.",
    "e2c": "Claude writes its autopilot within minutes, and then loses rovers to the battery: four of them. "
           "Its fast model never left the lander at all.",
    "e3": "And the tiers? They do not decide it. Google's fast model, Gemini 4 Hydrogen, has the best average of all nine: "
          "thirty-seven percent. Not because it drives better than its big brother. Carbon's best runs beat it. "
          "But all three of its runs had a program driving in time. On this task, finishing beats thinking longer.",
    "e3b": "Price does not buy it either. A run cost from three cents to almost two dollars, and the best average came at ninety-three cents.",
    "f1": "So what is our driver? Not an AI. It is a planner: about thirteen hundred lines of plain Python, "
          "playing through the same five tools as everyone else. It does four things.",
    "f2": "An extended Kalman filter tracks where the rover really is, through the delay and the noise. "
          "It learns how each surface slips, from its own wheels. It prices every leg of every route, in time and in energy, against the sun. "
          "And it searches for the best day: which rocks, in which order, and home before dark. Then it plans again, every few steps.",
    "f4": "Watch it work. By evening it turns for home with nineteen samples and a third of its battery left, "
          "and reaches the lander twenty-six steps before dark.",
    "f3": "Why is that a fair yardstick? It uses the same five tools, and nothing hidden. It is plain code that anyone can read. "
          "It gives the same score every time: on a laptop, on Modal, and through Harbor.",
    "f3b": "It has never lost a rover. And it can be beaten: it leaves more than half of the value on the ground.",
    "g1": "Lucky maps? We wondered too. So we took every model's best program and replayed it on three hundred fresh worlds, on Modal. "
          "Worlds no model had seen. Twenty-seven hundred match-ups.",
    "g1b": "The planner scored higher in ninety-five of every hundred, and lost no rover. The models' programs lost a hundred and fifty-four.",
    "g2": "And look at who holds up. Programs that scored fifty-six percent on the one map they were written for "
          "fall to the low forties on new ground. The planner holds fifty. A program tuned to one map is not yet a driver.",
    "h1": "One more driver. Can a machine learn this, instead of being told? We trained small controllers from scratch on Modal. "
          "No language model: trial and error, over forty-seven thousand practice missions.",
    "h2": "Before training they bring home eight percent. After, thirty-six, on worlds they had never seen. "
          "On the campaign, every trained seed passes every Claude run.",
    "h2b": "And there they stop: level with a simple greedy rule, and well short of the planner. "
           "We even trained a model to pick the planner's own strategy mid-mission. It gained less than half a point.",
    "h3": "So the task comes with two baselines. The planner is the bar to beat. The learned agent is an honest picture of where "
          "learning stands today. Bring your own model, and you know at once where it lands.",
    "i1": "One command reruns all of it, and a live demo on Modal lets you pick any world and watch eight drivers take it on. "
          "AI can write the code. It cannot yet plan the day. Can your agent make it home?",
}
SUBTITLES3: Dict[str, str] = {
    **LINES3,
    "b1": "This is Lightlag Traverse. 600 metres of craters, sand and bedrock. 38 targets at sunrise, more appearing "
          "through the day, and never enough time to reach them all. Every rover starts at the lander with a full battery, and 420 steps of daylight.",
    "c2": "Each gets the same task, the same five tools, and 45 minutes to write its own autopilot. No practice run. "
          "Three maps in a row. Surely one of them makes it home?",
    "d1": "Start with a fast one. GPT-6 Luna reaches for a rock, and misses. By 3 centimetres. The rover has to stand within "
          "2.5 metres when the command lands, and the command lands late. 9 tries on this map. 1 rock.",
    "d2": "A bigger one. Claude Sonnet drives onto a slope too steep. The rover freezes, and every order it was carrying is wiped. "
          "It sends new ones, and freezes again. 30 times on this one map. When the day ends it is 72 metres from home, and its samples count half.",
    "d3": "And a flagship. Claude Opus has had a good day: 21 samples on board, 13 metres from the lander. It will not make it.",
    "d4b": "And its autopilot played all three maps in 45 seconds, without checking a single result in between. "
           "It did not fail at coding. It failed at planning the day.",
    "d5": "And it is not one lab's problem. Here Google's Gemini 4 Argon drives its battery flat, 16 metres from the lander, with most of the day still ahead.",
    "d5c": "On the same map, our own driver sees its battery fall to 9%, stops, and waits for light.",
    "d6": "Not every run fails. This is the one that came within a hair: Gemini 4 Carbon, on its second run. On this map it brings home "
          "26 samples, as many as our planner, and is back at the lander before dark. So the task can be done. "
          "The same model's third run never left the lander.",
    "e1": "So how did all nine do? 25 live runs, three maps each. A dot is one run. The bar is the model's average. "
          "The gold line is our driver: 48% of everything on the maps, brought home.",
    "e1b": "No run crosses it. One comes within a hair: Google's flagship, Gemini 4 Carbon, at 47.3. "
           "On average, Gemini 4 Hydrogen and GPT-6.1 Sol lead. Claude Sonnet and Opus sit in the middle. And at the bottom, the models that missed, or never moved.",
    "e2": "Look closer, and every lab fails in its own way. Gemini is all or nothing. When its agents drive, they drive best. "
          "But 3 of 9 runs never left the lander: the agent used up its 45 minutes before its program drove a metre.",
    "e3": "And the tiers? They do not decide it. Google's fast model, Gemini 4 Hydrogen, has the best average of all nine: 37%. "
          "Not because it drives better than its big brother. Carbon's best runs beat it. But all three of its runs had a program driving in time. "
          "On this task, finishing beats thinking longer.",
    "e3b": "Price does not buy it either. A run cost from 3 cents to almost 2 dollars, and the best average came at 93 cents.",
    "f1": "So what is our driver? Not an AI. It is a planner: about 1,300 lines of plain Python, playing through the same five tools as everyone else. It does four things.",
    "f4": "Watch it work. By evening it turns for home with 19 samples and a third of its battery left, and reaches the lander 26 steps before dark.",
    "g1": "Lucky maps? We wondered too. So we took every model's best program and replayed it on 300 fresh worlds, on Modal. Worlds no model had seen. 2,700 match-ups.",
    "g1b": "The planner scored higher in 95 of every 100, and lost no rover. The models' programs lost 154.",
    "g2": "And look at who holds up. Programs that scored 56% on the one map they were written for fall to the low forties on new ground. "
          "The planner holds 50. A program tuned to one map is not yet a driver.",
    "h1": "One more driver. Can a machine learn this, instead of being told? We trained small controllers from scratch on Modal. "
          "No language model: trial and error, over 47,000 practice missions.",
    "h2": "Before training they bring home 8%. After, 36, on worlds they had never seen. On the campaign, every trained seed passes every Claude run.",
}
# What the long film's narration states in numbers, as `make.chart_numbers` counts them ("long"); the build stops if the runs say otherwise.
SAID3 = {"long": {"ticks": 420, "targets_at_launch": 38, "width": 600, "runs": 25, "reference_percent": 48, "best_run_per_mille": 473, "best_mean_percent": 37,
                  "best_mean_model": "GEMINI 4 HYDROGEN", "google_runs": 9, "google_never_started": 3, "anthropic_lost": 4, "sol_away_on_site_one": 3,
                  "sol_lost_or_idle": 0, "cheapest_cents": 3, "dearest_cents": 191, "best_mean_cents": 93, "reference_lines_hundreds": 13,
                  "worlds": 300, "pairs": 2700, "worlds_percent": 95, "reference_lost": 0, "programs_lost": 154,
                  "initial_percent": 8, "ppo_percent": 36, "gain_under_half_a_point": True, "training_missions_thousands": 47}}
RL_ROVER, BEST = "campaign-rl-ppo-43", "campaign-agent-gemini-4-carbon-2"


def shots3(durations: Dict[str, float], words: Dict[str, List[Dict[str, Any]]], stretch: float = 0.0) -> List[Dict[str, Any]]:
    """The long film, shot by shot. Lines that share a chart follow each other inside one beat (`more`)."""
    say = base.Words(words)
    at = lambda line, phrase, lead=0.0: round(say.at(line, phrase) + lead, 2)          # noqa: E731
    chase = "A.setCam('chase'); A.view.k = 1; A.view.snap = true; A.setSpeed(1); A.setPlaying(true);"
    gap = 0.7                                               # the breath between two lines that share a picture

    def chain(first: float, *lines: str) -> List[float]:   # when each of several lines starts, one after the other
        starts, clock = [], first
        for line in lines:
            starts.append(round(clock, 2))
            clock += durations[line] + gap
        return starts

    orbit = round(max(8.0, 0.9 + at("a1", "So who") - 0.25), 2)
    miss = round(0.4 + at("d1", "and misses") + 0.45, 2)
    stop = round(0.4 + at("d2", "The rover freezes") + 0.25, 2)
    flat = round(0.5 + at("d3", "It will not make it") + 1.05, 2)
    rules = chain(0.6, "b2", "b3", "b4")
    lineup = chain(0.5, "c1", "c2")
    quote = chain(0.5, "d4", "d4b")
    tiers = chain(0.5, "e1", "e1b")
    labs = chain(0.6, "e2", "e2b", "e2c", "e3", "e3b")
    planner = chain(0.5, "f1", "f2")
    why = chain(0.6, "f3", "f3b")
    worlds = chain(0.5, "g1", "g1b", "g2")
    learn = chain(0.5, "h2", "h2b")
    more = lambda starts, *lines: [{"vo": line, "at": start} for line, start in zip(lines, starts[1:])]      # noqa: E731
    return [
        # 0. The hook: orbit, the fall, the landing, the title.
        {"name": "l_intro", "page": "campaign", "site": 1, "addon": "intro.js", "addon_settings": {"orbit": orbit, "dive": 2.6, "land": 3.2, "rise": 2.4},
         "vacuum": [0.0, round(orbit + 2.4, 2)], "fade_in": 0.9, "beats": [
            {"min": round(orbit + 2.6, 2), "vo": "a1", "vo_at": 0.9, "over": True, "trackers": False,
             "js": "A.showTitle(false); A.seek(0); A.setCam('map'); A.setPlaying(false);",
             "sfx": [{"t": 0.4, "kind": "hit_soft"}, {"t": round(orbit - 0.3, 2), "kind": "riser", "len": 2.9}]},
            {"min": 5.6, "vo": "a2", "vo_at": 0.5, "over": True, "trackers": False, "sfx": [{"t": 0.0, "kind": "whoosh", "len": 2.2}]},
            {"min": 4.0, "pad": 1.0, "trackers": False, "js": "A.setSpeed(4); A.setPlaying(true);",
             "overlay": [{"kind": "title", "from": 0.1, "to": 99}], "sfx": [{"t": 0.15, "kind": "hit"}]},
        ]},
        # 1. The game: the first site from above with all ten rovers leaving the lander, then the rules.
        {"name": "l_day", "page": "campaign", "site": 1, "beats": [
            {"vo": "b1", "vo_at": 0.6, "pad": 1.4, "js": "A.showTitle(false); A.seek(1); A.setCam('map'); A.setSpeed(3); A.setPlaying(true);",
             "overlay": [{"kind": "caption", "from": round(0.6 + at("b1", "Six hundred"), 2), "to": round(0.6 + at("b1", "Thirty-eight") - 0.1, 2), "text": "600 × 400 M OF CRATERS, SAND AND BEDROCK"},
                         {"kind": "caption", "from": round(0.6 + at("b1", "Thirty-eight"), 2), "to": round(0.6 + at("b1", "Every rover") - 0.1, 2), "text": "38 TARGETS AT SUNRISE · MORE ON THE WAY"},
                         {"kind": "caption", "from": round(0.6 + at("b1", "Every rover"), 2), "to": 99, "text": "ONE BATTERY · 420 STEPS OF DAYLIGHT"}]}]},
        {"name": "l_rules", "page": "film", "scene": "rules", "beats": [
            {"vo": "b2", "vo_at": rules[0], "more": more(rules, "b3", "b4"), "pad": 1.8,
             "cues": [round(rules[1] + at("b3", "Commands land late") - 0.1, 2), round(rules[1] + at("b3", "The news") - 0.1, 2), round(rules[1] + at("b3", "Wheels slip") - 0.1, 2),
                      round(rules[1] + at("b3", "Ground that is too steep") - 0.1, 2), round(rules[1] + at("b3", "The only fuel") - 0.1, 2), round(rules[2] + at("b4", "And the score") - 0.1, 2)]}]},
        # 2. The drivers.
        {"name": "l_lineup", "page": "film", "scene": "lineup", "beats": [{"vo": "c1", "vo_at": lineup[0], "more": more(lineup, "c2"), "pad": 1.4}]},
        # 3. What goes wrong, one tier at a time.
        {"name": "l_fast", "page": "campaign", "site": 3, "beats": [
            {"vo": "d1", "vo_at": 0.4, "pad": 1.2,
             "js": "A.showTitle(false); A.follow('%s'); A.seek(%.2f); %s" % (FAST, 104 - base.PACE * miss, chase),
             "overlay": [{"kind": "caption", "side": "left", "from": round(miss + 0.3, 2), "to": round(0.4 + at("d1", "Nine tries") - 0.1, 2), "text": "3 CM TOO FAR · NO POINTS"},
                         {"kind": "caption", "side": "left", "from": round(0.4 + at("d1", "Nine tries"), 2), "to": 99, "text": "9 TRIES · 1 ROCK"}]}]},
        {"name": "l_mid", "page": "campaign", "site": 3, "beats": [
            {"vo": "d2", "vo_at": 0.4, "pad": 1.2,
             "js": "A.showTitle(false); A.follow('%s'); A.seek(%.2f); %s" % (MID, 302 - base.PACE * stop, chase),
             "overlay": [{"kind": "caption", "side": "left", "from": round(stop + 0.3, 2), "to": round(0.4 + at("d2", "When the day ends") - 0.1, 2), "text": "TOO STEEP · 30 SAFETY STOPS"},
                         {"kind": "caption", "side": "left", "from": round(0.4 + at("d2", "When the day ends"), 2), "to": 99, "text": "72 M FROM HOME · SAMPLES COUNT HALF"}],
             "sfx": [{"t": 0.0, "kind": "cut"}]}]},
        {"name": "l_flagship", "page": "campaign", "site": 1, "beats": [
            {"vo": "d3", "vo_at": 0.5, "over": True, "until": "A.state.t >= 409",
             "js": "A.showTitle(false); A.HOLD.lost = 999; A.follow('%s'); A.seek(%.2f); "
                   "A.setCam('chase'); A.view.k = 1; A.view.snap = true; A.setSpeed(2); A.setPlaying(true);" % (FLAGSHIP, 409 - 3 * flat),
             "overlay": [{"kind": "caption", "side": "left", "from": round(0.5 + at("d3", "twenty-one samples"), 2), "to": round(flat - 0.05, 2),
                          "text": "21 SAMPLES ON BOARD · 13 M FROM HOME"}], "sfx": [{"t": 0.0, "kind": "cut"}]},
            {"min": 1.0, "thump": 0.0, "js": "A.setPlaying(false); A.seek(409); document.getElementById('mini').style.opacity = '0';"},
            {"vo": "d3b", "vo_at": 0.9, "min": 5.0, "pad": 1.4, "js": "A.startStory();", "sfx": [{"t": 0.0, "kind": "whoosh", "len": 1.3}]},
        ]},
        {"name": "l_quote", "page": "film", "scene": "quote", "beats": [
            {"vo": "d4", "vo_at": quote[0], "more": more(quote, "d4b"), "pad": 1.6,
             "cues": [round(quote[0] + at("d4", "Its own closing report") - 0.1, 2), round(quote[1] - 0.1, 2), round(quote[1] + at("d4b", "It did not fail") - 0.15, 2)]}]},
        # the sun: Gemini 4 Argon runs flat at tick 62 of site 3; a cut to tick 93, where the planner waits
        {"name": "l_energy", "page": "campaign", "site": 3, "beats": [
            {"vo": "d5", "vo_at": 0.5, "over": True, "min": round(max(0.6, 0.5 + at("d5", "flat") - 5.3), 2),
             "js": "A.showTitle(false); A.HOLD.lost = 999; A.HOLD.ref_wait = 999; A.follow('%s'); A.seek(48); A.setCam('map'); A.setPlaying(false);" % FLAT,
             "overlay": [{"kind": "caption", "from": 0.4, "to": 99, "text": "THE ONLY FUEL IS THE SUN"}]},
            {"until": "!!(A.story.active && A.story.active.kind === 'lost')", "js": "A.startStory();"},
            {"vo": "d5b", "vo_at": 2.2, "min": 5.6, "thump": 0.0},
            {"vo": "d5c", "vo_at": 0.5, "over": True, "until": "!!(A.story.active && A.story.active.kind === 'ref_wait')",
             "js": "A.card.style.transition = 'none'; A.stopStory(); A.seek(90.4); A.startStory();",
             "at": [{"t": 0.2, "js": "A.card.style.transition = '';"}], "sfx": [{"t": 0.0, "kind": "cut"}]},
            {"min": 4.6, "pad": 1.4},
        ]},
        # ... and one that gets it right: Gemini 4 Carbon's second run at site 2, five samples in thirty steps (ticks 212 to 238)
        {"name": "l_best", "page": "campaign", "site": 2, "beats": [
            {"vo": "d6", "vo_at": 0.5, "pad": 1.2, "js": "A.showTitle(false); A.follow('%s'); A.seek(207); %s" % (BEST, chase),
             "overlay": [{"kind": "caption", "side": "left", "from": round(0.5 + at("d6", "On this map"), 2), "to": round(0.5 + at("d6", "So the task") - 0.1, 2),
                          "text": "26 SAMPLES · HOME BEFORE DARK"}], "sfx": [{"t": 0.0, "kind": "cut"}]}]},
        # 4. The scoreboard, then how each lab's runs ended.
        {"name": "l_tiers", "page": "film", "scene": "tiers", "beats": [
            {"vo": "e1", "vo_at": tiers[0], "more": more(tiers, "e1b"), "pad": 1.6,
             "cues": [round(tiers[1] + at("e1b", "One comes within") - 0.1, 2), round(tiers[0] + at("e1", "The gold line") - 0.1, 2)]}]},
        {"name": "l_outcomes", "page": "film", "scene": "outcomes", "beats": [
            {"vo": "e2", "vo_at": labs[0], "more": more(labs, "e2b", "e2c", "e3", "e3b"), "pad": 1.8,
             "cues": [round(labs[0] + at("e2", "Gemini is all") - 0.1, 2), round(labs[1] - 0.1, 2), round(labs[2] - 0.1, 2),
                      round(labs[3] + at("e3", "Google's fast model") - 0.1, 2), round(labs[4] - 0.1, 2)]}]},
        # 5. The reference: what it is, how it ends its day, why it is a fair one to measure against.
        {"name": "l_planner", "page": "film", "scene": "planner", "beats": [
            {"vo": "f1", "vo_at": planner[0], "more": more(planner, "f2"), "pad": 1.6,
             "cues": [round(planner[1] + 0.05, 2), round(planner[1] + at("f2", "It learns how") - 0.1, 2),
                      round(planner[1] + at("f2", "It prices every leg") - 0.1, 2), round(planner[1] + at("f2", "And it searches") - 0.1, 2)]}]},
        {"name": "l_home", "page": "campaign", "site": 3, "beats": [
            {"vo": "f4", "vo_at": 0.5, "over": True, "until": "!!(A.story.active && A.story.active.kind === 'ref_home')",
             "js": "A.showTitle(false); A.HOLD.ref_home = 999; A.seek(372); A.setCam('map'); A.startStory();"},
            {"min": 5.0, "pad": 1.4},
        ]},
        {"name": "l_why", "page": "film", "scene": "why", "beats": [
            {"vo": "f3", "vo_at": why[0], "more": more(why, "f3b"), "pad": 1.8,
             "cues": [round(why[0] + at("f3", "It uses the same") - 0.1, 2), round(why[0] + at("f3", "It is plain code") - 0.1, 2),
                      round(why[0] + at("f3", "It gives the same score") - 0.1, 2), round(why[1] - 0.05, 2), round(why[1] + at("f3b", "And it can be beaten") - 0.1, 2)]}]},
        # 6. At scale.
        {"name": "l_worlds", "page": "film", "scene": "worlds", "beats": [
            {"vo": "g1", "vo_at": worlds[0], "more": more(worlds, "g1b", "g2"), "pad": 1.8,
             "cues": [round(worlds[1] - 0.1, 2), round(worlds[2] - 0.1, 2)]}]},
        # 7. A learned baseline.
        {"name": "l_rl", "page": "campaign", "site": 1, "beats": [
            {"vo": "h1", "vo_at": 0.5, "pad": 1.2, "js": "A.showTitle(false); A.follow('%s'); A.seek(112); %s" % (RL_ROVER, chase),
             "overlay": [{"kind": "caption", "side": "left", "from": round(0.5 + at("h1", "We trained"), 2), "to": 99, "text": "OUR RL AGENT · TRAINED FROM SCRATCH"}],
             "sfx": [{"t": 0.0, "kind": "cut"}]}]},
        {"name": "l_learning", "page": "film", "scene": "learning3", "beats": [
            {"vo": "h2", "vo_at": learn[0], "more": more(learn, "h2b"), "pad": 1.6,
             "cues": [round(learn[0] + at("h2", "On the campaign") - 0.15, 2), round(learn[1] + at("h2b", "We even trained") - 0.15, 2)]}]},
        {"name": "l_drivers", "page": "film", "scene": "drivers", "beats": [{"vo": "h3", "vo_at": 0.6, "pad": 1.6, "min": 9.0}]},
        # 8. Try it.
        {"name": "l_end", "page": "film", "scene": "end", "fade_out": 1.0, "beats": [
            {"vo": "i1", "vo_at": 0.6, "pad": round(2.4 + stretch, 3), "min": 8.0,
             "cues": [round(0.6 + at("i1", "and a live demo") - 0.1, 2), round(0.6 + at("i1", "Can your agent") - 0.15, 2)]}]},
    ]
