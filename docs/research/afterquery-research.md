# AfterQuery: what the research changes for our project

**Working research brief — 13 November 2026.** This first increment records verified findings while the deeper sections are being prepared. Project choice and performance gap remain unproven; no challenge project has been implemented or evaluated.

## First conclusions

1. **Test a specific operational weakness, not “LLMs cannot plan.”** AutoVend already tests resource commitments, expiration and physical execution; one evaluated frontier agent beats its rule-based baseline while four others do not. That makes it a direct precedent and a warning against a blanket ColdChain claim. [AutoVend, November 2026, abstract and §4](https://arxiv.org/html/2610.36980v2)
2. **Let the agent build a controller or use a solver.** CoDyControlBench reports strong results for generated feedback controllers. That does not prove reliable operation under our proposed batch constraints, but it rules out assuming that numerical dynamics alone create a convincing challenge. [CoDyControlBench, August 2026, §§II–IV](https://arxiv.org/html/2608.07004v1)
3. **A low score can be a broken benchmark.** A recent Terminal-Bench audit found task defects and showed that repairs and time budgets can materially alter reported performance. Before celebrating a failure, classify whether it came from the decision, tools, resource limits or the evaluator. [Benchmarks as Software, November 2026, §§5–6](https://arxiv.org/html/2611.08417v1)
4. **A compelling result is a replayable causal explanation.** Our inference: show the moment a plausible local decision creates an avoidable later loss, demonstrate the reference handling the same information, and check that the pattern survives fresh instances and capable tool use.

These are research implications, not proof that any of our three environments will defeat the current challenge agent. The review also cannot estimate how many Junction teams are building similar projects.

## What Harbor already supplies

The [challenge brief](https://hackjunction.app/participate/45/challenges/328) names Harbor and OpenCode over MCP. Public upstream documentation confirms a practical route, but it does **not** establish the version or exact contract of the event's starter kit.

| Component | Verified upstream capability | What it means for us |
|---|---|---|
| Task packaging | Instructions, environment, reference solution and verifier are separate task components. [Task overview](https://docs.harborframework.com/tasks/overview) | Build a small environment package instead of a new evaluation platform. |
| Tool access | MCP services can be declared alongside container environments; agents may use code execution and files. [Environment](https://docs.harborframework.com/tasks/environment) | A model writing its own routing or control script is legitimate capability, not a loophole. |
| Agent integration | The current list includes OpenCode, reference (`oracle`) and no-op (`nop`) agents, with capabilities differing by integration. [Agent integrations](https://docs.harborframework.com/agents/pre-integrated-agents) | Pin and test the organizer's actual agent/model/configuration. A supported MCP integration alone does not prove connectivity. |
| Reward output | Verifiers write numeric rewards, including structured metrics, after checking outcomes. [Verifier](https://docs.harborframework.com/tasks/verifier) | Score the actual final world state and keep diagnostic metrics separate from the primary objective. |
| Verification boundary | Separate verifier environments are supported; configurations omitting both relevant settings retain shared verification. [Separate verifier](https://docs.harborframework.com/tasks/separate-verifier) | Inspect the supplied configuration. A separate container helps, but an agent-writable transcript is still not authoritative evidence of real events. |

**Our proposed boundary:** the simulator owns state and records accepted actions; the agent owns its scratch files and policy code. The verifier derives outcomes from trusted state or an authenticated action history. This is a design recommendation to discuss, not an implementation or security guarantee.

The ecosystem also distinguishes tasksets from runtimes: Hugging Face's environment catalogue can describe Harbor/OpenEnv/other compatibility, and its OpenEnv example runs an OpenCode agent over Harbor tasks. A missing verifier reward is an execution problem to investigate, not automatically a failed model decision. [Hugging Face environment announcement, September 2026](https://huggingface.co/blog/rl-environments)

## Questions the research must resolve next

- Which parts of routing, control and recovery are already well-covered, and which narrow mechanism could make our demo distinctive?
- Did a published failure survive code/solver access, multiple attempts, appropriate memory and fair resource budgets?
- Does the reference use only information available at the same decision time, or does it quietly know future disturbances?
- Can we explain a failure within a short demo without compressing the model's thinking time into an artificial real-time trap?
- What observation would make us abandon a candidate before investing in polish?

The deeper benchmark, control and reward reviews are being checked separately. This document will be updated with a combined judgment and an experiment proposal once those checks are complete.
