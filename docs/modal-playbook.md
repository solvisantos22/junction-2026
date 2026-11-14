# Using our Modal credits: agent runs, mission farms, training

Saturday 14 November, about 23:00 Helsinki. Kristján / Claude Code, for Manh and Sölvi. Three ways the team uses Modal, with the commands, what to check first, and what to record for the Modal prize ($2,000 + $3,000 credits; judged on effective use 40%, ambition 25%, impact 20%, a live deployed demo 15%).

## 1. Harbor agent runs on Modal (for the MAX task, or any of our tasks)

Harbor can run trials in cloud sandboxes instead of local Docker, and Modal is one of its environments: `--env modal`, with `-n` (`--n-concurrent`) running several trials at once. That means six agent runs in parallel instead of one at a time, and no OpenCode install over the venue network, which timed out six times on Saturday evening.

**First check the flags in your installed Harbor** (they come from Harbor's docs, not yet tried on this team's tasks):

```sh
harbor run --help | grep -i -A2 "env\|concurrent"
```

**Then one cheap reference run, before any agent:**

```sh
harbor run -p harbor/<task> -a oracle --env modal
```

It must give the same reward as in local Docker (the campaign task's oracle gives 0.476257). **Our Traverse tasks run the simulator in a second container beside the agent's**, and it is not yet known whether Harbor's Modal environment runs that two-container setup. If the oracle run fails or scores differently, use local Docker for agent runs (one at a time, `--agent-setup-timeout-multiplier 3` on a slow network).

**If the oracle run matches, the agents:**

```sh
harbor run -p harbor/<task> -a opencode -m anthropic/claude-opus-5-5 --ak version=1.19.5 \
    --env-file .env --env modal -n 6
```

- Modal uses your own login (`modal setup`, which writes `~/.modal.toml`); the runs bill your workspace's credits. Never paste a token into a chat or a file in the repo.
- The model key stays in the gitignored `.env`, passed with `--env-file`. Model API calls are paid separately from Modal (about $0.4–1.5 per agent run on Saturday's tasks).
- **Judges rerun in local Docker**, so the task must keep working there. Modal is for our own runs.

## 2. Thousands of missions: the Traverse farm

[`tools/traverse_farm/`](../tools/traverse_farm/), with details in [`traverse-farm.md`](traverse-farm.md). It plays missions in parallel on up to 100 one-core containers. Model-written programs run only inside Modal's containers; the local command refuses them.

```sh
pip install modal && modal setup        # once, with your own workspace
modal run tools/traverse_farm/modal_app.py::evaluate --policies "pilot,greedy" --seeds 600-699 --out <folder>
modal run tools/traverse_farm/modal_app.py::evaluate --policies "manh_max,pilot,program:<path>/policy.py" \
    --seeds 600-699 --map max --baseline manh_max --out <folder>         # Manh's MAX map
modal run tools/traverse_farm/modal_app.py::evaluate ... --analyse      # + the point of no return for every rover
modal run tools/traverse_farm/modal_app.py::replays --policies "pilot,..." --seeds 871 --out <folder>   # whole missions for the demo pages
```

- **It reproduces exactly:** 16 of 16 missions identical to a laptop; the campaign reference identical to Harbor; `manh_max` identical to Manh's MAX table on all seven of his worlds.
- **What it costs:** a reference mission is about 50 s on one core (about 70 s on the MAX map); 300 worlds × 7 players took 7 minutes. All of Saturday's farm runs (about 6,000 missions) were about 105 core-hours, roughly $6 at Modal's published rates (an estimate, not the bill).
- **A rerun into the same folder plays only missions it has not seen**, so you can add players to a finished comparison. A saved row is reused only if the same Traverse code played it.
- Stopping the local `modal run` does not always stop its app: `modal app list`, then `modal app stop --yes <app id>`.

## 3. Training and the live demo

- **Training:** Sölvi's launchers ([`tools/lightlag_rl/modal_job.py`](../tools/lightlag_rl/modal_job.py), [`tools/learning_campaign/modal_job.py`](../tools/learning_campaign/modal_job.py)) run bounded CPU jobs with a frozen image, a deadline and a budget cap; see [`learning-campaign.md`](learning-campaign.md).
- **The live demo** (the 15% "live deployed demo" part of the prize): https://kristjansolvi03--lightlag-traverse-live-web.us-east.modal.run, from [`tools/traverse_farm/live_app.py`](../tools/traverse_farm/live_app.py) (`modal deploy`). Pick any world; Modal drives the reference, a textbook controller and the six saved Claude-written autopilots that can drive a new world on it, eight containers at once, and serves the replay. Scroll, drag and right-drag move the camera. A MAX row could be added once the MAX map's players are settled.

## Seeds: who uses what

Keep training, tuning and selection off everything below; evaluate on fresh ranges.

| Worlds | Used for |
|---|---|
| 1–99 | Traverse development (the Traverse owner) |
| 100–499 | Farm option search and selection |
| 500–523 | Manh's MAX pool; the six held-out evaluation worlds 500, 510, 520, 505, 509, 515 (rule in `AGENTS.md`) |
| 600–899 | Farm comparisons (normal map; 600–699 also on the MAX map) |
| 1000–1199 | The Traverse owner's fresh checks |
| 1200–4999 | Integrity-review exploit probes |
| 2026; 2027–2029 | The one-mission task; the campaign's sites |
| 71000–71127 | Sölvi's first RL training worlds |
| 72000–72039 | Used in Sölvi's first RL experiment (no longer untouched) |
| **82000–82039** | **Sölvi's untouched final worlds, reserved until his weights are frozen** |
| 99991 | The example world in the one-request text |

Sölvi labels validation scores that were checked repeatedly as **development results**; only the final worlds give a held-out number.

## What to record for the Modal prize

For every Modal job: the app ID, the configuration (CPU, memory, containers, timeout), what ran, the result, the time, and the cost, saying whether it is measured or estimated. Add it to [`prize-evidence.md`](prize-evidence.md) under your own entry. The summary row at the top already lists the farm, the training runs and the live demo.
