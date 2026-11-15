"""The demo video's third cut: the second cut's story with Sunday morning's results in it.

    LIGHTLAG_STORYBOARD=storyboard3 uv run --no-project --python 3.12 --with playwright python -m tools.demo_video.make all

The four driving shots, the quotation and the reference slide are the second cut's (`storyboard.py`),
frame for frame and word for word. What changes, and why:

- **results**: all 25 campaign runs by nine models from three labs (Manh's tier comparison), not
  Claude's seven. Google's top model comes within 0.004 of the reference, and the slide says so.
- **the farm**: one sentence shorter, and a line for the other labs' programs on the same worlds.
- **learning**: Sölvi's final controllers on held-out worlds and on the campaign, in place of the
  pilot's development curve; then the Extra Trees model that picks the reference planner's strategy.
- **the end card**: the live site drives eight rovers now.

`storyboard.py` and the scenes it uses are untouched, so the second cut and Manh's cut, which is built
on top of it, still build as before. The second cut's three replaced lines stay in LINES (they are
spoken into `build/voice/` and never laid in the film) so that its shots can still be timed.
"""

from __future__ import annotations

from typing import Any, Dict, List

from . import data
from . import storyboard as base

VOICE, LIMIT_SECONDS, LIVE_URL, TRAVEL, PACE, POSTER = (base.VOICE, base.LIMIT_SECONDS, base.LIVE_URL, base.TRAVEL,
                                                        base.PACE, base.POSTER)

LINES: Dict[str, str] = dict(base.LINES)
LINES.update({
    "s2": "The reference scores zero point four eight. Twenty-five runs by nine models all finish below it. "
          "Only Google's top model comes close, at zero point four seven. Doing nothing scores zero.",
    "m3": "On Modal, six of Claude's programs replayed three hundred fresh worlds each. "
          "The reference scored higher ninety-nine times in a hundred and never lost a rover.",
    "m4": "A small policy trained from scratch learns too: from eight to thirty-six percent on unseen worlds, "
          "and past every Claude run on the campaign. "
          "Even a model trained to pick our planner's strategy gained less than half a point.",
})

SUBTITLES: Dict[str, str] = dict(base.SUBTITLES)
SUBTITLES.update({
    "s2": "The reference scores 0.48. Twenty-five runs by nine models all finish below it. "
          "Only Google's top model comes close, at 0.47. Doing nothing scores zero.",
    "m3": "On Modal, six of Claude's programs replayed 300 fresh worlds each. "
          "The reference scored higher 99 times in 100 and never lost a rover.",
    "m4": "A small policy trained from scratch learns too: from 8% to 36% on unseen worlds, "
          "and past every Claude run on the campaign. "
          "Even a model trained to pick our planner's strategy gained less than half a point.",
})

KEPT = ("cold", "world", "ground", "energy", "quote", "reference", "end")


class Words(base.Words):
    """As the second cut's, over this cut's lines."""

    def at(self, line: str, phrase: str) -> float:
        text, index, seen = LINES[line], LINES[line].index(phrase), 0
        for word in self.words[line]:
            if seen >= index and word["t0"] is not None:
                return float(word["t0"])
            seen += len(word["w"]) + (1 if word["space"] else 0)
        raise ValueError("{!r} is not spoken in line {}: {!r}".format(phrase, line, text))


def facts() -> Dict[str, Any]:
    """What this cut's slides need beyond `data.build()`."""
    return data.extras()


def shots(durations: Dict[str, float], words: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    say = Words(words)
    kept = {shot["name"]: shot for shot in base.shots(durations, words) if shot["name"] in KEPT}
    cue = lambda line, phrase, lead=0.0: round(0.4 + say.at(line, phrase) + lead, 2)      # noqa: E731
    totals = cue("m3", "The reference scored", -0.1)
    return [kept[name] for name in KEPT[:-1]] + [
        # 7. Results on the campaign, three labs: the callout comes up as the voice names the one model that
        #    comes close, and "do nothing" lights when it is said.
        {"name": "results", "page": "film", "scene": "results3", "beats": [
            {"vo": "s2", "vo_at": 0.4, "pad": 0.5, "min": 7.0,
             "cues": [cue("s2", "Only Google's", -0.15), cue("s2", "Doing nothing", -0.15)]}]},
        # 8. Modal: the 300-world comparison. The totals come as the voice gets to them; the note on who won
        #    the few worlds follows on its own, for whoever pauses.
        {"name": "farm", "page": "film", "scene": "farm", "beats": [
            {"vo": "m3", "vo_at": 0.4, "pad": 0.6, "min": 9.0, "cues": [totals, round(totals + 1.4, 2)]}]},
        # 9. Learning: the held-out result, then the campaign, then learning on top of the planner itself.
        {"name": "learning", "page": "film", "scene": "learning3", "beats": [
            {"vo": "m4", "vo_at": 0.4, "pad": 0.7,
             "cues": [cue("m4", "and past every", -0.15), cue("m4", "Even a model", -0.15)]}]},
        # 10. The end card, held a little shorter than in the second cut to stay inside two minutes.
        dict(kept["end"], beats=[dict(kept["end"]["beats"][0], pad=1.1)]),
    ]
