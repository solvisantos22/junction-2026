# Sponsor tools and extra prizes — Junction 2026

Checked Friday 13 November, approximately 22:10 Helsinki, against all 20 Developer Tools and Assets entries and all 19 Tech Challenges on the logged-in Junction platform. Offers can change. This is research: no credits redeemed, accounts created or prize entries submitted.

**Update, Saturday 14 November at 01:35 Helsinki:** Ved announced that **AfterQuery will not supply inference credits**. Harbor packaging, a 0–1 text reward and at least one scored Harbor model run are now explicit. See the [announcement and Lightlag implications](docs/afterquery-update-2026-11-14.md). Other sponsor rows below retain their Friday verification date; they are not confirmation of a redeemed balance.

**Modal update, Saturday 14 November around 02:05 Helsinki:** the participant offer was rechecked and Sölvi's **$100 redemption request was submitted**. The form confirmed processing and said confirmation would arrive by email. The grant has **not yet been verified as applied**. The offer remains $100 of CPU/GPU compute per participant, valid for one year; each teammate needs an existing Modal workspace to claim through the [participant resource](https://hackjunction.app/participate/45/hackerpacks/62). No payment method was added or compute started during the claim.

## Recommendation for our AfterQuery project

**Start with AfterQuery + Best Use of Codex + one compute provider.** Modal is my initial preference for a deployed evaluation/demo; Verda is particularly attractive if we reach the optional model-training stretch. Add a model prize only when that model does useful, visible work in the project.

- **Codex:** a natural extra entry because we already intend to build with it. Keep concrete evidence of its contribution to the actual environment, reference solver, evaluations and debugging.
- **Modal:** use isolated environments, parallel evaluations, an inference endpoint or a usable deployed demo. These support AfterQuery's reproducibility and demonstration needs.
- **Verda:** its brief explicitly suggests running rollouts in an AfterQuery environment and fine-tuning a smaller model. Strong fit if we demonstrate learning improvement; compute can also support evaluation/inference.
- **Gemini / Gemma / Nemotron:** choose a purposeful role rather than integrating all three. An agent operating our environment, a controlled comparison or a measured improvement could be relevant, but merely mentioning or making one incidental call is not strong evidence for these prizes.
- Preserve the frontier-model evaluation required by AfterQuery. Confirm its harness/model requirements before treating any sponsor model as the qualifying frontier run.

These are fit judgments, not confirmed eligibility decisions or estimates of winning probability. Tech challenges can run alongside the main track. [Official overview](https://2026.hackjunction.com/)

## Best-fitting prize options

| Extra challenge | Prize as listed | What we must demonstrate | Fit / decision |
|---|---|---|---|
| [Best Use of Codex](https://hackjunction.app/participate/45/tech-challenges/49) | 1st **$10,000 API credits**, 2nd $5,000, 3rd $2,500 | Meaningful use of Codex to build, iterate and ship the project | **Strong default entry.** Document actual development contributions. Prizes are credits, not cash. |
| [Best Use of Modal](https://hackjunction.app/participate/45/tech-challenges/40) | **$2,000 cash + $3,000 Modal credits** for the winning team | Modal central to the project; effective use 40%, ambition 25%, impact 20%, live deployed demo 15% | **Strong infrastructure candidate.** Use it where it improves evaluation or the demo. |
| [Verda Compute Track](https://hackjunction.app/participate/45/tech-challenges/56) | 1st **$10,000 cloud credits + hoodies**; 2nd and 3rd $2,500 credits each | Compute enables something beyond a laptop; document process and post a summary link in their Discord channel | **Strong alternative to Modal**, especially rollouts/training. Choose a clear compute story. |
| [Best Use of Gemini API](https://hackjunction.app/participate/45/tech-challenges/48) | 1st **€4,000 + $1,000 Google Cloud credits per member**; 2nd €2,000; 3rd €1,000 | Meaningful, innovative, technically impressive Gemini integration; explain why Gemini matters | **Conditional strong fit.** Could be an operator in the environment; confirm that our evaluation use meets their expectations. |
| [Best Use of Gemma](https://hackjunction.app/participate/45/tech-challenges/47) | **€1,000 to each of three winning teams**, unranked | Innovative, impactful use of Gemma open models | **Good training/stretch candidate.** Hosting via Featherless, Modal or Verda is explicitly suggested. |
| [Best Use of Nemotron](https://hackjunction.app/participate/45/tech-challenges/46) | **Two winning teams receive one RTX 5080 each** | Use **Nemotron 3.5 Super VL** in core functionality; visibly demonstrate it and explain model, role, value and improvements in submission text | **Possible, but verify endpoint first.** The minimum requirement names Super VL, while a getting-started example names a different Lightning model. Do not assume they are interchangeable for eligibility. |
| [Best Use of Aiven](https://hackjunction.app/participate/45/tech-challenges/43) | **€1,000 / €750 / €500** | At least one Aiven service meaningfully contributes; meaningful use 40%, implementation 30%, impact 20%, creativity 10% | **Useful if needed:** PostgreSQL for episodes, ClickHouse for evaluation events, or Runtime for hosting. Avoid adding a database solely for another entry. |

## Tools and credits available tonight

| Provider | Offer / access | Application to AfterQuery |
|---|---|---|
| [AfterQuery](https://hackjunction.app/participate/45/challenges/328) | Harbor required; OpenCode encouraged; mentors. **No inference credits**, per Ved's Saturday 01:35 update. Upstream Harbor link supplied; no separate event starter kit in those posts. | Package the environment and obtain a scored model run. Confirm judging model/budget and source API access elsewhere. [Update](docs/afterquery-update-2026-11-14.md) |
| [OpenAI](https://hackjunction.app/participate/45/hackerpacks/70) | **$100 / 2,500 Codex usage credits per participant**, 30 days after redemption, one-use personal link; works on Free accounts | Development tooling. **This offer excludes API credits and a paid subscription.** Separate from the prize above. |
| [Google DeepMind](https://hackjunction.app/participate/45/hackerpacks/68) | Gemini API credits; amount not specified. [Apply once per team](https://forms.gle/bByXvjGkW9WZuYwW9). Challenge page says up to **400 teams**, participants 18+ | Apply early if Gemini is a serious option. Access instructions are supplied to eligible teams. |
| [Anthropic](https://hackjunction.app/participate/45/hackerpacks/67) | **$20 Claude API credits per participant**; redemption link in the resource entry | Development evaluations or additional model comparisons, subject to AfterQuery harness rules. |
| [Modal](https://hackjunction.app/participate/45/hackerpacks/62) | **$100 CPU/GPU credits per participant**, valid one year after redemption; rechecked Saturday 02:05. Sölvi's request is processing, not yet a confirmed balance. | Run isolated episodes, evaluations and hosted models. Current Harbor docs list Modal support for Docker Compose tasks; Lightlag compatibility still needs a real test. See the compute/API distinction below. |
| [Verda](https://hackjunction.app/participate/45/hackerpacks/71) | **€200 credits**, signup + claim form; inference API, CPU/GPU instances, clusters, containers and batch jobs | Alternative compute platform. Verda's tech brief also advertises a hosted NVIDIA Nemotron endpoint. |
| [Featherless API](https://hackjunction.app/participate/45/hackerpacks/51) | **$50 API credits** via the Junction coupon; hosted open-weight models | Fast route to comparing open models; Gemma prize page explicitly links this provider. |
| [Featherless GPU](https://hackjunction.app/participate/45/hackerpacks/52) | Bare-metal GPU credits for **selected teams**, amount unspecified; discuss needs with their representatives | Optional training compute; availability is not guaranteed for everyone. |
| [Aiven](https://hackjunction.app/participate/45/hackerpacks/66) | **$50 signup credits**, templates and on-site mentors | Managed storage, event analysis or hosting if the selected environment needs it. |
| [CRACI](https://hackjunction.app/participate/45/hackerpacks/64) | **€1,000 credits per team** for CI/CD or compute; invite code from booth/channel; GitHub integration | Reproducible evaluation CI. Requires setup and repository access; a simple runner switch alone is not a competitive prize story. |
| [Context.dev](https://hackjunction.app/participate/45/hackerpacks/60) | **50,000 credits per team, no expiry, no card**; search, scraping, structured extraction, monitors and MCP | Relevant only if live-web inputs are central. Freeze/version evaluation inputs so repeated runs remain comparable. |
| [Exa](https://hackjunction.app/participate/45/hackerpacks/49) | **$50 credits per participant**; search, contents and research tools | Research-grounded environments, if chosen. No separate Exa prize was listed among the 19 tech challenges inspected. |
| [Oxylabs](https://hackjunction.app/participate/45/hackerpacks/61) | First month of the **$500 Flexible plan discounted fully**; card required, subscription renews unless cancelled | Live search/scraping if essential. It adds billing administration and mutable data to an otherwise self-contained benchmark. |
| [MariaDB](https://hackjunction.app/participate/45/hackerpacks/69) | Database, Wikipedia datasets, vector/RAG and system-versioning examples; credited publication of selected work | Potential episode/history storage or dataset-backed tasks. No cash amount confirmed in this entry. |
| [IronShard](https://hackjunction.app/participate/45/hackerpacks/59) | Event storage, S3/MCP, dataset forks, large-artifact submission with judge access | Useful for trajectory datasets/model weights too large for Git; not required for a small simulation. |
| [Cloudinary](https://hackjunction.app/participate/45/hackerpacks/63) | Free tier, image/video APIs and mentors | Only compelling if visual replay/media processing becomes a core product feature. |
| [Arduino](https://hackjunction.app/participate/45/hackerpacks/65) / [Hardware Lab](https://hackjunction.app/participate/45/hackerpacks/57) | Borrowable UNO Q kit, camera and sensors; [hardware booking](https://2026.hackjunction.com/hardware) | Consider only if we deliberately select a physical environment. Hardware adds reproduction and availability constraints. |
| [Wendy](https://hackjunction.app/participate/45/hackerpacks/56) | Open-source deployment tools for robots/edge devices; simulator available | Useful for a robotics direction, not a dependency for our current software-environment ideas. |
| [Qualia](https://hackjunction.app/participate/45/hackerpacks/53) | Robot-demo episode curation; temporary event environment closes after **7 days** | Relevant to robot training data; export anything worth keeping. |
| [Scailab](https://hackjunction.app/participate/45/hackerpacks/50) | Free event Scaipipe access by form; synthetic vision data, annotation, training/evaluation | Relevant if we select a computer-vision environment. |

## Modal compute versus model API costs

Modal's current Harbor example uses `harbor run --env modal`, and Harbor lists Modal support for multi-container tasks through Docker-in-Docker Compose. This is a documented integration path for our sidecar-based task, not a verified Lightlag deployment. Pin the tested Harbor version and check lifecycle, artifact collection and verifier behavior. [Modal example](https://modal.com/docs/examples/harbor_evals), [Harbor support table](https://docs.harborframework.com/tasks/multi-container)

Dedicated Modal endpoints are billed for compute; Shared Endpoints are billed per token. Standard plan-included credits do not cover Shared Endpoint tokens. The Junction offer describes CPU/GPU credits, and its form did not establish separate token-API coverage, so budget it as compute until that is confirmed. Calls to an external model provider need that provider's API access/budget. [Modal endpoint modes](https://modal.com/docs/guide/endpoints), [Shared Endpoint pricing](https://modal.com/docs/guide/shared-endpoints)

## Other tech prizes and their conditions

| Challenge | Listed reward | Important condition / relevance |
|---|---|---|
| [CRACI](https://hackjunction.app/participate/45/tech-challenges/42) | 1st: LEGO per member; 2nd: 24 Red Bulls per member; 3rd: Slush lunch invite; top 5: 50,000 build minutes per member and interview opportunity | CI must run on CRACI. Judging rewards technical depth and creative use of SBOMs, fixes, provenance/traces/API, not just choosing its runner. |
| [Context.dev](https://hackjunction.app/participate/45/tech-challenges/44) | €750 / €250 / swag | At least one API endpoint in the core flow; its data must visibly drive the demo; repo/demo and endpoint explanation. |
| [Oxylabs](https://hackjunction.app/participate/45/tech-challenges/32) | €1,000 Apple voucher per winning team + $500 product credits per member | At least one live search/scrape call during demo, source URLs, explanation of endpoints. |
| [Cloudinary](https://hackjunction.app/participate/45/tech-challenges/41) | $500 Amazon gift cards **per winning team member** | Meaningful use of one of the four specified hackathon tools; CDN alone insufficient. **Separate [submission form](https://cld.media/hackathon-survey) required.** |
| [Arduino](https://hackjunction.app/participate/45/tech-challenges/45) | UNO Q + Plug and Make kit per winning member | Working hardware/edge AI. **Also publish on Arduino Project Hub with tag Junction Finland 2026.** |
| [Atech](https://hackjunction.app/participate/45/tech-challenges/29) | Pro Atech kit for winner; kits/swag for runners-up | Actual Atech modules and live hardware demo; public repo/export, short demo/video and Discord summary. |
| [MongoDB Atlas / MLH](https://hackjunction.app/participate/45/tech-challenges/55) | M5Stack IoT kit per winning member | Build with Atlas; $50 student credit or free tier offered. |
| [Vultr / MLH](https://hackjunction.app/participate/45/tech-challenges/54) | M5Stack mini programmable monitor | Meaningful use of Vultr; credit amount not stated in the captured brief. |
| [Tiger Data / MLH](https://hackjunction.app/participate/45/tech-challenges/53) | Stream Deck Mini | Time-series/PostgreSQL analytics; plausible for evaluation telemetry only if needed. |
| [Entire / MLH](https://hackjunction.app/participate/45/tech-challenges/51) | Prize not confirmed from captured brief | Sessions, Graph and/or Brain for AI collaboration. Conceptually relevant to team coordination, but introducing another collaboration stack tonight has a cost. |
| [Solana / MLH](https://hackjunction.app/participate/45/tech-challenges/52) | Unruggable hardware wallets per winning member | Blockchain use; weak fit for our current ideas. |
| [ElevenLabs / MLH](https://hackjunction.app/participate/45/tech-challenges/50) | Wireless earbuds | Meaningful audio integration; weak fit unless voice is central to the environment. |

## Tonight's actions

1. Follow [Ved's updated Harbor contract](docs/afterquery-update-2026-11-14.md), confirm the required evaluation settings with mentors, and secure API access from another provider; AfterQuery has withdrawn its inference-credit offer.
2. If interested, have one teammate request Gemini credits promptly; places are limited to 400 teams. Each teammate can inspect their personal Codex offer.
3. Pick one environment first, then choose Modal or Verda based on the compute we actually need. Keep a second model prize conditional.
4. For NVIDIA, ask which hosted endpoint serves the **required Super VL model**; the example model mismatch needs clarification.
5. Keep evidence of meaningful sponsor use and note any separate submission requirement. Do not assume checking a box guarantees eligibility.
6. Save the preliminary project draft by 23:59; target 23:45 and verify it appears under Your Submissions. The organizer clarified that a draft is sufficient tonight; final submission remains Sunday 10:00.
