# Reusable-policy experiment: reviewed preparation checkpoint

**No real provider endpoint or fresh seed 60000–60019 has been used yet.**
The single-response [protocol](../../lightlag-synthesis-experiment.md) is
predeclared. This increment publishes the exact public request, constrained
worker, historical parity checks and reviewed API runner. The evaluation phase
is still being implemented/reviewed; do not launch generation until it passes.

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

## Pending launch and reporting

A+B is complete and independently reconciled at **$9.4355068**. This phase
reserves at most $1 inside the user’s reported $15.70 overnight budget; no new
paid launch at $12 cumulative usage. The free token counter must pass the
25%-plus-1000-token allowance and $0.90 maximum calculated bound first.
One model response only, no retries or repairs, with recorded usage and
calculated cost distinguished from a verified account balance.

After evaluation review and publication, root can invoke the documented
`synthesize` phase with the exact approved request hash and explicit operator
flag. Credentials are supplied only in the child process environment, never
in request artifacts or containers. Then freeze the unedited response and run
exactly the declared 40 cells against original KF, retaining every outcome,
protected grade, transcript, source hash and four verification repetitions.
If generation is invalid or incomplete, retain all planned cells as unrun/null;
do not buy another response or repair the program.

This is one sampled program across many maps, not forty independent model
attempts, and is separate from the online OpenCode comparisons and required
Harbor playthrough. A failure here does not establish inability with feedback.
