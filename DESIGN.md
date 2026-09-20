# AI Interviewer Design Notes

Source reference: getdesign.md presents DESIGN.md files as compact product design systems: visual philosophy, tokens, spacing, typography, components, interactions, and the reason a product's interface works.

## Product Positioning

AI Interviewer should feel like a focused interview studio, not a settings form. The first screen must guide one decision at a time, then move into a working interview room with video, voice, timing, notes, STT, and follow-up questions visible.

The product has two halves, and the interface must make both legible: the
**interview** (what is being asked right now) and the **assessment** (what the
answers were worth). A screen that shows only the first is a question reader; a
screen that shows only the second is a grading tool. The workspace runs the
interview with the assessment beside it; the report screen is where the
assessment becomes the subject.

## Borrowed Principles

- From AI voice products: make audio feel tangible with signal visuals, clear voice status, and explicit model/fallback states.
- From precision workflow products: keep controls dense, aligned, and predictable. Avoid decorative clutter.
- From fintech onboarding: use one-step decisions, strong CTAs, progress rails, and review before start.
- From premium productivity tools: use a restrained dark workspace, high contrast, stable dimensions, and direct status copy.

## Visual System

- Framework: Qt 6 (PySide6, Fusion style). All colors, spacing, radii, and
  type sizes come from design tokens in `ai_interviewer/ui/theme/tokens.py`;
  the stylesheet is generated from tokens (`theme/qss.py`) — no hex values in
  widget code.
- Theme: two palettes, dark (interview-studio default look) and light, with a
  System/Light/Dark mode switch. "System" follows the Windows color scheme
  live. Both palettes keep body text at WCAG AA contrast (enforced by test).
- Accents: blue voice accents and teal confirmation accents in both themes.
- Score bands: one color per rubric band (`band_outstanding` … `band_insufficient`),
  resolved through `tokens.band_color()`. A score's color must be identical
  wherever it appears — dial, meter, radar, chip, exported HTML — so the band is
  readable without reading the number. Never restate a band in a second hue.
- Meters: an unfilled track (`track`) plus a band-colored fill. A score that has
  not been measured renders an em dash on the empty track, never a zero-length
  bar, because "not scored" and "scored zero" are different facts.
- Surfaces: no floating nested card stacks. Use one main shell, stage surfaces, selected tiles, and compact inspector panels.
- Typography: Segoe UI (Malgun Gothic fallback for Korean), strong hierarchy, no viewport-dependent font sizing.
- Icons: Lucide SVGs (`assets/icons/`), stroke-tinted per theme at the device
  pixel ratio — no emoji glyphs.
- DPI: per-monitor high-DPI aware (Qt 6 PassThrough rounding); no fixed-pixel
  bitmaps.
- Motion: short setup transitions only (150 ms step fade). No heavy animation that competes with TTS or recording.
- Scoring widgets: `ui/widgets/scoring.py` owns the three painted primitives —
  `ScoreDial` (one headline number as an arc), `ScoreBar` (the row unit of every
  breakdown), `CompetencyRadar` (the shape of a profile). All three read tokens
  live and repaint on theme change; none of them knows how a score was produced.
  The radar refuses to draw below three axes and the caller falls back to bars,
  because a two-axis radar is a line pretending to be a shape.
- Chips carry metadata, not emphasis: competency, stage, engine, depth. Accent
  chips are reserved for the one fact that identifies the row.
- Media: interviewer video is the primary visual. A single generated portrait
  photo is also supported and shown with a subtle breathing zoom so it reads as
  a living presence (see `docs/interviewer_asset_prompt.md`). When neither exists,
  use the QPainter interviewer placeholder and audio signal canvas.

## Interaction Rules

- App startup must not load Qwen. Loading starts only on sound test or interview start.
- Analysis never blocks the interview. Scoring runs on a worker thread; the
  interviewer can advance, replay, or re-record while a verdict is pending.
- A score is never invented to fill a panel. With no answer the coach panel says
  so; with no provider it shows the rule-based verdict and labels the engine.
- The engine that produced a verdict is always visible, and a fallback to the
  rule engine is stated with its reason rather than silently substituted.
- Cloud analysis takes consent in a dialog that names what is sent, before the
  first call — never at the first scored answer.
- A follow-up is offered, not forced: the app proposes the question and the
  interviewer decides whether to ask it.
- Speaker and model are selected from known options, never free text.
- Korean and English modes must not mix question packs.
- Fallback quality drops must be visible in runtime status and warnings.
- Double-click video enters fullscreen; Esc or double-click exits.
