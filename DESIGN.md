---
name: "Lightlag Traverse — Homepage"
description: "Adopted homepage design, extracted from tools/traverse_farm/home_preview; authority excludes the replay viewer and other product surfaces."
colors:
  ground: "#161819"
  surface: "#202324"
  surface-hover: "#2b2e2f"
  ink: "#f1f0e9"
  muted: "#b1b4b2"
  quiet: "#929895"
  line: "#3d4241"
  accent: "#e9b752"
  accent-hover: "#f3c975"
  on-accent: "#1c211d"
  danger: "#ffae98"
typography:
  display:
    fontFamily: "Barlow Condensed, sans-serif"
    fontWeight: 600
    lineHeight: 0.99
    letterSpacing: "-0.015em"
  headline:
    fontFamily: "Barlow Condensed, sans-serif"
    fontSize: "34px"
    fontWeight: 600
    lineHeight: 1.15
  body:
    fontFamily: "Barlow, sans-serif"
    fontSize: "17px"
    fontWeight: 400
    lineHeight: 1.5
  action:
    fontFamily: "Barlow, sans-serif"
    fontSize: "17px"
    fontWeight: 600
    lineHeight: 1.5
  label:
    fontFamily: "Barlow, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
  form-support:
    fontFamily: "Barlow, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.4
  data:
    fontFamily: "ui-monospace, 'SFMono-Regular', Consolas, monospace"
    fontSize: "0.88em"
    fontWeight: 400
    lineHeight: 1.5
  world-link:
    fontFamily: "ui-monospace, 'SFMono-Regular', Consolas, monospace"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  control: "3px"
spacing:
  "4": "4px"
  "8": "8px"
  "12": "12px"
  "16": "16px"
  "20": "20px"
  "24": "24px"
  "32": "32px"
  "40": "40px"
  "56": "56px"
  "64": "64px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.on-accent}"
    typography: "{typography.action}"
    rounded: "{rounded.control}"
    padding: "12px 24px"
  button-primary-hover:
    backgroundColor: "{colors.accent-hover}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.action}"
    rounded: "{rounded.control}"
    padding: "12px 20px"
  button-secondary-hover:
    backgroundColor: "{colors.surface-hover}"
  input-world:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "12px 16px"
    height: "50px"
    width: "100%"
  navigation-link:
    textColor: "{colors.muted}"
    typography: "{typography.label}"
  navigation-link-hover:
    textColor: "{colors.ink}"
  featured-world-link:
    textColor: "{colors.ink}"
    typography: "{typography.world-link}"
  featured-world-link-hover:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.accent}"
  controller-row:
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    padding: "16px 0"
  disclosure:
    textColor: "{colors.muted}"
    typography: "{typography.body}"
    padding: "16px 0"
---

# Design System: Lightlag Traverse — Homepage

## Overview

**Creative North Star: "Mission control"**

The user adopted this homepage direction on 15 November 2026 and requested its deployment. This record is extracted from the reviewed implementation in `tools/traverse_farm/home_preview/` and applies to the homepage being integrated into `tools/traverse_farm/live_app.py`. Its authority is limited to that homepage; the replay viewer and other repository surfaces keep their existing designs.

The user selected dark charcoal, real terrain, and restrained amber. The built preview expresses that direction through quiet dark surfaces, compact Barlow Condensed headings, readable Barlow prose, square replay imagery, and flat rows divided by fine rules. The real terrain supplies the visual detail; the interface uses tone and spacing to stay legible around it.

The source of truth is the preview's `style.css`, `index.html`, `home.js`, and `assets/fonts.css`. The [surface brief](docs/superpowers/specs/2026-11-15-homepage-preview-design.md) retains the page strategy. The terrain and font provenance live beside their assets. The companion `.impeccable/design.json` records component examples and responsive behavior; its generated color ramps are panel visualizations, not additional implementation colors.

**Key Characteristics:**

- Dark charcoal ground with warm, readable text.
- Amber for the replay action, focus, useful links, and reference-planner identity.
- Condensed headings, open body copy, and tabular numeric details.
- Real replay terrain with square corners and a quiet action overlay.
- Flat sections and controller rows with thin separators.

## Colors

The palette pairs charcoal neutrals with the viewer's warm amber. Token names preserve the source CSS custom properties.

### Primary

- **Mission amber** (`accent`): the main replay action, keyboard focus, selection, input caret, reference planner, and links in the world notes.
- **Lit amber** (`accent-hover`): the replay action's hover fill.
- **Dark amber ink** (`on-accent`): text and the play symbol on an amber fill.

### Neutral

- **Charcoal ground** (`ground`): page ground and the terrain action overlay at rest.
- **Control charcoal** (`surface`): inputs, the secondary action, and world-link hover surfaces.
- **Raised charcoal tone** (`surface-hover`): the secondary action's hover fill; this is a color change without elevation.
- **Warm white** (`ink`): headings, principal text, and control text.
- **Soft gray** (`muted`): explanatory copy, placeholders, and navigation.
- **Quiet gray** (`quiet`): supporting notes, counts, conditions, and footer copy.
- **Divider gray** (`line`): section rules, row separators, and resting input/control borders.

### Feedback

- **Warm error** (`danger`): the invalid world-number border and its explanatory message. It is a feedback color, not another decorative accent.

**The Amber Action Rule.** Keep amber tied to the uses already present: a replay action, focus or selection, useful links, and the reference-planner identity. The custom-world action uses the charcoal secondary treatment.

## Typography

**Display Font:** Barlow Condensed, with a sans-serif fallback.

**Body Font:** Barlow, with a sans-serif fallback.

**Label/Mono Font:** The system monospace stack recorded in `typography.data`, for world numbers and measurements.

**Character:** The condensed headings relate the homepage to the replay viewer. Body copy and controls retain Barlow's regular proportions. Local WOFF2 files load through `assets/fonts.css` with `font-display: swap`; the heading uses the supplied semibold face.

### Hierarchy

- **Display:** The main heading uses the `display` role. Its source size is fluid (`clamp(60px, 5.6vw, 82px)`), with the responsive overrides below. The fluid value lives in prose and the sidecar because the [frontmatter dimension format](https://raw.githubusercontent.com/google-labs-code/design.md/main/docs/spec.md) accepts static dimensions.
- **Headline:** Section headings use `headline`; the small-screen override is recorded in Layout.
- **Body:** `body` is the page default. The introduction uses a larger size (`19px`), a moderate measure (`34ch`), and the muted tone. Controller descriptions use a slightly smaller size (`16px`) and a bounded measure (`54ch`).
- **Action:** `action` provides the semibold text of both buttons and controller names.
- **Label:** `label` covers form labels and desktop navigation. Supporting form text uses `form-support`; other minor notes are small (`14px`) and inherit the page line height.
- **Data:** Inline numbers use `data`; featured-world links use `world-link`. Both retain tabular figures. The world links become smaller (`13px`) on small screens.

**The Read Before Data Rule.** Use Barlow for prose and controls, Barlow Condensed for page and section headings, and monospace for numeric details. Preserve sentence case in the interface.

## Layout

The centered shell has a maximum width (`1328px`). At ordinary desktop widths it leaves equal side margins (`56px`). The spacing entries above record repeated measurements in the actual stylesheet; they are an extracted vocabulary, not a requirement that every gap use a single interval.

The desktop introduction and terrain form an unequal two-column grid (`0.78fr / 1.5fr`), with a fluid gap (`clamp(40px, 5vw, 80px)`) and generous vertical padding (`64px` above, `56px` below). The custom-world section uses two columns (`1fr / 1.12fr`) and a gap (`64px`); the experiment uses two columns (`0.8fr / 1.2fr`) and a wider gap (`100px`). The form's field and submit action stay on one horizontal row, with a gap (`12px`).

| Viewport rule | Observed changes |
| --- | --- |
| At least 1600px | Introduction/terrain gap and top padding become (`88px`); bottom padding becomes (`80px`). |
| At most 1100px | Shell side margins become (`32px`). Introduction/terrain columns become (`0.9fr / 1.2fr`), gap (`40px`), padding (`52px` above / `48px` below), main heading (`64px`), introduction (`18px`). World navigation sits below its label. Custom-world gap becomes (`40px`); experiment gap becomes (`56px`). |
| At most 760px | Shell side margins become (`20px`). Introduction, custom world, and experiment become single-column sections. Main heading becomes (`clamp(56px, 11vw, 72px)`); section headings become (`30px`). The masthead is shorter (`76px` minimum), and its experiment link is hidden while Source remains visible. World links return beside their label. Controller rows all receive a top separator. |
| At most 380px | Shell side margins become (`16px`). The world chooser may wrap, the form gap becomes (`8px`), and the secondary action's horizontal padding becomes (`12px`). |

On small screens, the introduction/terrain gap is (`32px`), custom-world gap (`24px`), and experiment gap (`32px`). The form keeps its side-by-side field and action through the checked narrow width (`320px`). The source gives interactive navigation links a minimum height (`44px`), buttons a minimum height (`50px`), and the input a fixed height (`50px`).

**The Shared Edge Rule.** Align the masthead, main sections, and footer to the same responsive shell. Keep controller descriptions and counts in rows within that shared composition.

## Elevation & Depth

There are no box shadows, text shadows, blur layers, or decorative gradients in the preview stylesheet. Depth comes from the actual terrain image, modest differences between the page and control tones, and single-pixel separators. Hover states change color; a pressed action moves down slightly (`1px`).

**The Flat Surface Rule.** Keep the preview's sections and controller rows flat. Use spacing, tone, and thin rules to establish hierarchy.

## Shapes

Controls and the terrain's action overlay use the small `control` corner radius. Terrain imagery and section boundaries remain square. Borders and separators are thin (`1px`); the preview has no pill controls or enclosed controller cards.

**The Square Terrain Rule.** Keep the replay image rectangular and square-cornered, using its captured aspect ratio (`1070 / 585`). The small control radius belongs to interactive elements and the image's action label.

## Components

### Buttons

The replay action is clear and compact. It uses `button-primary`, an inline SVG play symbol (`17px` square), and an internal gap (`12px`). Hover changes to `button-primary-hover`. The secondary world action uses `button-secondary`, a divider-tone border (`1px`), and its own hover tone. Both have a minimum height (`50px`) and a slight pressed displacement (`translateY(1px)`).

Color and press feedback transition quickly (`150ms ease-out`). The preview's reduced-motion query removes all transitions and animations. It does not define a loading or disabled visual variant: the form validates and navigates immediately.

### Inputs / Fields

The world input uses `input-world`, a divider-tone border (`1px`), a visible label, and the amber caret. Hover changes the border to Quiet gray. Keyboard focus uses the shared outline. The form marks invalid input with the Warm error border and a text message, using `aria-invalid` and a polite live region. Editing clears the error state. The field's note and reserved error line keep feedback close to the control.

### Navigation

Masthead links use the muted text treatment, a minimum height (`44px`), and an underline on hover. Their desktop gap is (`32px`), reducing to (`16px`) on small screens. The wordmark remains text, with semibold Lightlag and a quieter regular Traverse.

Featured-world links are plain numeric targets rather than pills. Their minimum dimensions are (`51px` wide / `44px` high), with a compact gap (`8px`). Hover adds a Control charcoal surface and amber text. Small screens reduce their minimum width (`45px`) and gap (`4px`); the responsive arrangement is recorded in Layout.

### Terrain replay

The real replay capture fills the available width and retains its aspect ratio. A ground-colored action label sits at the lower right, turning amber when its image link is hovered. World identity and dimensions sit above the image; other world destinations sit immediately below. The source asset `assets/world-2027.png` is accompanied by `assets/world-2027.provenance.json`.

### Controller rows

Each row pairs a semibold controller name with a small, quiet rover count, followed by a muted description. Rows use vertical padding (`16px`) and a single-pixel separator. The first desktop row omits its top padding and separator; the narrow layout restores both. Reference-planner text receives amber without a filled container.

### Field notes disclosure

A native details/summary element contains the optional world notes. Its summary has a generous minimum height (`56px`) and turns from muted to principal text on hover. The browser's disclosure marker remains native. Expanded notes use world links beside explanatory text, changing to stacked lines on small screens.

**The Visible Focus Rule.** Links, buttons, inputs, and the disclosure summary use an amber outline (`2px`) with a clear offset (`5px`). Preserve the keyboard-accessible skip link and visible form label.

## Do's and Don'ts

### Do:

- **Do** apply this adopted direction to the homepage, using the reviewed implementation in `tools/traverse_farm/home_preview/` as its source.
- **Do** preserve the real replay image and its source provenance.
- **Do** keep the amber replay action visually primary and the custom-world action secondary.
- **Do** preserve the shared shell, responsive stacking, and flat controller rows.
- **Do** preserve visible keyboard focus, labeled input, text validation feedback, and reduced-motion behavior.

### Don't:

- **Don't** extend this homepage design authority to the replay viewer or unrelated product surfaces.
- **Don't** replace the observed terrain with invented scenery or an unrelated illustration.
- **Don't** turn controller rows into repeated elevated cards or pill-shaped containers.
- **Don't** promote the sidecar's generated tonal ramps into source tokens; the frontmatter records the implemented palette.
