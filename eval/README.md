# Evaluation

| File | What |
|---|---|
| `run_ablation.py` | Runs the 18 ablation scenarios through System A (no precedent) and System B (with precedent), the reference gate, a held-out-family check and Recall@3 |
| `RUBRIC.md` | Human rating rubric (primary result) |
| `results/summary.md` | Automatic sanity checks (regenerated each run) |
| `results/score_sheet.csv` | Blind sheet for two raters |
| `results/score_sheet_KEY_...json` | Which plan is which system. Open only after rating |
| `results/ablation_runs.json` | Full outputs for every run |

Run: `python eval/run_ablation.py`

## Run log (keep every run; do not overwrite history)

**Run 1, library v0 (28 cases), 2026-11-07.**
- Right family when acting is right: A 0/13, B 10/13.
- Abstained correctly: A 17/18, B 14/18.
- Unsafe acts: A 0/18, B 1/18.
- Held-out family: B abstained 13/13.
- Misses: both fraud scenarios and the not-as-described scenario abstained.
- Cause: two authored cases stored zeros for delivery fields that do not apply to digital
  goods, and the library had only two physical-goods fraud cases.

**Changes between runs (made after seeing run 1):**
- Removed the inapplicable zero features from cases d01 and d03.
- Added a not-as-described share feature.
- Added three authored cases (d04, d05, e03).

These changes were made after looking at the evaluation set, so run 2 is optimistic.

**Run 2, library v1 (31 cases).**
- Right family when acting is right: A 0/13, B 12/13.
- Abstained correctly: A 17/18, B 16/18.
- Unsafe acts: A 0/18, B 1/18.
- Retriever Recall@3: 15/15.
- Held-out family: B abstained 12/13; the one non-abstention picked fraud with prepare-only
  actions, so 0/13 unsafe.

**Run 3: held-out TEST set, library v1 frozen, run once (2026-11-08). This is the headline
result.**
- The 18 TEST scenarios (`scenarios.TEST`: new seeds, volumes, intensities and targets) were
  committed before the run (commit `060db7c`). Results: `results/test/summary.md`.
- Detector agrees with ground truth on 18/18.
- Right family when acting is right: A 0/13, B **9/13**.
- Abstained correctly: A 17/18, B 13/18.
- Unsafe acts: A 0/18, B 1/18 (the mixed-cause scenario again).
- Recall@3: 15/15.
- Held-out family: B abstained 13/13, 0 unsafe.
- B's four misses where acting was right are all abstentions below the 0.5 confidence floor:
  T06 (110h backlog, 0.49), T13 (not-as-described, 0.47), T12 (not-as-described, 0.39) and
  T11 (mild fraud, 0.38). All four fail safe: no action is proposed.
- The gap from run 2 (12/13) to run 3 (9/13) is the overfitting we expected from tuning on
  the dev set. The weak spots are the thin parts of the library: not-as-described and fraud.

**Known failures in run 2:**
- S13 (not-as-described on one SKU): abstained at confidence 0.47, just under the 0.5 floor.
  Safe, but a miss.
- S14 (carrier and fulfilment causes at once): read as fulfilment only, at confidence 0.68.
  This is the one unsafe act. The detector has no notion of two simultaneous causes. Fixing
  it needs a mixed-cause signal, not more tuning on this set.
