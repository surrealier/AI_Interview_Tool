# Interview Intelligence

How the app decides what a question is *for*, what an answer was worth, and what
to ask next. All of it lives in `ai_interviewer/intelligence/`, which is pure
Python and imports no GUI toolkit (`tests/test_no_qt_in_core.py` enforces that).

## The rule that shapes everything

**Every analyzer has an offline implementation, and an LLM can only improve on
it.** The app never depends on a model being present:

| Capability | Offline (always) | With a provider |
| --- | --- | --- |
| Question plan | keyword tagging of the question pack | a role-specific loop authored from a JD |
| Answer score | structural signals against the rubric | rubric judgement with cited reasons |
| Follow-up | the gap the answer left, phrased from a template | one question written for this answer |
| Report | computed scores + template guidance | the same scores with a written debrief |
| Delivery | measured locally from transcript + duration | *unchanged — never asked of a model* |

Delivery is the load-bearing example: pace and filler are **measured**, so a
model is never asked to guess them. When an LLM verdict comes back, the locally
measured delivery score replaces whatever the model might have said
(`evaluation._merge_llm_verdict`).

## Modules

```text
intelligence/
  rubric.py       competencies, score dimensions and weights, bands
  phrasebook.py   all bilingual interview content (probes, coaching, headings)
  delivery.py     pace, filler, hedging, measurements — offline analytics
  evaluation.py   answer signals, gap detection, rubric scoring
  probing.py      probe decisions (which gap, how deep) and probe generation
  blueprint.py    competency/stage tagging, provider-authored question plans
  report.py       session aggregation and Markdown/HTML/JSON rendering
  pipeline.py     one call per turn, one call per report (what the UI uses)
  llm/
    base.py              LLMRequest/LLMReply, JSON extraction, normalization
    registry.py          provider selection + fallback chain
    ollama_provider.py   local daemon over HTTP
    anthropic_provider.py Claude via the official SDK (optional dependency)
```

## The rubric

Six dimensions, weighted, blended into one 0-100 score
(`rubric.weighted_overall`): structure (0.20), evidence (0.22), impact (0.20),
reasoning (0.18), relevance (0.12), delivery (0.08). Only the dimensions
actually present are counted, so a pass that cannot judge reasoning does not
silently score it as zero.

Bands: 85+ outstanding, 70-84 strong, 55-69 solid, 40-54 developing, below 40
insufficient. The band decides the colour everywhere — dial, meter, radar, HTML
report — through `ui/theme/tokens.band_color`.

Eight competencies (ownership, problem solving, communication, collaboration,
learning agility, role fit, technical depth, values) are weighted per interview
type: `rubric.INTERVIEW_TYPE_COMPETENCIES` decides which ones the report counts
for more, so a technical interview is not scored on HR competencies.

## Gaps drive the interview

`evaluation.detect_gaps` looks for ten specific omissions, and
`phrasebook.GAP_PRIORITY` orders them by what is worth asking about first —
missing context beats a missing metric, because a metric without a situation
cannot be interpreted. The first applicable gap becomes the probe
(`probing.decide_probe`), bounded by `max_probe_depth` so the interview cannot
circle one story forever. An answer at 80+ with no gaps ends the thread.

## Adding a provider

1. Implement `LLMProvider` (`name`, `model`, `is_available()`, `complete()`).
   Raise `LLMUnavailable` for "cannot run" and `LLMFailure` for "ran and
   failed"; the chain treats them differently.
2. Add it to `registry.build_chain`, after the local options if it uses the
   network.
3. Add the config name to `config.SUPPORTED_AI_PROVIDERS` — the parity test in
   `tests/test_intelligence_providers.py` fails if the two lists drift.

Structured output is requested through `LLMRequest.schema`; a provider that
cannot constrain decoding should still return text, and `base.extract_json`
will recover the object from prose or code fences.

## Privacy boundary

Cloud analysis is off by default and cannot be enabled by editing
`config.json`: `AppConfig.normalize_ai_settings` drops a cloud provider that
has no matching `enable_cloud_ai` consent, and `registry.build_chain` refuses to
put one in the chain without it. The consent dialog states exactly what is sent
(question + transcript text; never audio). API keys live in
`%APPDATA%\AIInterview\credentials.json`, never in `config.json` — that file
ends up in support bundles.

## Testing

Provider behaviour is tested with fakes rather than live calls, including the
Claude request shape (`tests/test_intelligence_providers.py` asserts model,
`max_tokens`, adaptive thinking, `output_config.effort`, the JSON schema, and
the refusal-fallback retry path against a stub SDK). Offline scoring is
asserted to be deterministic, which is what makes the rule engine a usable
default rather than a placeholder.
