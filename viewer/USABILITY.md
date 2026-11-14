# Mission-control demo improvements

> **Superseded on 14 November.** Kristján found this layout too squashed and asked for the four full-screen views back. The briefing strip, the transport strip, the per-panel buttons, the mission menu, the guide and the phone layouts described below were removed again. Two ideas survive as keys with no panels: jump between events (`,` and `.`) and zoom one screen (`Z`). This file is kept as the record of that increment; the current controls are in [README.md](README.md).

Open `mars-demo.html` for the standalone demo, or serve `viewer/mars/` for development. The data builder and saved outcomes remain the source of truth.

The default desktop layout gives Mars more space, with Earth's delayed view alongside and the map and recorded tool activity below. The persistent objective explains sample collection, energy and final scoring. Samples collected and the latest mission event update as the replay advances. The opening menu uses focusable mission buttons; the guide explains the views, map symbols and controls.

## Controls

- **Play / Pause**, **Restart**, **Back / Forward one tick**, speed and the timeline are visible buttons. Restart pauses at tick zero. Play at the end replays the mission.
- **Next event / Previous event** jump to recorded sample, discovery, safety or battery events, or the start/end. Jumps pause playback. Viewer-generated reserve warnings use the existing reserve calculation.
- **Compare runs** keeps the same tick and shows all four runs. Selecting an individual run keeps that comparison tick too.
- **Overview / Follow rover** changes the Mars camera. The expand button on each panel focuses that view; Escape restores the layout.
- At phone widths, **Mars / Earth / Map / Console** tabs show one readable view. Compare mode scrolls through all four runs.
- **?** opens the mission guide. **F** toggles full screen.

Keyboard: Space plays/pauses; arrows step; `[` and `]` jump between events; `R` restarts; `C` changes camera; `M` compares; `1`–`4` switch run; `N` switches mission; `-` and `+` change speed. Native input/button behavior takes priority when a control has focus. The guide blocks background shortcuts, and mission selection keeps focus within its buttons. Opening the mission menu, opening the guide or hiding the tab pauses playback. A manual action cancels a pending unattended-loop restart.

## Verification

14 November 2026: Chrome browser checks exercised mission selection, mouse and keyboard stepping, immediate slider synchronization, play/pause, event navigation, run comparison, camera/focus controls, guide focus and 768/390-pixel layouts. After integrating the reserve correction and the new Rocks mission, all twelve included outcomes were compared against the saved replay rewards. All 38 browser checks passed, including opening the standalone file with networking disabled: no runtime errors and no HTTP requests. The 29 Python viewer tests passed. Screenshots were inspected locally; they are QA artifacts, not new evidence of model performance.

This is replay presentation. It does not change mission rules, the benchmark reference, saved model decisions or scoring.
