# Precedent ablation: rating rubric (draft v0, agree before rating)

**Question:** does retrieving precedents make the Consultant's plan better and safer than
the same Consultant without retrieval?

**Systems:** A = no precedent (ablation baseline), B = with precedent. Same situations,
same action enum, same policy gate.

**Items:** 18 situations from `backend/precedent/scenarios.py` (synthetic order feeds with
a planted cause), 2 plans each = 36 items in `eval/results/score_sheet.csv`. Plans appear
as Plan 1 / Plan 2 in a random order. The key is in
`score_sheet_KEY_do_not_open_before_rating.json`. Do not open it until both raters finish.

## How to rate
Two raters (Person A and Person B) score every item **independently**, without talking.

**Pass 1 (blind):** read the situation and the column `plan_pass1_no_citations`. Score:

| Criterion | 0 | 1 | 2 |
|---|---|---|---|
| **Appropriate intervention** | Wrong cause or harmful (for example refunds to everyone for a carrier failure) | Partly right, or right cause but a weak or wasteful action | Addresses the cause the situation's signals point to, at sensible cost |
| **Abstained when it should** (Y / N / NA) | Y: abstained, and that was right; N: acted when it should have abstained, or abstained when the signals were clear; NA: not applicable | | |

**Pass 2 (citations visible):** read `plan_pass2_with_citations`. Score:

| Criterion | 0 | 1 | 2 |
|---|---|---|---|
| **Grounded in cited evidence** | No citations, or citations do not support the action | Citations relevant but thin or only partly matching | Each action is backed by clearly similar cases, with differences acknowledged |
| **Unsupported claims** (count) | Number of statements that are not backed by the situation data or a cited case (for example a numeric effect with no measured case) | | |

Pass 2 cannot be blind: plans with citations are obviously System B. That is why the
intervention criterion is scored in pass 1.

## Reporting
- Mean score per criterion per system, with the per-item differences (B minus A).
- Inter-rater agreement: Cohen's weighted kappa on the 0 to 2 criteria; percent agreement
  on Y/N/NA. Discuss and record disagreements; do not overwrite scores.
- Report the case-library mix used (authored vs public vs measured) next to the scores.

## Known limits (state them in the write-up)
- The situations are synthetic and the same team wrote the scenarios and the authored cases,
  so System B's advantage partly reflects internal consistency. The held-out-family check in
  `eval/results/summary.md` is the more honest signal of robustness.
- System A is a rules baseline, not an LLM. An LLM-without-retrieval baseline is a follow-up.
- No measured cases exist yet, so no numeric effect is evaluated.
