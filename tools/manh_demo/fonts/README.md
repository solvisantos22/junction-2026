# Typefaces used when the film is recorded

Kristján's pages ask for DIN Condensed, the system sans and the system mono of a Mac. So that the film can be built on any machine, and looks the same on each, these open typefaces stand in for them (see `../pages.py`):

| Files | Typeface | Stands in for | Licence |
|---|---|---|---|
| `BarlowCondensed-500/600/700.ttf` | Barlow Condensed | DIN Condensed | SIL Open Font License 1.1, `OFL-barlowcondensed.txt` |
| `Inter-400/500/600.ttf` | Inter | the system sans | SIL Open Font License 1.1, `OFL-inter.txt` |
| `JetBrainsMono-400/500.ttf` | JetBrains Mono | the system mono | SIL Open Font License 1.1, `OFL-jetbrainsmono.txt` |

They are the Latin subsets published by Fontsource (packages `@fontsource/barlow-condensed`, `@fontsource/inter`, `@fontsource/jetbrains-mono`, version 5.3.0), unchanged. Nothing is installed on the machine: the browser is started with a fontconfig file that adds this folder.
