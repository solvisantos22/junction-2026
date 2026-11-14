# Reusable-policy experiment: bounded generation outcome

**The single response hit its 24,000-token output cap during thinking, before
producing any controller text.** The declared attempt is retained without a
retry. There is **no transfer-performance result**: all 40 cells (80 planned
policy/reference episodes) remain unrun with null rewards. No fresh maps were
constructed, and the result does not establish inability to solve the task.

The [generation record](generation-v1/synthesis.json) retains the exact request,
response and stream hashes. The [unrun evaluation ledger](evaluation-v1/summary.json)
keeps every planned identity, denominator and missing-score bound. Independent
review verified both records and found no credential/path-pattern leakage.

## Frozen inputs

- Simulator/service/original KF: commit `02e4f7062ec3feaca14d9cc2eeb953af870ba769`,
  twelve recorded imported source files in a separate verified snapshot.
- Protocol: `7f9f57c63a9665cd158327eb7d46ac7f32cca571`.
- [Exact request](preparation-v1/request.json), SHA-256
  `665216780f653805a25efb555e1eec1e5274fb7a134ae9aa33ff5c51611c5454`.
  Only public instructions, rules, interface shapes and the generic aid;
  no episode seeds/maps, simulator/reference source or historical traces.
- [Preparation manifest](preparation-v1/preparation.json): 28 artifact hashes,
  32 historical input hashes, worker/image/runtime settings and verification.
  The eight complete historical KF trajectories and results reproduce exactly.
- Python 3.12.16, Anthropic SDK 2.8.0. Worker image is pinned to
  `python@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b`.
  The isolated worker has no network, repository, secret, seed or evaluator
  mount; the host broker serves only the five public methods.

`preparation-v1` is immutable. Its saved `runner.py` records the exact preparer
used at that time. The live preparer later gained diagnostic sanitization,
phase dispatch and optional explicit standard-service defaults; those changes
do not regenerate or alter this request. The API phase reads and hash-checks
the saved JSON, and each phase records the implementation it actually uses.
The worker, simulator and model-facing request remain the saved bytes.

## Verified implementation

Independent preparation review passed all 15 tests, including real Docker
isolation, timeout cleanup, accepted-command retention after policy failure,
new-only output ownership and the eight-reference parity gate. API review
passed all 10 offline tests plus a fake-client whole-CLI check. It reproduced
and closed three issues before any real request: a stream without its terminal
event must have unknown usage; SDK environment header overrides must be
rejected; an actual cost above the $1 reservation must retain its known cost
and stop. A permanent claim prevents a second request destination for this
preparation. No network request is made by those fake-client tests.

Run the same preparation/API checks with the declared SDK and image installed:

```sh
SYNTHESIS_TEST_IMAGE=python@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b   python -m unittest discover -s tests/lightlag_experiments -p 'test_overnight_synthesis.py' -v
python -m unittest discover -s tests/lightlag_experiments -p 'test_overnight_synthesis_api.py' -v
```

Without `SYNTHESIS_TEST_IMAGE`, the two Docker tests explicitly skip. The tests
use only old fixture seeds, not the reserved fresh cells. Existing evidence
directories are never overwritten. Do not run the generated policy on the host.

## Completed one-response attempt

The exact predeclared request was sent once to `claude-opus-5-5`, with adaptive
thinking, high effort and `max_tokens=24000`. The free counter estimated 5,989
input tokens. Its padded allowance was 8,487, for a maximum calculated cost of
$0.513948 including all 24,000 output tokens, within the $1 reservation.

The completed response reports **5,989 input tokens and 24,000 thinking tokens**,
`stop_reason=max_tokens`, and no text block. Both `response-text.txt` and the
extracted `policy.py` are empty. This is a response-budget outcome; no program
was repaired, replaced or executed. Standard-tier token pricing gives a
**calculated cost of $0.503956**, distinct from an invoice or verified balance.

A+B reported $9.4355068; adding this calculated usage gives **$9.9394628** for
this coordinated work. The $12 launch guard and $15.70 user-reported ceiling
were respected. No paid request remains running.

The evaluator took its declared ineligible-generation path: **0 attempted,
0 scored, 80 unrun** primary rows and four unrun verification rows. Each
policy/profile mean is null, with [0,1] missing-score bounds; paired bounds are
[−1,1]. These are not zero-reward episodes. Seeds 60000–60019 remain uninspected.
One `message_start` and one `message_stop`, all twelve generation artifact hashes,
claim links, exact request bytes, usage and all planned evaluation identities
were independently checked. No retry was made.

The controller-transfer question remains open. This is neither an online
OpenCode playthrough nor a qualifying new Harbor model run. A poor or incomplete
single response under this budget does not establish general model incapability.
The protocol forbids replacing it to obtain a more favorable result.

## Final runner review before launch

The evaluator preserves 80 planned primary slots and four fixed generated-policy
verification attempts. Policy errors receive normal protected grading;
infrastructure failures retain null primary scores and bounded comparisons.
Interrupted in-flight attempts remain attempted/unknown, not unrun; interruption
stops the loop, and matching infrastructure failures cannot establish policy
reproducibility. Review also fixed CLI exit-code propagation and malformed
terminal JSON handling. The exact request, worker and twelve simulator source
files remain unchanged. No real endpoints or fresh maps were used in review.

Review approved broker SHA-256
`39a25cee7473b4319c9de906788e56b0f9dfce7a68115fdb1a944fed9dade469` and evaluator
`8ba24f003cd5999293a8d44f2d86b614c146aee776bb267168a343f2bec34e24`.
Run all 42 checks with the pinned image via the same test command above, using
pattern `test_overnight_synthesis*.py`.

The provider’s [current model documentation](https://platform.claude.com/docs/en/models/opus-5-5/overview)
still lists $4/million input and $20/million output. Its
[versioning documentation](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions)
identifies these dateless IDs as pinned model snapshots; serving infrastructure
can still change. Both sources were rechecked before launch on 14 November.
