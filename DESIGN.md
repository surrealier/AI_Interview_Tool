# AI Interviewer Design Notes

Source reference: getdesign.md presents DESIGN.md files as compact product design systems: visual philosophy, tokens, spacing, typography, components, interactions, and the reason a product's interface works.

## Product Positioning

AI Interviewer should feel like a focused interview studio, not a settings form. The first screen must guide one decision at a time, then move into a working interview room with video, voice, timing, notes, STT, and follow-up questions visible.

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
- Surfaces: no floating nested card stacks. Use one main shell, stage surfaces, selected tiles, and compact inspector panels.
- Typography: Segoe UI (Malgun Gothic fallback for Korean), strong hierarchy, no viewport-dependent font sizing.
- Icons: Lucide SVGs (`assets/icons/`), stroke-tinted per theme at the device
  pixel ratio — no emoji glyphs.
- DPI: per-monitor high-DPI aware (Qt 6 PassThrough rounding); no fixed-pixel
  bitmaps.
- Motion: short setup transitions only (150 ms step fade). No heavy animation that competes with TTS or recording.
- Media: interviewer video is the primary visual. When no video file exists, use a generated interviewer placeholder and audio signal canvas.

## Interaction Rules

- App startup must not load Qwen. Loading starts only on sound test or interview start.
- Speaker and model are selected from known options, never free text.
- Korean and English modes must not mix question packs.
- Fallback quality drops must be visible in runtime status and warnings.
- Double-click video enters fullscreen; Esc or double-click exits.
