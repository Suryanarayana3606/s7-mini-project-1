# Novelty Features Added

Four features layered onto the existing pipeline. Nothing about the
existing upload → preprocessing → aspect discovery → sentiment → root
cause → recommendation → report flow was removed or restructured —
these are additive.

## 1. Recommendation Feedback Loop (reviewer Accept/Reject/Implement)

**Why:** Your project is titled a *"management system,"* but until now
recommendations were generate-and-display only — no management
actually happened to them. This closes that loop.

**Backend**
- `services/recommendation_service.py` — every recommendation now gets
  a stable `rec_id` (uuid) and starts at `status: "Pending"`.
- `database/db.py` — `update_recommendation_status()`,
  `get_recommendation_feedback_stats()` (acceptance rate overall + per
  department).
- `routers/recommendation_router.py` — `PATCH
  /api/recommendations/{rec_id}/status`, `GET
  /api/recommendations/feedback-stats`. Both `/run` and `/results` now
  return `feedback_stats` alongside the existing payload.

**Frontend**
- `RecommendationPage.tsx` — Accept / Reject / Implement / Pending
  buttons on every recommendation card, plus a "Reviewer Feedback"
  summary panel (accepted/rejected counts, acceptance rate, per-department
  breakdown).

**For your report:** this gives you an actual metric —
*"X% of AI-generated recommendations were accepted by reviewers,
broken down by department"* — instead of just describing what the
system outputs.

## 2. Severity-Weighted Root Cause Scoring

**Why:** The original TF-IDF ranking treated every negative review
identically, whether the sentiment model was 51% or 99% confident it
was negative. A root cause repeated across low-confidence borderline
reviews ranked the same as one repeated across reviews the model was
certain about.

**Backend** — `services/rootcause_service.py`
- New `weighted_phrase_frequency()`: each phrase occurrence is weighted
  by a 0.5–1.5 multiplier derived from that review's ABSA sentiment
  confidence, instead of counted as a flat +1.
- `score_keywords()` now accepts confidences and uses the weighted
  count when available (falls back to the original unweighted
  behavior automatically for datasets without a `Confidence` column —
  fully backward compatible).
- `analyze_dataset()` now also emits an `Avg Severity` figure per
  aspect (mean ABSA confidence across that aspect's negative reviews).

Verified in isolation (see terminal transcript) — severity weighting
changes phrase ranking scores as intended, and gracefully degrades to
the original scoring when no confidence data is present.

## 3. Explainability / Evidence Panel

**Why:** Recommendations were previously a black box — no way to see
*which* customer reviews actually drove a given recommendation.

**Backend**
- `rootcause_service.py` — `_build_evidence()` picks, for each of the
  top root-cause phrases, the real customer review that best
  demonstrates it (preferring the highest-confidence match). Stored as
  an `Evidence` column (list of `{phrase, review, confidence}`) on the
  `root_cause` table.
- `recommendation_service.py` — when a recommendation is generated for
  an aspect, its evidence is attached directly (`evidence` field),
  carried through to the `recommendations` table and API response.
  This is *deterministic* traceability (not LLM-generated), so there's
  no hallucination risk — every citation is a real row from the
  dataset.

**Frontend** — `RecommendationPage.tsx`
- "Why this recommendation?" toggle on each card, expanding to show
  the source phrases with the actual customer quotes and the
  sentiment model's confidence for each.

## 4. Multi-Language Support

**Why:** Every model in the pipeline (BERTopic embeddings, the DeBERTa
ABSA sentiment model, TF-IDF root cause extraction) is English-only.
Non-English reviews would previously be silently mis-analyzed.

**Backend**
- New `services/language_service.py` — `langdetect` for per-review
  language ID, `deep-translator` (Google Translate) for translating
  non-English reviews to English. Both are optional at import time; if
  either isn't installed or has no network access, the system degrades
  to "leave text as-is" rather than crashing the upload.
- `routers/dataset_router.py` — on `/api/dataset/confirm`, every review
  is now language-detected; non-English reviews get a translated
  working copy. `review_original` preserves exactly what the customer
  wrote; `review` (what the rest of the pipeline reads) becomes the
  English text. Response now includes a `language_support` block:
  per-language counts, how many were translated, and whether the
  translator was reachable.
- `config.py` / `database/db.py` / `routers/settings_router.py` — new
  `auto_translate` setting (default `True`), toggleable from Settings,
  so this can be switched off in an offline/air-gapped grading
  environment.

**Frontend** — `UploadPage.tsx` shows a "🌐 Multi-Language Detection"
panel after a successful upload when any non-English reviews are
found: language breakdown, translated count, and a visible warning if
the translator had no network access.

**Note on this repo's own sandbox:** translation was tested here and
correctly *detected* Spanish/Japanese text, but the translation call
itself failed because this environment has no outbound access to
Google's endpoint — exactly the "no network" fallback path described
above, and it degraded gracefully (kept original text, marked
`translation_failed`) instead of crashing. In your real dev/deployment
environment with normal internet access, translation will succeed.

---

## Setup

```bash
pip install -r requirements.txt   # now includes langdetect, deep-translator
```

No database migration needed — `recommendations` and `root_cause` are
recreated (`if_exists="replace"`) the next time you run Root Cause
Analysis and Generate Recommendations, which will pick up the new
columns automatically. Settings default `auto_translate=True` the
first time `get_settings()` is called if it isn't already set.

## What I verified before delivering

- `python -m py_compile` on every changed backend file (no syntax
  errors).
- Ran `RootCauseService.analyze_aspect()` standalone with a small
  review set + mixed confidences — confirmed severity weighting shifts
  scores and evidence extraction picks the correct highest-confidence
  matching review per phrase.
- Ran `db.py`'s new functions against a temp SQLite file — save/load of
  `evidence` (JSON round-trip), `update_recommendation_status`, and
  `get_recommendation_feedback_stats` all behave correctly.
- Ran `language_service.py` standalone — detection works offline;
  translation correctly falls back on network failure.
- `tsc --noEmit` on the whole frontend — zero type errors.

I could not run the full FastAPI app or a Vite production build
end-to-end in this sandbox (no `torch`/`bertopic`/GPU stack installed,
and the sandbox's `vite build` is missing a platform-specific native
binary unrelated to this change). Please do a full local run before
your final submission/demo.
