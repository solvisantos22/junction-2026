# API preflight correction before model generation

The first launch, from `e2d444e`, stopped during token counting. The provider
returned HTTP 400: the tool input schema cannot use a top-level `oneOf`.
Request ID: `req_011Ch36cL46oUX3o4SbYBV1c`. The retained
[preflight report](adaptation/adaptation.json) records zero generation requests,
zero reported generation cost and no unknown usage. No practice or fresh case
was opened by that launch. It is an incomplete harness preflight, not a model
failure or a completed adaptation attempt.

Correct the API schema to a plain object with optional `code` and `replacements`
fields. Tool descriptions still require exactly one, and the existing local
validator still rejects both/neither. No change to what code the model may
submit, the prompt, mission, resources, model, tools' semantics or retirement
thresholds. Add a focused regression for the rejected schema shape. Retain the
failed launch rather than overwriting its artifacts.

After verification and publication, relaunch to `adaptation-v2/`. This is a
documented correction to the earlier stop-on-count-failure protocol: the old
launch remains incomplete; the new launch uses corrected provider formatting.
The original **two generation requests and $1.00 total usage guard** are shared
across both directories, with the first consuming neither. There are no extra
model attempts or fresh-map observations, and no automatic retry loop. All
other [frozen protocol](adaptation-protocol.md) terms remain unchanged.
