# Frozen question review

Use the unchanged 80 inputs, 75 original question groups and 99 previously locked atomic
facts. Retain all cases, including failed executions and empty outputs. Holdout is excluded.
The reference is assistant-decomposed and assistant-reviewed, not independent human gold.

Score the actual structured staff question list. Do not award question credit for facts only
in the prose draft, model explanation or customer history. Customer enquiry and history may
resolve the subject of a question; they do not turn an unasked fact into an asked fact.

For every case, preserve hashes of the exact predicted question list and gold question list.
Return 1-based `whole: [[prediction, gold]]` and `facts: [[prediction, gold, fact]]` indices.

- A whole match asks the same central decision and covers every required gold fact. Whole
  matches must be one-to-one. An additional independent decision within a question prevents
  a whole match; partial requested facts can still count. Redaction instructions are not an
  independent decision, and extra alternatives within one decision are not a separate fact.
- Match meaning rather than literal wording or internal field identifiers. Preserve relevant
  provider, product, quantity, period and scope qualifiers.
- Typical and maximum counts are distinct. Matrix operations differ from elements or pairs.
  Request rate differs from concurrent requests. Traffic conditions differ from departure timing.
- A complete failing request may cover endpoint and sent parameter facts requested in that
  reproduction context. It does not implicitly request a response, aggregate rate, contract
  status, deployment history or independent customer requirements.
- Keep references unchanged when a question repeats a supplied fact or conflicts with a
  proceed instruction. Record that concern separately; do not silently relabel or exclude it.
- Empty gold or empty predictions permit zero matches without subjective judgement.
  Reuse an earlier semantic decision only for identical text and unchanged enquiry/history
  and reference, with exact index remapping if unique question order changes.

Use the production `score_bound_review` scorer after reviews are bound to the full prediction
and reference hashes. Report micro question F1, precision, recall, covered facts out of 99,
and questions produced on the 40 empty-gold cases. Schema and execution outcomes are separate.

The most recent comparable historical result is `frozen-qualification`: 8 whole matches,
46 predicted questions, 75 gold questions, F1 13.2231%, and fact coverage 18/99 (18.1818%).
The earlier `frozen-locked` result had F1 0 and fact coverage 4/99.

New runs use fresh endpoint calls. Treat score differences as observed historical comparisons,
not isolated causal estimates. If semantic policy is changed, re-review both sets under one
policy and identify that comparison separately. This run does not authorize implementation
changes, reference changes or frozen-data tuning.
