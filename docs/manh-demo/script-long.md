# The long film: script and shot list

`manh_demo_long.mp4`, 8:35 (515 s). Sunday 15 November 2026. Manh / Claude Code (demo cut chat). A draft with a placeholder voice, written from the film as it was last built.

Manh asked for the two-minute film's idea told in depth and without hurry: what happens and why, how the models compare and why each lab did as it did, the reference in detail and why it is a fair one to measure against, and the learned agent as a baseline. The words are `LINES3` in [`tools/manh_demo/cut.py`](../../tools/manh_demo/cut.py); every number in them is counted from the saved runs at each build (`SAID3`).


## 0:00 · The hook

| From | Picture | Say |
|---|---|---|
| 0:00 | Mars from orbit, the dive, the landing, the title | Imagine driving a car where everything you see happened three seconds ago, and the car obeys you three seconds late. On Mars, that is every day. A signal from Earth takes minutes to arrive, so a rover cannot be steered. It has to be trusted. So who do you trust to drive? We built that day. One rover, one day of sunlight, and a map full of rocks worth collecting. And one rule above all: be home before the battery dies. |

## 0:30 · The game

| From | Picture | Say |
|---|---|---|
| 0:30 | Site 1 from above: ten rovers leave the lander | This is Lightlag Traverse. 600 metres of craters, sand and bedrock. 38 targets at sunrise, more appearing through the day, and never enough time to reach them all. Every rover starts at the lander with a full battery, and 420 steps of daylight. |
| 0:49 | Slide: the five tools and the six catches | The driver gets five tools: read the rules, read the map, read the telemetry, send commands, and let time pass. Then come the catches. Commands land late. The news from the rover is already old. Wheels slip, differently on every surface. Ground that is too steep stops the rover and wipes its orders. The only fuel is the sun. And the score is unforgiving. Come home, and keep everything. Stop short, and keep half. Run flat, and keep nothing. |

## 1:23 · The drivers

| From | Picture | Say |
|---|---|---|
| 1:23 | Slide: three labs, three tiers, nine models | Then we handed the keys to nine AI models from three labs: Anthropic, Google and OpenAI. From each lab, the fast model, the everyday one, and the flagship. Each gets the same task, the same five tools, and 45 minutes to write its own autopilot. No practice run. Three maps in a row. Surely one of them makes it home? |

## 1:48 · What goes wrong, one tier at a time

| From | Picture | Say |
|---|---|---|
| 1:48 | Behind GPT-6 Luna, site 3: the sample missed by 3 cm | Start with a fast one. GPT-6 Luna reaches for a rock, and misses. By 3 centimetres. The rover has to stand within 2.5 metres when the command lands, and the command lands late. 9 tries on this map. 1 rock. |
| 2:05 | Claude Sonnet 5.5 stopped on the scarp, site 3 | A bigger one. Claude Sonnet drives onto a slope too steep. The rover freezes, and every order it was carrying is wiped. It sends new ones, and freezes again. 30 times on this one map. When the day ends it is 72 metres from home, and its samples count half. |
| 2:24 | Behind Claude Opus 5.5, site 1: battery flat 13 m from home; its score-card | And a flagship. Claude Opus has had a good day: 21 samples on board, 13 metres from the lander. It will not make it. Battery flat. Zero points for the whole map. Nothing broke. So what went wrong? |
| 2:41 | Slide (Kristján's): in Claude's own words, with his verdict line | Ask the model. Its own closing report says the route planner only counted time. It never checked whether the battery would last. And its autopilot played all three maps in 45 seconds, without checking a single result in between. It did not fail at coding. It failed at planning the day. |
| 3:04 | Site 3: Gemini 4 Argon runs flat; a cut to the planner waiting for the sun | And it is not one lab's problem. Here Google's Gemini 4 Argon drives its battery flat, 16 metres from the lander, with most of the day still ahead. A wait of four steps for the sun would have saved it. On the same map, our own driver sees its battery fall to 9%, stops, and waits for light. |

## 3:24 · One that gets it right

| From | Picture | Say |
|---|---|---|
| 3:24 | Behind Gemini 4 Carbon in its best run, site 2: five samples in thirty steps | Not every run fails. This is the one that came within a hair: Gemini 4 Carbon, on its second run. On this map it brings home 26 samples, as many as our planner, and is back at the lander before dark. So the task can be done. The same model's third run never left the lander. |

## 3:44 · The scoreboard, and how each lab fails

| From | Picture | Say |
|---|---|---|
| 3:44 | Chart: every campaign run of all nine models against the planner | So how did all nine do? 25 live runs, three maps each. A dot is one run. The bar is the model's average. The gold line is our driver: 48% of everything on the maps, brought home. No run crosses it. One comes within a hair: Google's flagship, Gemini 4 Carbon, at 47.3. On average, Gemini 4 Hydrogen and GPT-6.1 Sol lead. Claude Sonnet and Opus sit in the middle. And at the bottom, the models that missed, or never moved. |
| 4:19 | Chart: how every site of every run ended, lab by lab, and what a run cost | Look closer, and every lab fails in its own way. Gemini is all or nothing. When its agents drive, they drive best. But 3 of 9 runs never left the lander: the agent used up its 45 minutes before its program drove a metre. OpenAI's flagship, GPT-6.1 Sol, is the steadiest of all nine: never lost, never idle. But on the first map it ended every run away from the lander, and kept half. Its smaller models come home with little on board. Claude writes its autopilot within minutes, and then loses rovers to the battery: four of them. Its fast model never left the lander at all. And the tiers? They do not decide it. Google's fast model, Gemini 4 Hydrogen, has the best average of all nine: 37%. Not because it drives better than its big brother. Carbon's best runs beat it. But all three of its runs had a program driving in time. On this task, finishing beats thinking longer. Price does not buy it either. A run cost from 3 cents to almost 2 dollars, and the best average came at 93 cents. |

## 5:35 · The reference: what it is and why it is a fair one

| From | Picture | Say |
|---|---|---|
| 5:35 | Slide (Kristján's, with the methods named): the planner's four parts, its battery over a day | So what is our driver? Not an AI. It is a planner: about 1,300 lines of plain Python, playing through the same five tools as everyone else. It does four things. An extended Kalman filter tracks where the rover really is, through the delay and the noise. It learns how each surface slips, from its own wheels. It prices every leg of every route, in time and in energy, against the sun. And it searches for the best day: which rocks, in which order, and home before dark. Then it plans again, every few steps. |
| 6:11 | Site 3: the planner turns for home; its score-card | Watch it work. By evening it turns for home with 19 samples and a third of its battery left, and reaches the lander 26 steps before dark. |
| 6:23 | Slide: five reasons this reference is a fair yardstick | Why is that a fair yardstick? It uses the same five tools, and nothing hidden. It is plain code that anyone can read. It gives the same score every time: on a laptop, on Modal, and through Harbor. It has never lost a rover. And it can be beaten: it leaves more than half of the value on the ground. |

## 6:46 · At scale: 300 fresh worlds

| From | Picture | Say |
|---|---|---|
| 6:46 | Chart: every model's best program on 300 fresh worlds | Lucky maps? We wondered too. So we took every model's best program and replayed it on 300 fresh worlds, on Modal. Worlds no model had seen. 2,700 match-ups. The planner scored higher in 95 of every 100, and lost no rover. The models' programs lost 154. And look at who holds up. Programs that scored 56% on the one map they were written for fall to the low forties on new ground. The planner holds 50. A program tuned to one map is not yet a driver. |

## 7:24 · A learned baseline

| From | Picture | Say |
|---|---|---|
| 7:24 | Behind the team's trained agent, site 1 | One more driver. Can a machine learn this, instead of being told? We trained small controllers from scratch on Modal. No language model: trial and error, over 47,000 practice missions. |
| 7:39 | Slide (Kristján's): the models that learn | Before training they bring home 8%. After, 36, on worlds they had never seen. On the campaign, every trained seed passes every Claude run. And there they stop: level with a simple greedy rule, and well short of the planner. We even trained a model to pick the planner's own strategy mid-mission. It gained less than half a point. |
| 8:04 | Slide: the two baselines side by side | So the task comes with two baselines. The planner is the bar to beat. The learned agent is an honest picture of where learning stands today. Bring your own model, and you know at once where it lands. |

## 8:19 · Try it

| From | Picture | Say |
|---|---|---|
| 8:19 | The end card (Kristján's) | One command reruns all of it, and a live demo on Modal lets you pick any world and watch eight drivers take it on. AI can write the code. It cannot yet plan the day. Can your agent make it home? |
