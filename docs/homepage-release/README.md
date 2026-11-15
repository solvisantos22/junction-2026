# Homepage release, 15 November 2026

Sölvi reviewed the local mission-control homepage and explicitly approved immediate publication. Source is on main in `e047a451`, with the explicit Modal asset-mount correction in `d4722a54`. Deployment uses Kristján’s existing Modal workspace and the same submitted URL:

https://kristjansolvi03--lightlag-traverse-live-web.us-east.modal.run/

## Public verification

At **10:25:42 Helsinki (08:25:42 UTC)** the homepage and all nine CSS/JS/font/image files returned HTTP 200 and matched the approved local bytes. World 2027 reported ready; its cached replay was HTTP 200, 3,219,685 bytes, SHA-256 `4712d1af26d5fcba8ae9ba6ffcdad93b0c206b4dce39508a7e9ec3eca60815c3`, identical to the pre-change capture. [HTTP evidence](deployment-check.json).

A fresh signed-out Chromium check at 1440 px and 390 px found loaded fonts/image, visible primary action, no horizontal overflow and no script/resource errors. Skip navigation, invalid-number feedback and the primary link to world 2027 worked; pressing Enter started the replay (tick 1 observed). Both live screenshots were visually inspected. [Browser evidence](live-browser-check.json).

Before publication, local checks covered six widths from 320 to 1440 px, form bounds, keyboard, reduced motion and text contrast. Independent finish review found no material fixes. The farm suite ran 39 tests with one optional dependency skip. FastAPI smoke checks covered packaged assets, valid query redirect, invalid world/status routes and excluded source paths. The Modal SDK entrypoint-mount behavior was inspected and the cloud asset path checked against the explicit image mount.

No new mission, cache reskin, simulation/result edit, submission edit or inference was needed. The replay viewer, saved programs and frozen task remain unchanged. [Design, skill sources and deployment command](../../tools/traverse_farm/home_preview/README.md).
