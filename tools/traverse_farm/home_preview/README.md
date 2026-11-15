# Lightlag homepage

Sölvi requested a local preview, selected **mission control: dark charcoal, real terrain, restrained amber**, reviewed it and approved immediate publication on 15 November 2026. `live_app.py` now serves these exact homepage files and assets. The replay viewer and all simulation/results files remain unchanged.

Run from the repository root:

```sh
python3 tools/traverse_farm/home_preview/serve.py
```

Open <http://127.0.0.1:5183>. The old homepage capture is at `/before` when present in the local cache. The server listens only on localhost and serves an explicit allowlist, not the repository.

The current local cache contains public world 2027. Opening that replay runs entirely from its saved HTML. Other world links and a submitted new world number navigate to the existing public Modal site. A new world may start the existing rollout there; opening the homepage alone makes no cloud call. The server imports no Modal SDK or credentials.

## Design and material

- Real terrain from the public world 2027 replay at tick 170 replaces the schematic crater illustration. Its embedded PNG provenance records source, frame and capture method.
- A featured replay is the primary action. The same world-number bounds, five featured destinations and four controller groups remain available.
- Charcoal, restrained amber, local Barlow fonts, square media and flat rows replace the gradient and repeated rounded cards.
- “Only one always makes it home” is removed: it overstates the scope of measured evidence. Specific featured-world descriptions remain available in the disclosure.
- No new inference, benchmark run or result claim. Production integration changes only the homepage and its static/form routes.

Fonts are served locally. Barlow and Barlow Condensed are by Jeremy Tribby, distributed under the SIL Open Font License; the two license files and exact Google Fonts download origins are in `assets/`.

## Requested skills

Installed in the user's Codex skill directory, pinned to the following upstream revisions. No global hooks or third-party npm installer were added.

| Skill | Upstream | Revision | Use in this preview |
|---|---|---|---|
| TasteSkill | [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill) | `f6b76575f949707b4e3c37cd86cb44b0b98643e8` | Product/audience/material analysis, restrained copy and copy lint |
| Impeccable | [pbakaus/impeccable](https://github.com/pbakaus/impeccable) | `2b86d9c07b97d4bed7de23583e1bd1e58dd2baae` | Context, simplification/craft/polish guidance, source detector, raster provenance and finish review |
| Hallmark | [Nutlope/hallmark](https://github.com/Nutlope/hallmark) | `04977e15f3dfd6ee4b74c887dac3eb52665d6c92` | Token/focus/layout guidance and static sloplint |
| UI/UX Pro Max | [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | `d643997c82e94742dd3bee43210b0198e8bbba3d` | Contrast, labels, touch targets and responsive guidance. Its generic neumorphism/HUD palette suggestions did not fit the chosen brief and were not applied. |
| Unslop-UI | [JCarterJohnson/vibecoded-design-tells](https://github.com/JCarterJohnson/vibecoded-design-tells/tree/main/skill) | `f7c4aefc2c797a66e55b49354a93917ab60d33ac` | Before/after source scanner and deliberate choice review |

The user-selected direction governs this homepage. This is not a claim of full compliance with every conflicting design framework.

## Verification

The existing rollout-farm baseline passed 39 tests, one skipped. Browser checks at 1440, 1280, 1024, 768, 390 and 320 pixels found no horizontal overflow, missing control labels or script errors; local image and fonts loaded. Checked skip link, keyboard entry, primary replay link, disclosure, five destinations, reduced motion, valid seed and invalid empty/zero/too-large/fractional seeds.

All tested text/background pairs exceed 4.5:1; the lowest is secondary text at 6.06:1. Impeccable's source detector returned no findings. Unslop-UI scored both the original and the candidate **0**: this is a narrow regex scan, not evidence that they look equally good or that the redesign is certified. Taste copy lint returned no failures and one retained warning for the real world-number links. Hallmark static lint returned no failures; its missing disabled-style reflex is waived because the form navigates immediately and has no disabled state. Browser rendering was checked separately with Chromium/Playwright, not Hallmark's render tier.

Independent visual review found no material fixes. Sölvi approved adoption after viewing the local preview. Production route checks passed for the homepage, CSS/JS, fonts/image, valid form redirect, invalid-world rejection and source-path exclusion, without remote execution.

## Deploy to the existing public URL

The submitted URL belongs to the `kristjansolvi03` Modal workspace. Deploy from a checkout authenticated to that workspace; Sölvi’s `solvi-junction` profile belongs to a different workspace.

```sh
git pull --ff-only
modal deploy tools/traverse_farm/live_app.py
```

Use a clean main checkout. The existing image already packages this directory. No cache reskin, new worlds or replay regeneration is needed. Keep the same app name and cache volume. After deployment, verify the homepage, its assets and cached `/world/2027`.
