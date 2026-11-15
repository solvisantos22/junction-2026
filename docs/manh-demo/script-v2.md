# Script v2: plain words, a cliffhanger after every beat

Sunday 15 November 2026, about 04:30 Helsinki. Manh / Claude Code (demo cut chat). **A draft for the team to change and record in its own voice**; nothing here is final, and the clips it names are separate drafts, not one film.

Written to Manh's notes of tonight: no jargon (a viewer does not know what a tick is), say what this is, why and for whom before anything else, start in orbit and land on the map, and end every beat on a question the next beat answers.

## The one big hook

Everything in the film hangs on one question. Three ways to put it; the script below uses the first.

| Pick | The hook | Why |
|---|---|---|
| **1 (used)** | *Who would you trust to drive, when everything you see has already happened?* | It puts the viewer in the seat first, so "is this for me?" is answered before any number |
| 2 | *One of the world's most capable AI models drove this rover to its death, 13 metres from home.* | The strongest picture we have; it works as the second beat instead |
| 3 | *AI can write the code. It can't yet plan the day.* | It is the conclusion; said first, it gives the ending away |

## The script

About 270 words: 1:50 spoken calmly, with room for the pauses. Each row is one clip. **Bold** is the cliffhanger that closes the beat.

| # | Picture (clip) | Say | On screen |
|---|---|---|---|
| 1 | **In orbit.** Mars turning in space, the sun on its edge | Imagine driving a car where everything you see happened three seconds ago, and the car obeys you three seconds late. That is every day on Mars. **So who do you trust to drive?** | nothing; let the planet carry it |
| 2 | **The dive.** Down through the dust onto our map; the title lands | We built that day. One rover, one day of sunlight, rocks to collect, and one rule: be home before the battery dies. **Then we handed the keys to one of the most capable AI models in the world.** | LIGHTLAG TRAVERSE |
| 3 | **13 metres.** Behind the rover as its battery runs out | This is its rover. Thirteen metres from home, twenty-one samples on board, and it will not make it. **Nothing broke. So what went wrong?** | 13 M FROM HOME · BATTERY 0% |
| 4 | **The ground.** The slip, the missed sample, the stop on the slope | Mars doesn't play fair. Wheels slip. Miss a rock by three centimetres: no points. Climb too steep: the rover freezes and forgets its orders. **But that isn't what killed it.** | 3 CM · TOO STEEP |
| 5 | **The sun.** Our driver waits; the AI's rover drives on and dies | The sun did. It is the only fuel. Our driver sees the battery fall, stops, and waits for light. The AI keeps driving. A short wait would have saved it. **One bad model? We asked the rest.** | THE ONLY FUEL IS THE SUN |
| 6 | **The lineup.** Three labs, three tiers, nine models roll out | Three labs. Nine models. From the fastest to the most powerful. **One of them must do better… right?** | the logos and names |
| 7 | **The scores.** The bars; ours on top | None beat our driver. It brought home 48% of everything out there, and never lost a rover. **So what is it? Not an AI.** | 48% · NEVER LOST A ROVER |
| 8 | **What our driver is.** The planner card | It's a planner. Plain code that works out the whole day before the wheels turn. **Lucky map? We wondered too.** | A PLANNER, NOT A MODEL |
| 9 | **At scale.** The 300 worlds filling in | So we ran eighteen hundred more match-ups on Modal, on worlds nobody had seen. The planner won 1,780. **Can a machine learn it instead?** | 1,780 / 1,800 · MODAL |
| 10 | **Our trained agent.** The learning curve | We trained one from scratch. It beat every Claude run, and still lost to the planner. | OUR RL AGENT · 37% |
| 11 | **The end card.** | AI can write the code. It can't yet plan the day. **Can your agent make it home?** | CAN YOUR AGENT MAKE IT HOME? |

## Words to keep out

| Instead of | Say |
|---|---|
| tick | nothing: "late", "a short wait", "a moment" |
| telemetry, position fix | "what you see", "where the rover says it is" |
| the reference | "our driver", then "a planner" once it is revealed |
| score 0.476 | "48% of everything out there" (the share of the samples' value brought home) |
| lost a rover | "the battery ran out", "it didn't make it" |
| campaign, site, world | "day", "map" |
| Harbor, OpenCode, PPO, MCP | leave out of the voice; they stay on screen, small, for the judges who look for them |

## Check before recording

Every line is true today, with these to confirm when the last runs are in:

- **"Nine models" and "None beat our driver"** depend on the tier comparison still running in another chat. So far only the fastest tier of GPT and Gemini has finished: Gemini 4 Hydrogen scored about 0.40 and 0.44 on the same three maps, the closest anyone has come to the planner's 0.476; GPT-6 Luna 0.11 to 0.20. If a run passes 0.476, beat 7 has to change. If the top tiers cannot be run in time, say "seven models" or name the three labs without a count.
- **"It beat every Claude run"** is Sölvi's matched result (PPO 0.366 against the best Claude 0.293, the same three maps). It learned which rock to go for next; the steering under it is hand-written. The line does not say more than that, and should not.
- **"Three seconds"** in beat 1 is a picture for the viewer, not the task's unit; the task counts in steps. Keep it as "imagine".
- **"48%"** is the planner's 0.476 on the three maps; "never lost a rover" holds there and on the 300 fresh worlds.

## Clips

Each beat is its own draft clip in `tools/manh_demo/build/out/` (not in the repository while they are drafts). Accept, change or drop each one; nothing is stitched until you say so.
