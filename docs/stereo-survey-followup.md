# Stereo follow-up: can an agent build the solver?

14 November 2026. Kristján asked to continue investigating stereo survey and assess whether it is a good lead. The [v1 result](stereo-survey.md) remains unchanged: a small generic-search portfolio attains every fresh optimum. That establishes easy search **once an appropriate program exists**. It does not measure whether a coding agent will formulate and implement that program from the public rules.

This follow-up targets that missing evidence before constructing a larger environment. It is a different, explicitly stated question, not a reinterpretation of the failed v1 screening gate. No LLM weakness is established at the start of this follow-up.

## Why the research does not settle it

[AstroAgentBench](https://aclanthology.org/2026.aacl-long.72.pdf), §§3 and 5 and Appendix C, asks stereo agents to choose observation times and pointing angles and derive useful products from them. Our v1 instead supplies finite image opportunities and rectangular footprints. The paper separates task formulation from solution construction, and reports specification-related failures as well as genuine planning failures. Its procedure/memory interventions are reported for Regional Coverage and Relay, not a clean current-model stereo replication. These differences justify a limited agent test; they do not justify claiming the paper's gap for our easier task.

## Intended test

Package the public rules, geometry helper, independent validator and development missions in an isolated workspace. Do not expose reference/search code, solutions or fresh outcomes. Invite code, solver use and local validation. Freeze the returned program and evaluate it on new missions against the same exact reference, retaining every outcome and any resource/error limit.

Start with a cheap falsification: if a generated general solver already matches the reference, retire this version as a difficulty candidate. A failure from one generation is weaker evidence and would require a proper feedback-enabled coding-agent run before any positive claim. A solver hint should also be tested before treating a failure as robust.

The protected checks, source/task hashes, execution limits, prompts, exact model configuration and spend limit must be concrete before a model call. No API spend is authorized by this document, and no unrelated session's budget is reused. Preparation and offline validation are within the user's approved continued investigation.

Implementation, evaluation protocol and results will be recorded here.
