# Lightlag MCP server

14 November 2026, 01:00 Helsinki. Owner: Kristján / Claude Code. Code: [`lightlag_mcp/`](../lightlag_mcp/), tests: `tests/lightlag_mcp/`. It wraps Sölvi's simulator and changes nothing in it.

**Status:** the server works over stdio and HTTP and is covered by 18 tests, driven by a real MCP client. **No model has played through it yet**, the container image has not been built, and nothing here has been run under Harbor. The organizers' starter kit is still unpublished.

## One finding that affects the whole project

**OpenCode lets the agent call MCP tools from its own code by default.** Its docs call this Code Mode: tools appear to the agent as `tools.<server>.<tool>(...)` inside code it writes, unless the server is configured with `codemode: false`. So an agent can write a loop that reads telemetry and sends commands with no model in the loop. The round-two reviewer said this is the case in which a control gap closes. Together with the [pilot result](lightlag-pilot.md) that a plan which never reads telemetry already scores 97–101% of the reference, the rule changes proposed there matter more, not less. We do not know yet whether the judges' harness keeps Code Mode on.

## Run it

Needs Python 3.10+ and the `mcp` package, version 2.x. With `uv` nothing has to be installed permanently:

```sh
# one episode over stdio (a local agent starts this command itself)
uv run --with 'mcp>=2.3,<3' python -m lightlag_mcp --transport stdio --seed 7 --delay 3 --artifact-dir /tmp/lightlag-run1

# one episode over HTTP, at http://127.0.0.1:8000/mcp
uv run --with 'mcp>=2.3,<3' python -m lightlag_mcp --transport http --port 8000 --seed 7 --delay 3 --artifact-dir /tmp/lightlag-run1

# tests: 10 need only the standard library, 8 more run when mcp is installed
python3 -m unittest discover -s tests/lightlag_mcp -v
uv run --with 'mcp>=2.3,<3' python -m unittest discover -s tests/lightlag_mcp -v
```

One server process is one episode. To run another episode, start another process with another seed.

## What the agent gets

Exactly five tools, with the simulator's own JSON as the result:

| Tool | Advances time | What it does |
|---|---|---|
| `rules` | no | Delay, episode length, energy costs, slip ranges, limits |
| `map` | no | Size, base, targets, hazards, sand |
| `telemetry_log` | no | Every packet received so far |
| `uplink(commands)` | no | Queue 1–5 commands; returns when each will execute |
| `advance(ticks=1)` | yes | Let 1–5 ticks pass; returns the packets that arrived |

The tool descriptions and the server instructions state the timing rule in full (a command sent at tick `t` executes at `t + delay + 1` at the earliest; a packet is `delay` ticks old). A rejected call comes back as a tool error with the reason, for example `metres must be in (0, 5.0]`, so an interface mistake is visible to the agent and cannot pass for task difficulty.

## What the agent cannot do

Each of these is a test:

- Call anything but the five tools. `evaluate`, `replay`, `finish`, `reset` and private names are refused.
- Reset the episode or choose a seed. There is no such tool, and one process is one episode.
- See the seed or the hidden slip. A full reference-controller episode was played and every result searched for both.
- Change state with an invalid request. It is rejected whole.
- Stop the clock by leaving. Finishing always runs the remaining ticks before grading, so doing nothing scores 0 and stopping early is graded at the full horizon.
- Finish or grade the episode over HTTP without the evaluator's token. The route answers 404 without it, and does not exist at all when no token is configured.

**What is not protected:** in stdio mode the server is a child process of the agent, which can read its command line and files. Stdio is for local pilots. Benchmark runs need the HTTP server in its own container.

## The evaluator's side

- **`service.finish()`** (Python) or **`POST /evaluator/finish`** with `Authorization: Bearer <token>` (HTTP): closes the episode to the agent, runs out the clock, grades it and returns the result. The token is read from the `LIGHTLAG_EVALUATOR_TOKEN` environment variable only.
- **Artifacts** in `--artifact-dir`: `result.json` (score, sampled targets, survival, number of tool calls), `replay.json` (true states, hidden slip, all commands) and `transcript.jsonl` (one line per tool call, written as it happens, including rejected ones). This directory must not be mounted into the agent's container.
- **Stopping the process** (end of stdio, or SIGTERM as a container stop sends) also finishes and grades the episode.

## Run scripted controllers through it

`lightlag_mcp.client.connect` turns an MCP connection into the five blocking methods the controllers expect, so the reference and baselines can play through the same service a model uses. A test confirms they score the same as on the simulator directly.

```python
from lightlag_controllers import REFERENCE, drive, make
from lightlag_mcp.client import connect

with connect("http://127.0.0.1:8000/mcp") as tools:
    drive(tools, make(REFERENCE))
```

## Connecting OpenCode (from its current docs, not yet tried)

Project `opencode.jsonc`, local pilot over stdio:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "servers": {
      "lightlag": {
        "type": "local",
        "command": ["uv", "run", "--with", "mcp>=2.3,<3", "python", "-m", "lightlag_mcp",
                    "--transport", "stdio", "--seed", "7", "--delay", "3",
                    "--artifact-dir", "/tmp/lightlag-run1"]
      }
    }
  }
}
```

Against the HTTP server, use `"type": "remote"`, `"url": "http://127.0.0.1:8000/mcp"` and `"oauth": false`; OpenCode tries OAuth on remote servers unless told not to. Add `"codemode": false` to compare an agent that must call tools one at a time with one that can script them. Model API keys go in a `.env` file or the shell environment, never in this file.

## Fitting it into a Harbor task (from Harbor's docs, not yet tried)

Harbor's documented pattern for an MCP environment is a sidecar container next to the agent's `main` container:

```toml
# task.toml
[[environment.mcp_servers]]
name = "lightlag"
transport = "streamable-http"
url = "http://lightlag:8000/mcp"
```

```yaml
# environment/docker-compose.yaml
services:
  main:
    depends_on:
      lightlag:
        condition: service_healthy
  lightlag:
    build:
      context: ./lightlag          # lightlag/, lightlag_mcp/ and the Dockerfile
    expose: ["8000"]
    environment:
      LIGHTLAG_SEED: "7"
      LIGHTLAG_DELAY: "3"
      LIGHTLAG_EVALUATOR_TOKEN: "${LIGHTLAG_EVALUATOR_TOKEN}"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz', timeout=2)"]
      interval: 2s
      timeout: 5s
      retries: 15
```

The verifier would then call `/evaluator/finish` and write the returned `raw_score` to Harbor's reward file. Open questions for the starter kit:

- **Does the sidecar survive until verification?** Harbor's separate-verifier mode starts a fresh copy of the environment. If that restarts the sidecar, the episode state is gone, so we would need shared verification or a persistent artifact volume.
- **How does the verifier get the token** without the agent's container seeing it?
- **Which agent settings are fixed** by the organizers: model, Code Mode, time and step limits.
- **The reference run:** Harbor's `oracle` agent runs `solution/solve.sh` in the agent's container. Ours would be the snippet above, which needs `lightlag_controllers/` and the `mcp` package there.

## Not done

- A model playing an episode. Needs OpenCode installed and a model API key in the environment.
- Building and running the container. Docker was not running on this machine.
- A Harbor task directory. Waiting for the starter kit, to avoid guessing its layout twice.
- More than one map. The server uses the simulator's default map; a `--map` option is a small addition once the team decides on maps.

## Sources

- [Harbor: Environment (MCP declaration)](https://docs.harborframework.com/tasks/environment), [Multi-container](https://docs.harborframework.com/tasks/multi-container), [Separate verifier](https://docs.harborframework.com/tasks/separate-verifier), read 14 November 2026.
- [OpenCode: MCP servers](https://opencode.ai/docs/mcp-servers), read 14 November 2026.
- MCP Python SDK 2.3.0, inspected as installed.
