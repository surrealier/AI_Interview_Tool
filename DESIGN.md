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

- Theme: dark interview studio with blue voice accents and teal confirmation accents.
- Surfaces: no floating nested card stacks. Use one main shell, stage surfaces, selected tiles, and compact inspector panels.
- Typography: Segoe UI, strong hierarchy, no viewport-dependent font sizing.
- Motion: short setup transitions only. No heavy animation that competes with TTS or recording.
- Media: interviewer video is the primary visual. When no video file exists, use a generated interviewer placeholder and audio signal canvas.

## Interaction Rules

- App startup must not load Qwen. Loading starts only on sound test or interview start.
- Speaker and model are selected from known options, never free text.
- Korean and English modes must not mix question packs.
- Fallback quality drops must be visible in runtime status and warnings.
- Double-click video enters fullscreen; Esc or double-click exits.
