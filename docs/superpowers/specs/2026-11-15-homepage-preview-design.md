> **Adopted after local review:** Sölvi approved immediate production publication on 15 November 2026. The preview-only restrictions below record the original review phase; the approved homepage can now be committed and deployed. Replay/simulation scope exclusions still apply.

# Homepage local preview

Sölvi chose mission control: dark charcoal, real terrain, restrained amber, from three offered directions. The agreed intent is to see a local first page before committing to it.

## Direction contract

THESIS: A mission selection screen that shows the actual terrain and leads directly to a replay. The page should feel like the front door to this rover experiment.

OWN-WORLD: Charcoal surfaces, the viewer's amber, square media, thin separators. Barlow Condensed gives headings the compact lettering of the existing viewer; Barlow carries readable explanatory text. Monospace is confined to world numbers and measurements.

STORY: Understand the task, open a featured replay, then optionally choose a world. Eight fixed programs run on identical terrain. Their routes, battery and samples are visible in the viewer.

FIRST VIEWPORT: A quiet masthead. A large real terrain view is the main object; beside it, the project name, a brief explanation and an amber Open replay action. Featured-world choices sit immediately with the terrain. The custom-world form follows, then a flat driver list rather than four equal cards.

FORM: seed: none (pinned). User selected “Mission control: dark charcoal, real terrain, restrained amber” after the proposal to use real terrain and an “Open a replay” action. Local code preview, not a generated mockup; no standing tool workflow preference inferred.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.

## Boundaries

Create the preview in `tools/traverse_farm/home_preview/`. Do not change `live_app.py`, the Modal deployment, frozen task/controller/results, or the viewer. Keep all five world destinations and the original seed range. Local cached replays open without triggering cloud work. The arbitrary-world action can navigate to the existing live route only when a visitor submits it. Review the local preview before any integration.

## Validation

Inspect desktop and mobile renders, keyboard focus, all world choices, range validation and reduced motion. Use the requested skills' audits as supporting checks, not as proof that a design is good. Preserve source and font provenance. Run the existing rollout-farm baseline before changes; it passed 39 tests with one skip.
