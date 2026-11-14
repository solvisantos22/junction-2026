"""Deterministic silent screen recording of the verified offline decision page.

Only presentation captions are injected. Existing controls advance both saved
replays; the viewer source, embedded data and evidence files are never changed.
Output and temporary work directories must be new. No remote asset is allowed.
"""

import argparse
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True

DESIGN_COMMIT = "b115cfcbce6106c0bfb7a0ac75357e0516c9d102"
VIEWER = "viewer/decisions.html"
DESIGN = "docs/superpowers/specs/2026-11-14-lightlag-demo-recording.md"
ACTUAL = "docs/lightlag-runs/rush-noisy-seed504-delay3-opus-5-5/artifacts/evaluator/replay.json"
STOP = "docs/lightlag-audits/fixed-seeds501-504/rush-noisy-seed504-delay3-opus-5-5/stop-check.json"
SUMMARY = "docs/lightlag-runs/fixed-seeds501-504-summary.json"
WIDTH, HEIGHT, FPS, SECONDS = 1920, 1080, 12, 62
PHASES = [
    (0, 6, "Selected case, complete context", "One saved noisy mission. Three ticks of delay; 50-tick horizon; 100 starting energy."),
    (6, 16, "Tick 25: return still queued", "Accepted drives will execute at ticks 26 and 27. Call 21 adds 8.1 m + a sample: 11.1 action energy."),
    (16, 22, "Tick 27: the return completes", "Both rovers reach home at tick 27. The actual run still has another excursion queued for ticks 29–31."),
    (22, 25, "The extra excursion executes", "The actual run leaves base and samples d1. The post-hoc branch sends no new commands after call 20."),
    (25, 34, "Science is not final reward", "The actual run has collected 9 sample points. Its battery still has to last through the mission horizon."),
    (34, 38, "Tick 47: energy exhausted", "The actual rover dies away from base. The checked continuation remains alive at home."),
    (38, 43, "Tick 50: the scored result", "Actual: 0/10. Post-hoc continuation: 6/10, alive at home, with 9.33 battery."),
    (43, 54, "The fixed idle bill", "Every 50-tick survivor pays 50 × 0.5 = 25 idle energy. Returning home neither recharges nor stops the clock."),
    (54, 62, "A checked branch, not a new trial", "This post-hoc continuation is not a fresh successful model attempt. The selected case does not estimate failure prevalence."),
]
FRAME_CHECKS = {"opening": 2, "queued_return": 12, "home_at_27": 20,
                "death_at_47": 35, "final_at_50": 41, "idle_bill": 50, "closing": 59}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_text())


def verify_inputs(repo):
    paths = (VIEWER, DESIGN, ACTUAL, STOP, SUMMARY)
    hashes = {}
    for relative in paths:
        current = (repo / relative).read_bytes()
        committed = subprocess.check_output(["git", "show", DESIGN_COMMIT + ":" + relative], cwd=repo)
        if current != committed:
            raise RuntimeError("Frozen recording input changed: " + relative)
        hashes[relative] = sha(current)
    html = (repo / VIEWER).read_text()
    payload_text = re.search(r'<script id="decision-data" type="application/json">(.*?)</script>', html, re.S).group(1)
    payload = json.loads(payload_text)
    case = next(c for c in payload["cases"] if c["id"] == "rush-noisy-504")
    actual, branch = case["actual"]["replay"], case["alternative"]["replay"]
    assert actual == read(repo / ACTUAL)
    stop = next(r for r in read(repo / STOP)["counterfactuals"] if r["after_call"] == 20)
    assert branch["result"] == stop["result"] and branch["states"][-1]["battery"] == stop["final_battery"] == 9.33
    assert case["decision"]["call"] == 21 and case["decision"]["tick"] == 25
    assert case["alternative"]["cutoff_call"] == 20
    assert actual["states"][:28] == branch["states"][:28]
    assert actual["result"]["raw_score"] == 0 and branch["result"]["raw_score"] == 6
    assert actual["result"]["max_available_value"] == branch["result"]["max_available_value"] == 10
    assert not actual["result"]["alive"] and not actual["result"]["at_base"]
    assert branch["result"]["alive"] and branch["result"]["at_base"]
    assert case["actual"]["death_tick"] == 47 and case["alternative"]["death_tick"] is None
    base, radius = actual["world"]["base"], actual["config"]["base_radius"]
    assert math.dist(actual["states"][25]["position"], base) > radius
    assert math.dist(actual["states"][27]["position"], base) <= radius
    pending = [c for c in branch["commands"] if c["sent_tick"] <= 25 < c["execute_tick"]]
    assert [c["execute_tick"] for c in pending] == [26, 27]
    added = [c for c in actual["commands"] if c["sent_tick"] == 25]
    assert [c["execute_tick"] for c in added] == [29, 30, 31]
    assert [c["command"]["action"] for c in added] == ["drive", "drive", "sample"]
    assert math.isclose(sum(c["command"].get("metres", 0) for c in added), 8.1)
    assert actual["config"]["drive_cost"] == 1 and actual["config"]["sample_cost"] == 3
    assert actual["config"]["max_ticks"] * actual["config"]["idle_cost"] == 25
    groups = read(repo / SUMMARY)["paired_aggregates"]
    counts = {key: sum(g[key] for g in groups) for key in ("model_wins", "ties", "reference_wins")}
    assert counts == {"model_wins": 3, "ties": 2, "reference_wins": 3}
    evidence = {"case": case["id"], "tick25_at_base": False, "queued_return_execution_ticks": [26, 27],
                "home_tick": 27, "additional_action_energy": 11.1, "actual_death_tick": 47,
                "actual_final_raw_score": 0, "maximum": 10, "post_hoc_cutoff_call": 20,
                "post_hoc_final_raw_score": 6, "post_hoc_final_battery": 9.33,
                "post_hoc_alive_at_home": True, "idle_energy_for_full_horizon_survival": 25,
                "original_eight_model_counts": counts}
    return hashes, sha(payload_text.encode()), evidence


def tick_at(t):
    if t < 16:
        return 25
    if t < 17:
        return 26
    if t < 22:
        return 27
    if t < 34:
        return min(46, 28 + int((t - 22) * 19 / 12))
    if t < 36:
        return 47
    if t < 37:
        return 48
    if t < 38:
        return 49
    return 50


def ease(value):
    value = min(1, max(0, value))
    return value * value * (3 - 2 * value)


def scroll_at(t, tracks, chart):
    if t < 6:
        return 0
    if t < 8:
        return round(tracks * ease((t - 6) / 2))
    if t < 43:
        return tracks
    if t < 46:
        return round(tracks + (chart - tracks) * ease((t - 43) / 3))
    return chart


OVERLAY = """
() => {
  const style = document.createElement('style');
  style.textContent = `
  .recording-caption{position:fixed;z-index:1000;top:38px;width:284px;padding:22px;
    background:#fffefa;border:1px solid #dcded4;border-radius:12px;color:#20302f;
    font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;box-shadow:0 4px 24px #20302f08}
  #recording-left{left:24px}#recording-right{right:24px}
  .recording-caption .label{font-size:12px;font-weight:750;letter-spacing:.09em;text-transform:uppercase;color:#65736e}
  .recording-caption h2{font-size:28px;line-height:1.15;letter-spacing:-.035em;margin:14px 0 18px}
  .recording-caption p{font-size:20px;line-height:1.4;margin:13px 0 0}
  .recording-caption .detail{font-size:15px;line-height:1.45;color:#65736e}
  .recording-caption .rule{height:1px;background:#dcded4;margin:20px 0}
  .recording-caption .counts{font-size:27px;font-weight:700;letter-spacing:-.04em}
  .recording-caption .actual{color:#be4c29}.recording-caption .branch{color:#14766d}
  .recording-caption .clock{font-family:ui-monospace,monospace;font-size:22px}
  `;
  document.head.appendChild(style);
  const left = document.createElement('aside'); left.id='recording-left'; left.className='recording-caption';
  left.innerHTML='<div class="label">Recorded replay · selected case</div><h2 id="recording-title"></h2><p id="recording-copy"></p><div class="rule"></div><div class="label">rush_noisy · seed 504</div><p class="detail">Saved evidence, synchronized ticks.<br>Silent first cut for team review.</p>';
  const right = document.createElement('aside'); right.id='recording-right'; right.className='recording-caption';
  right.innerHTML='<div class="label">Original eight model attempts</div><p class="counts">3 wins · 2 ties<br>3 deficits</p><p class="detail">Against the frozen original reference. This selected case does not estimate failure prevalence.</p><div class="rule"></div><div class="label">Synchronized saved replay</div><p class="clock" id="recording-clock"></p><p class="detail"><span class="actual">Left: actual model run.</span><br><span class="branch">Right: checked post-hoc continuation.</span></p><div class="rule"></div><p class="detail">Solid marker: evaluator truth.<br>Purple ring: delivered telemetry.<br><br>Sources: viewer/decisions.html<br>and the accompanying README.</p>';
  document.body.append(left,right);
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chrome", required=True, type=Path)
    parser.add_argument("--ffmpeg", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--work-dir", required=True, type=Path)
    args = parser.parse_args()
    repo = next(p for p in Path(__file__).resolve().parents if (p / "AGENTS.md").exists())
    hashes, payload_hash, evidence = verify_inputs(repo)
    args.output.mkdir(parents=True, exist_ok=False)
    args.work_dir.mkdir(parents=True, exist_ok=False)
    output, work = args.output.resolve(), args.work_dir.resolve()
    script_hash = sha(Path(__file__).read_bytes())
    encoder_version = subprocess.check_output([str(args.ffmpeg), "-version"], text=True).splitlines()[0]
    video_path = output / "lightlag-selected-case.webm"
    encode = [str(args.ffmpeg), "-hide_banner", "-loglevel", "warning", "-n",
              "-f", "image2pipe", "-c:v", "mjpeg", "-framerate", str(FPS), "-i", "pipe:0",
              "-an", "-c:v", "libvpx-vp9", "-pix_fmt", "yuv420p", "-b:v", "0", "-crf", "28",
              "-deadline", "realtime", "-cpu-used", "4", "-threads", "4", str(video_path)]
    from playwright.sync_api import sync_playwright
    js_errors, network_requests, captured = [], [], []
    unique_frames = 0
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=str(args.chrome), headless=True,
                    args=["--disable-background-networking", "--disable-component-update", "--disable-sync"])
        browser_version = browser.version
        context = browser.new_context(viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=1,
                                      reduced_motion="reduce")

        def route(request):
            if request.request.url.startswith(("file:", "data:", "blob:")):
                request.continue_()
            else:
                network_requests.append(request.request.url.split("?")[0])
                request.abort()

        context.route("**/*", route)
        page = context.new_page()
        page.on("pageerror", lambda error: js_errors.append(str(error)))
        page.goto((repo / VIEWER).resolve().as_uri(), wait_until="load")
        page.get_by_role("tab").nth(2).click()
        assert page.locator("#case-meta").text_content() == "rush noisy / seed 504 / delay 3"
        assert page.locator("#tick-value").inner_text() == "25"
        page.evaluate(OVERLAY)
        positions = page.evaluate("""() => ({tracks:Math.round(document.querySelector('.controls').getBoundingClientRect().top+scrollY-20),chart:Math.round(document.querySelector('.battery-section').getBoundingClientRect().top+scrollY-70)})""")
        assert page.evaluate("document.documentElement.scrollWidth") == WIDTH
        encoded_log = (work / "encoder.log").open("wb")
        process = subprocess.Popen(encode, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=encoded_log)
        prior_key, jpeg, phase_seen = None, None, -1
        try:
            for frame in range(FPS * SECONDS):
                t = frame / FPS
                phase = next(i for i, (start, end, _, _) in enumerate(PHASES) if start <= t < end)
                tick = tick_at(t)
                scroll = scroll_at(t, positions["tracks"], positions["chart"])
                # At the first advancing tick the new state is 26; keep the caption precise.
                title = "The queued return executes" if 16 <= t < 17 else PHASES[phase][2]
                key = (phase, tick, scroll, title)
                if key != prior_key:
                    page.evaluate("""({tick,scroll,title,copy}) => {
                        const slider=document.getElementById('tick-slider');
                        slider.value=tick; slider.dispatchEvent(new Event('input',{bubbles:true}));
                        window.scrollTo({top:scroll,behavior:'instant'});
                        document.getElementById('recording-title').textContent=title;
                        document.getElementById('recording-copy').textContent=copy;
                        document.getElementById('recording-clock').textContent='TICK '+String(tick).padStart(2,'0')+' / 50';
                    }""", {"tick": tick, "scroll": scroll, "title": title, "copy": PHASES[phase][3]})
                    assert page.locator("#tick-value").inner_text() == str(tick).zfill(2)
                    jpeg = page.screenshot(type="jpeg", quality=95, animations="disabled")
                    unique_frames += 1
                    prior_key = key
                process.stdin.write(jpeg)
                if phase != phase_seen:
                    print(json.dumps({"video_seconds": t, "caption": title, "tick": tick}), flush=True)
                    phase_seen = phase
            process.stdin.close()
            result = process.wait(timeout=60)
            if result:
                raise RuntimeError("Encoder failed; inspect the isolated work-directory log")
        finally:
            if process.poll() is None:
                process.kill()
            encoded_log.close()
        assert sha(page.locator("#decision-data").text_content().encode()) == payload_hash
        assert not js_errors and not network_requests
        page.close()

        # Decode the final WebM in real Chrome, inspect metadata, seek checkpoints,
        # and advance playback in real wall time. Frames remain temporary QA aids.
        preview = work / "playback.html"
        preview.write_text('<!doctype html><meta charset="utf-8"><style>body{margin:0;background:black}video{display:block;width:1920px;height:1080px}</style><video muted preload="auto" src="' + video_path.as_uri() + '"></video>')
        player = context.new_page()
        player.on("pageerror", lambda error: js_errors.append(str(error)))
        player.goto(preview.as_uri())
        player.wait_for_function("document.querySelector('video').readyState >= 2")
        metadata = player.locator("video").evaluate("v=>({duration:v.duration,width:v.videoWidth,height:v.videoHeight,readyState:v.readyState})")
        assert metadata["width"] == WIDTH and metadata["height"] == HEIGHT
        assert abs(metadata["duration"] - SECONDS) < 0.15
        for label, seconds in FRAME_CHECKS.items():
            player.locator("video").evaluate("""(v,t) => new Promise(resolve=>{v.pause();v.addEventListener('seeked',resolve,{once:true});v.currentTime=t;})""", seconds)
            player.wait_for_timeout(100)
            path = work / ("decoded-" + label + ".png")
            player.screenshot(path=str(path), animations="disabled")
            captured.append({"label": label, "seconds": seconds, "tick": tick_at(seconds), "decoded_frame_sha256": sha(path.read_bytes())})
        player.locator("video").evaluate("async v=>{v.currentTime=33;await v.play();}")
        player.wait_for_timeout(1300)
        progress = player.locator("video").evaluate("v=>({time:v.currentTime,paused:v.paused,error:v.error?{code:v.error.code,message:v.error.message}:null})")
        assert progress["time"] > 34 and not progress["paused"] and progress["error"] is None
        player.locator("video").evaluate("v=>{v.pause();v.currentTime=61.5;}")
        player.wait_for_timeout(100)
        player.locator("video").evaluate("v=>v.play()")
        player.wait_for_function("document.querySelector('video').ended", timeout=4000)
        assert not js_errors and not network_requests
        context.close()
        browser.close()
    assert verify_inputs(repo)[0] == hashes
    assert sha(Path(__file__).read_bytes()) == script_hash
    record = {"schema_version": 1, "design_commit": DESIGN_COMMIT,
              "input_sha256": hashes, "payload_sha256": payload_hash, "recording_script_sha256": script_hash,
              "script_path": "tools/lightlag_experiments/overnight_demo_video.py",
              "video": {"file": video_path.name, "sha256": sha(video_path.read_bytes()), "bytes": video_path.stat().st_size,
                        "format": "WebM / VP9, yuv420p, silent", "fps": FPS, "frames": FPS * SECONDS,
                        "expected_seconds": SECONDS, "decoded_metadata": metadata},
              "software": {"python": sys.version.split()[0], "playwright": importlib.metadata.version("playwright"),
                           "chrome": browser_version, "encoder": encoder_version,
                           "encoder_sha256": sha(args.ffmpeg.read_bytes())},
              "capture": {"method": "Existing UI slider, deterministic synchronized ticks; camera scroll and side captions only",
                          "source_screenshot_format": "JPEG quality 95", "unique_browser_frames": unique_frames,
                          "user_profile_used": False, "network_asset_requests": network_requests,
                          "javascript_errors": js_errors, "unchanged_embedded_payload": True},
              "evidence_assertions": evidence,
              "storyboard": [{"start": a, "end": b, "title": title, "caption": copy} for a, b, title, copy in PHASES],
              "decoded_checkpoints": captured,
              "playback_check": {"advanced_in_real_time": True, "ended_at_duration": True, "error": None},
              "limits": ["Selected recorded replay, not a live model rollout or failure-prevalence estimate.",
                         "Post-hoc no-new-command continuation, not a fresh successful model trial.",
                         "Tick-stepped editorial timing, not real-time mission timing.",
                         "WebM/VP9 playback verified in local Chrome; no external submission or upload."],
              "paid_inference_calls": 0}
    (output / "verification.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    narration = ["# Suggested narration for the silent first cut", "", "No speech or audio track is embedded in the video.", ""]
    for start, end, title, copy in PHASES:
        narration.append(f"{start:02d}–{end:02d} seconds — {title}. {copy}")
        narration.append("")
    narration += ["The opening/ending context remains: the original eight model attempts had three wins, two ties and three deficits against the original frozen reference. This is one selected example, not an estimate of failure prevalence.", ""]
    (output / "narration.md").write_text("\n".join(narration))
    print(json.dumps({"complete": True, "video_bytes": record["video"]["bytes"],
                      "duration": metadata["duration"], "dimensions": [WIDTH, HEIGHT],
                      "decoded_checkpoint_frames": len(captured)}), flush=True)


if __name__ == "__main__":
    main()
