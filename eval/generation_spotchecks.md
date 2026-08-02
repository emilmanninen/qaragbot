# Generation-layer spot-checks (manual, not part of eval_set.json)

These test known limitations #1 and #4 from `qabotproject.md`'s "Known
limitations found via testing" section. Neither can be scored by the
Recall@k harness (`run_eval.py`), because in both cases **retrieval
already succeeds** -- the correct chunk is pulled back correctly. The bug
lives entirely in what the LLM does with that chunk afterward, which
`run_eval.py` never sees (it doesn't call the LLM at all, per the Step 9
design). Including these in `eval_set.json` would score them as a "pass"
and mask the actual bug behind a green checkmark.

Run these manually via curl against `/query`, once per question, and
inspect the actual model output by eye -- same method already used to
verify the MVP end-to-end.

Limitations #3 (condenser ambiguity resolution) and #7 (offset drift) are
not included here: #3 is already covered by the existing
`test_condenser.py` adversarial cases, and #7 is documented as
metadata-only with no behavioral impact, so there's nothing left to
regress-test.

---

## Check 1 -- Parameterized table lookup (limitation #1)

**Doc:** `tulojen_vaikutus_korkeakoulussa.md`
**Question (FI):** "Paljonko saa ansaita opintotuen aikana?"

Deliberately omits the support-month count the income-limit table is
keyed by -- mirrors the original finding exactly.

**What to check:** does the model decline to answer entirely, even though
the correctly-retrieved chunk contains the full table? A better behavior
would be a conditional answer or a clarifying question. Prior finding was
an outright decline despite complete, correctly-retrieved context.

**Pass/fail is a judgment call, not a boolean** -- record what actually
happened (decline / hedge / clarify / answer with an assumed month count)
rather than just pass/fail, since the point is characterizing the
behavior, not a binary check.

---

## Check 2 -- Language-dependent refusal confidence (limitation #4)

**Doc:** ambiguous multi-turn follow-up (same one that originally
surfaced this finding -- reuse the exact condenser test case, not a new
question, so this is a true regression check against the original
observation)

**Question (FI):** "Entä vanhemmille?"
(follow-up to an earlier turn asking about the student's own income limit
 -- see test_condenser.py case 5 for the exact preceding history array)
**Question (EN):** "What about for parents?"

**What to check:** run the same underlying ambiguous question in both
languages, same corpus, and compare the *tone* of the two outputs --
specifically whether one hedges with a partial answer while the other
gives an explicit "not found" refusal, despite both citing the same
underlying retrieved chunks. Original finding: hedged in English,
explicit refusal in Finnish.

**Record:** the full text of both outputs side by side, plus which
citations each used -- if the citations differ between languages, that's
a separate and more serious bug than a tone difference alone.

---

## How to use this file going forward

Re-run both checks any time `generator.py`'s prompt changes, the LLM
provider or model changes, or after any fix attempt at either limitation.
This file's job is to make sure #1 and #4 don't get silently forgotten
once Step 9's automated Recall@k numbers become the main thing everyone's
looking at.
