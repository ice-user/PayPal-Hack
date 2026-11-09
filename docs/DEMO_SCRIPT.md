# Demo script (draft): under 3 minutes

**Setup before recording**
1. Make a fresh sandbox dispute (buyer pays the business 7.50 USD, goods and services,
   then reports "item not received"). Put its ID in `backend/.env` as
   `DEMO_DISPUTE_ID=PP-R-...` and restart the API.
2. Wait until the API shows "waiting for seller response" for it.
3. Start the API and `npm run dev:api`, then `POST /api/demo/reset`.
4. Browser at 1440 px wide. Hide bookmarks. Zoom 100%.
5. Have the PayPal sandbox Resolution Center (business account) open in a second tab.

**Rule for the voiceover:** say "observed" or "followed", never "caused". Say "simulated"
wherever the screen says it.

| Time | Screen | Voiceover (aim for about 2.6 words per second) |
|---|---|---|
| 0:00 to 0:15 | Title card, then dashboard on situation A | "Disputes cost PayPal merchants money and time. The usual tools tell you the rate went up. They do not tell you why, or what worked last time. MediateAI does." |
| 0:15 to 0:40 | Left column: rate, 4.4x, confidence interval, anomaly p-value, signals | "This store's dispute rate is four times its baseline, and the test says it is not noise. The signals say why: most disputes sit on one carrier, orders ship on time, and few disputed parcels show a delivery scan." |
| 0:40 to 1:05 | Middle column: precedents, hover matched/differs chips, badges | "MediateAI retrieves similar past cases and shows why each one matches and where it differs. Every case is labelled. These are authored playbook cases; the FTC cases in the library are public records. Nothing pretends to be measured when it is not." |
| 1:05 to 1:25 | Right column: diagnosis, actions, tier badges, "no numeric forecast" | "The plan cites its cases. Preparing a note runs automatically. Anything a buyer or PayPal would see needs my click. And because no precedent has measured numbers, it refuses to invent a forecast." |
| 1:25 to 1:50 | Click Approve on the evidence action; show live dispute status and the PayPal tab | "I approve. The backend re-checks the policy, re-reads the real sandbox dispute, and files the evidence through the PayPal Disputes API. Here it is in PayPal's Resolution Center." |
| 1:50 to 2:15 | Switch A, B, C quickly | "Same symptom, different causes. Spread across carriers with slow shipping, it fixes the backlog and messages buyers. Parcels marked delivered, it files proof of delivery." |
| 2:15 to 2:35 | Flip toggle to Without precedent | "Without precedents, the same system gives the same generic advice every time, refunds included. The policy gate blocks all of it, because nothing backs it up." |
| 2:35 to 2:50 | Back to A, Advance 14 days (simulated), outcome box | "Advancing a simulated clock records what followed, and saves it as a new case for review. Simulated, labelled, and never used for a forecast." |
| 2:50 to 2:58 | Ablation summary table | "On a held-out test set, precedent found the right cause 9 of 13 times; without it, none. Every miss was a refusal to act, not a wrong action. When its playbook was missing, it abstained." |

**Do not**
- Do not show numbers that are not on screen.
- Do not call simulated steps real, or authored cases real incidents.
- Do not claim the system learns or improves outcomes.

**Backup if PayPal is reviewing during recording:** the action shows "Simulated: PayPal
does not allow PROVIDE_EVIDENCE while the dispute is UNDER_PAYPAL_REVIEW". Say exactly
that. It demonstrates the safety check. Re-record the PayPal beat later.
