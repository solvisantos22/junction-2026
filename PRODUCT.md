# Lightlag Traverse

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

AfterQuery judges and hackathon visitors trying the submitted rover environment. The homepage should get a first-time visitor into a replay quickly.

## Product Purpose

Compare a reference planner, a textbook A* + Kalman controller and six saved Claude-written autopilots on the same simulated terrain.

## Capabilities and Constraints

The live Modal site accepts world numbers 1–1,000,000, runs the fixed programs and serves a cached interactive replay. Each mission has 420 ticks; commands and observations are delayed by three ticks. This is not an interface for arbitrary agent inference. New worlds take about a minute for the initial replay; the slowest autopilot can join later.

Sölvi reviewed the local homepage preview and approved immediate publication on 15 November 2026. The adopted direction applies to the homepage only; backend execution, saved results, the simulator and the replay viewer stay unchanged.

## Brand Commitments

The user chose “Mission control: dark charcoal, real terrain, restrained amber.” Preserve the Lightlag Traverse name and the relationship to the rover viewer.

## Evidence on Hand

`tools/traverse_farm/live_app.py` supplies the current content, driver descriptions and five featured worlds. `viewer/traverse/` is the real product UI. The public Modal page supplies cached world 2027 for a local screenshot and replay. No new metrics, testimonials or outcome claims are needed.
