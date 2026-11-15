#!/usr/bin/env python3
"""Build the pitch deck: eleven slides, 1920 by 1080, as one PDF.

    uv run --no-project --python 3.12 --with playwright python -m tools.pitch_deck.make

Six slides are the demo video's own scenes (`tools/demo_video/film.html`) at their last frame,
drawn from the same numbers (`tools/demo_video/data.py`), so the deck and the film cannot
disagree. Two carry a frame of the finished film (`docs/demo-video/lightlag-traverse-demo.mp4`).
The rest are text, set below in the film's type and colours. Writes
`docs/pitch-deck/lightlag-traverse-deck.pdf` and one PNG per slide beside the build
(`tools/pitch_deck/build/`, not committed). Needs Google Chrome and ffmpeg. No model or API call.
"""

from __future__ import annotations

import html
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from tools.demo_video import data, storyboard

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
FILM = REPO / "tools" / "demo_video"
VIDEO = REPO / "docs" / "demo-video" / "lightlag-traverse-demo.mp4"
POSTER = REPO / "docs" / "demo-video" / "poster.jpg"
BUILD = HERE / "build"
OUT = REPO / "docs" / "pitch-deck" / "lightlag-traverse-deck.pdf"
SIZE = (1920, 1080)
CHROME_ARGS = ["--enable-gpu", "--ignore-gpu-blocklist", "--use-angle=metal", "--hide-scrollbars", "--force-color-profile=srgb"]

# The film's scenes used as slides, with every build-up already in: (file, scene, cues).
SCENES = [("quote", "quote", [0.3, 0.6, 0.9]), ("reference", "reference", [0.3, 0.6, 0.9]), ("results", "results3", [0.5]),
          ("farm", "farm", [0.5, 0.9]), ("learning", "learning3", [0.5, 0.9]), ("end", "end", [0.5, 0.9])]
# Frames of the finished film: (file, seconds in).
FRAMES = [("map", 15.0), ("flat", 9.5)]

STYLE = """
@page { size: 1920px 1080px; margin: 0; }
* { box-sizing: border-box; }
html, body { margin: 0; background: #0b0807; }
section { width: 1920px; height: 1080px; position: relative; overflow: hidden; page-break-after: always; break-after: page;
  background: #0b0807; color: #f3ead9; font-family: -apple-system, "Helvetica Neue", "Segoe UI", sans-serif; }
section.full img { width: 1920px; height: 1080px; display: block; }
.bar { position: absolute; left: 0; top: 0; width: 100%; height: 54px; background: #000; border-bottom: 2px solid #2e201a; }
.bar b { position: absolute; left: 24px; top: 7px; font: 700 34px "DIN Condensed", "Arial Narrow", sans-serif; letter-spacing: 6.8px; }
.bar b i { font-style: normal; font-size: 26px; color: #ff4a2f; letter-spacing: 5.2px; margin-left: 10px; }
.bar span { position: absolute; right: 28px; top: 12px; font: 700 26px "DIN Condensed", "Arial Narrow", sans-serif; letter-spacing: 4.2px; color: rgba(243,234,217,.62); }
h1 { position: absolute; left: 120px; top: 96px; margin: 0; font: 700 76px "DIN Condensed", "Arial Narrow", sans-serif; letter-spacing: 6.5px; }
h2 { position: absolute; left: 122px; top: 190px; margin: 0; font: 700 27px "DIN Condensed", "Arial Narrow", sans-serif; letter-spacing: 3.5px; color: rgba(243,234,217,.62); }
.col { position: absolute; }
.col h3 { margin: 0 0 18px; font: 700 34px "DIN Condensed", "Arial Narrow", sans-serif; letter-spacing: 4.4px; color: #ffb224; }
.col p, .col li { font-size: 31px; line-height: 44px; margin: 0 0 20px; color: #f3ead9; }
.col ul { margin: 0; padding: 0; list-style: none; }
.col li { padding-left: 34px; position: relative; }
.col li::before { content: ""; position: absolute; left: 0; top: 16px; width: 14px; height: 14px; background: #ffb224; }
.col li b, .col p b { color: #ffb224; font-weight: 600; }
.dim { color: rgba(243,234,217,.62) !important; }
.shot { position: absolute; border: 2px solid #2e201a; }
.note { position: absolute; left: 120px; right: 120px; bottom: 70px; padding: 24px 34px; background: #120c0a; border-left: 8px solid #ffb224;
  font-size: 28px; line-height: 40px; color: rgba(243,234,217,.82); }
.note code, .col code { font: 500 26px "SF Mono", Menlo, monospace; color: #b6e35a; }
.big { font: 700 108px "DIN Condensed", "Arial Narrow", sans-serif; letter-spacing: 2px; line-height: 1; }
.cap { font: 700 25px "DIN Condensed", "Arial Narrow", sans-serif; letter-spacing: 3px; color: rgba(243,234,217,.62); margin-top: 8px; }
.band { position: absolute; left: 0; right: 0; bottom: 0; height: 196px; background: #0b0807; border-top: 2px solid #2e201a; text-align: center; }
.band p { font-size: 44px; margin: 40px 0 0; }
.band small { display: block; margin-top: 22px; font: 700 30px "DIN Condensed", "Arial Narrow", sans-serif; letter-spacing: 6px; color: rgba(243,234,217,.62); }
"""


def run(command: List[str]) -> None:
    done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode != 0:
        raise SystemExit("{} failed:\n{}".format(command[0], (done.stderr or done.stdout)[-2000:]))


def bar(chapter: str) -> str:
    return '<div class="bar"><b>LIGHTLAG<i>TRAVERSE</i></b><span>{}</span></div>'.format(html.escape(chapter))


def slides(facts: Dict[str, Any]) -> List[str]:
    models, farm, final, plan = facts["models"], facts["farm"], facts["final"], facts["planner"]
    reference = facts["campaign"]["reference"]["score"]
    best = models["rows"][0]
    early = next(row for row in facts["campaign"]["baselines"] if "stop" in row["id"])
    open_home, lost = farm["lost_with_way_home_open"]
    image = lambda name: (BUILD / name).as_uri()              # noqa: E731
    full = lambda name: '<section class="full"><img src="{}"></section>'.format(image(name + ".png"))     # noqa: E731
    return [
        # 1. Title
        # the film's own title frame, with what the entry is and whose it is in a band over the page's legend
        '<section><img src="{poster}" style="position:absolute;inset:0;width:1920px;height:1080px;object-fit:cover">'
        '<div class="band"><p>A Mars rover campaign where frontier agents lose to a planner</p>'
        '<small>AFTERQUERY · BREAK THE AGENT · JUNCTION 2026 &nbsp;·&nbsp; KRISTJÁN · SÖLVI · MANH</small></div></section>'.format(poster=POSTER.as_uri()),
        # 2. The task
        '<section>{bar}<h1>ONE ROVER · THREE SITES · ONE SCORE</h1><h2>FIVE TOOLS OVER MCP · EVERY FORMULA PUBLISHED · NO RESET, NO PRACTICE RUN</h2>'
        '<div class="col" style="left:120px;top:280px;width:800px"><ul>'
        '<li><b>Light lag.</b> Every command lands 3 ticks late, and every position fix is 3 ticks old.</li>'
        '<li><b>The ground fights back.</b> Wheels slip on sand and slopes. Ground steeper than 0.36 stops the rover and wipes its queued commands.</li>'
        '<li><b>The only fuel is the sun.</b> A battery at zero ends the rover, and that site scores nothing.</li>'
        '<li><b>The score.</b> The value of the samples, times 1 at the lander, ½ alive elsewhere, 0 if the battery ran out, over all the value there was.</li>'
        '</ul></div>'
        '<img class="shot" src="{map}" style="left:980px;top:290px;width:820px;height:461px;object-fit:cover;object-position:left">'
        '<div class="col" style="left:980px;top:775px;width:820px"><p class="dim" style="font-size:25px;line-height:36px">One site: 600 m by 400 m, 420 ticks, '
        'about 46 targets, most with deadlines. Nobody can reach them all, so the task is which ones, in what order, and home before the battery dies.</p></div>'
        '</section>'.format(bar=bar("THE ENVIRONMENT"), map=image("map.jpg")),
        # 3. What goes wrong
        '<section>{bar}<h1>13 METRES FROM HOME</h1><h2>AN AUTOPILOT WRITTEN BY CLAUDE OPUS, AT THE FIRST SITE · 21 SAMPLES ON BOARD · SCORE FOR THE SITE: 0</h2>'
        '<img class="shot" src="{flat}" style="left:120px;top:270px;width:1000px;height:562px;object-fit:cover;object-position:left">'
        '<div class="col" style="left:1170px;top:270px;width:640px"><h3>WHY THE AGENTS LOSE</h3><ul>'
        '<li><b>Worse routes.</b> Claude\'s runs that came home took 28 to 53% fewer samples than the reference.</li>'
        '<li><b>Flat batteries with home in reach.</b> {share}% of Claude\'s lost rovers on 300 fresh worlds still had a way home. Waiting for the sun would have saved them.</li>'
        '<li><b>Write once, look later.</b> Their autopilots played a whole site in 8 to 30 seconds, before the agent had looked.</li>'
        '</ul></div>'
        '<div class="note" style="bottom:60px">The agents do not fail at coding: every one wrote a working autopilot within minutes. They fail at planning the day.</div>'
        '</section>'.format(bar=bar("WHY CLAUDE STRUGGLES"), flat=image("flat.jpg"), share=round(open_home / lost * 100)),
        full("quote"), full("reference"), full("results"), full("farm"), full("learning"),
        # 9. Reward integrity
        '<section>{bar}<h1>HARD TO GAME</h1><h2>THE SCORE IS COMPUTED FROM THE ROVER\'S TRUE STATE, IN THE SIMULATOR\'S OWN CONTAINER, AFTER THE AGENT\'S HAS STOPPED</h2>'
        '<div class="col" style="left:120px;top:290px;width:760px"><h3>NO SHORTCUTS IN THE SCORE</h3>'
        '<div style="display:flex;gap:70px;margin-bottom:30px"><div><div class="big">0.000</div><div class="cap">DOING NOTHING</div></div>'
        '<div><div class="big">{early:.3f}</div><div class="cap">STOPPING AFTER ONE SITE</div></div></div>'
        '<ul><li>A flat battery scores 0 for that site.</li><li>Ending away from the lander halves it.</li>'
        '<li>A sample counts only within 2.5 m of a target, by the true position.</li></ul></div>'
        '<div class="col" style="left:980px;top:290px;width:820px"><h3>WE ATTACKED IT FIRST</h3>'
        '<div style="display:flex;gap:70px;margin-bottom:30px"><div><div class="big">27</div><div class="cap">ATTACKS FROM INSIDE THE AGENT\'S CONTAINER</div></div>'
        '<div><div class="big" style="color:#ffb224">0</div><div class="cap">CHANGED THE REWARD</div></div></div>'
        '<ul><li>Forged reward files, a perfect fake result and a grader that always passes.</li>'
        '<li>Hidden tools, guessed routes, 1,147 ports, the finish route.</li>'
        '<li>36 malformed commands, the delay, twelve sessions at once.</li></ul></div>'
        '<div class="note"><b style="color:#ffb224">One known limit.</b> The worlds are fixed by seeds that are public with the code. Change <code>LIGHTLAG_SEEDS</code> to any integers: '
        'the reference averages {fresh:.3f} on 300 worlds it had never seen.</div>'
        '</section>'.format(bar=bar("REWARD INTEGRITY"), early=early["score"], fresh=farm["reference_mean"]),
        # 10. How it was built
        '<section>{bar}<h1>BUILT ON MODAL, WITH CODEX AND CLAUDE CODE</h1><h2>UNDER HUMAN DIRECTION · EVERY RESULT LINKED TO ITS CODE, ITS RUNS AND ITS FAILURES IN THE REPOSITORY</h2>'
        '<div class="col" style="left:120px;top:290px;width:540px"><h3 style="color:#b6e35a">MODAL</h3><ul>'
        '<li>The rollout farm: 1,500 missions in 7 minutes on up to {containers} containers.</li>'
        '<li>{missions:,} training missions for the small controllers.</li>'
        '<li>Model-written programs run isolated from our machines.</li>'
        '<li>The live demo: pick any world, watch eight rovers drive it.</li></ul></div>'
        '<div class="col" style="left:700px;top:290px;width:540px"><h3>CODEX</h3><ul>'
        '<li>Evaluation, learning and experiment orchestration.</li>'
        '<li>Policies frozen before fresh tests; failures kept, not hidden.</li>'
        '<li>Independent audits of the reported statistics.</li>'
        '<li>The learned planner: Extra Trees, {gain:+.2f} points.</li></ul></div>'
        '<div class="col" style="left:1280px;top:290px;width:540px"><h3 style="color:#9fd8ff">CLAUDE CODE</h3><ul>'
        '<li>The Traverse simulator and the reference planner.</li>'
        '<li>The farm, the live site, the replay viewer.</li>'
        '<li>The three-lab comparison and the integrity review.</li>'
        '<li>The film and this deck.</li></ul></div>'
        '<div class="note">Live: <code>{url}</code><br>Rerun: <code>harbor run -p harbor/lightlag-traverse-campaign -a oracle</code> gives {reference:.6f}</div>'
        '</section>'.format(bar=bar("HOW IT WAS BUILT"), containers=farm["containers"], missions=final["training_missions"],
                            gain=plan["first"]["gain"], url=storyboard.LIVE_URL, reference=reference),
        full("end"),
    ]


def main() -> int:
    from playwright.sync_api import sync_playwright

    if not VIDEO.exists():
        raise SystemExit("the film is not built: {}".format(VIDEO.relative_to(REPO)))
    BUILD.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    facts = {**data.build(), **data.extras(), "live_url": storyboard.LIVE_URL}
    for name, at in FRAMES:
        run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "{:.2f}".format(at), "-i", str(VIDEO), "-frames:v", "1", "-q:v", "2", str(BUILD / (name + ".jpg"))])
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True, args=CHROME_ARGS)
        context = browser.new_context(viewport={"width": SIZE[0], "height": SIZE[1]}, device_scale_factor=1)
        clocked = browser.new_context(viewport={"width": SIZE[0], "height": SIZE[1]}, device_scale_factor=1)
        clocked.add_init_script((FILM / "clock.js").read_text(encoding="utf-8"))
        for name, scene, cues in SCENES:              # each scene, stepped past its last build-up
            page = clocked.new_page()
            page.add_init_script("window.FILM_DATA = {};".format(json.dumps(facts, separators=(",", ":"))))
            page.goto((FILM / "film.html").as_uri() + "?scene=" + scene)
            page.wait_for_function("window.__scene !== undefined && document.fonts.status === 'loaded'", polling=50)
            page.evaluate("cues => { window.__scene.duration = 12; window.__scene.cues = cues; window.__film.step(34); "
                          "window.__film.step(14000); window.__film.step(34); }", cues)
            page.screenshot(path=str(BUILD / (name + ".png")), type="png")
            page.close()
        pages = slides(facts)
        deck = BUILD / "deck.html"
        deck.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Lightlag Traverse</title><style>{}</style></head>'
                        '<body>{}</body></html>'.format(STYLE, "\n".join(pages)), encoding="utf-8")
        page = context.new_page()
        page.goto(deck.as_uri())
        page.wait_for_function("document.fonts.status === 'loaded' && [...document.images].every(image => image.complete)", polling=50)
        for number in range(len(pages)):               # one picture per slide, to look at
            page.locator("section").nth(number).screenshot(path=str(BUILD / "slide-{:02d}.png".format(number + 1)))
        page.pdf(path=str(OUT), width="{}px".format(SIZE[0]), height="{}px".format(SIZE[1]), print_background=True, prefer_css_page_size=True)
        browser.close()
    print("{} slides, {:.1f} MB: {}".format(len(pages), OUT.stat().st_size / 1e6, OUT.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
