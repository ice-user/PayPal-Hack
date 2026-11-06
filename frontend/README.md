# Precedent Frontend (Person A)

React + TypeScript + Vite frontend for the PayPal Hackathon dashboard.

## Features

- **Three-column layout** matching the UI spec:
  - **Situation** — dispute rate, trend, reason mix, concentration, narrative
  - **Precedents** — top-k cases with similarity, matched_on/differs_on, provenance badges, evidence quality
  - **Plan** — typed action, approval tier (AUTO/NEEDS_APPROVAL/BLOCKED), confidence, playbook notes, approve/reject buttons
- **Timeline** — detected → recommended → approved → executed → measured (simulated labels)
- **Scenario switcher** — one_carrier_delays / many_carriers_delays / delivered_orders
- **With/without-precedent toggle** — shows recommendation difference
- **Abstain state** — displays when system abstains
- **All simulated elements labelled** — per hackathon requirements

## Development

```bash
cd frontend
npm install
npm run dev
```

Runs on `http://localhost:5173` with API proxy to `http://127.0.0.1:8765` (Person B backend).

## Build

```bash
npm run build
```

## Project Structure

```
frontend/
├── index.html
├── package.json
├── tsconfig.json
├── tsconfig.node.json
├── vite.config.ts
├── src/
│   ├── main.tsx          # Entry point
│   ├── App.tsx           # Main app component
│   ├── App.css           # Styles (CSS variables for theming)
│   ├── types/
│   │   └── api.ts        # TypeScript types matching contracts/
│   ├── api/
│   │   └── client.ts     # Axios API client
│   └── components/
│       ├── SituationPanel.tsx
│       ├── PrecedentsPanel.tsx
│       ├── PlanPanel.tsx
│       ├── TimelinePanel.tsx
│       ├── ScenarioSwitcher.tsx
│       ├── AbstainBanner.tsx
│       ├── LoadingState.tsx
│       └── ErrorState.tsx
```

## Contract Alignment

All TypeScript types in `src/types/api.ts` mirror:
- `contracts/SituationRecord.schema.json`
- `contracts/Recommendation.schema.json`

Fixtures in `contracts/fixtures/` are used by the backend to seed demo scenarios.

## API Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `GET /api/merchants/{id}/situation` | Current situation |
| `GET /api/situations/{id}/recommendation` | Consultant recommendation |
| `POST /api/actions/{id}/approve` | Human approval |
| `POST /api/actions/{id}/reject` | Human rejection |
| `GET /api/merchants/{id}/timeline` | Event timeline |
| `POST /api/sim/advance` | Advance simulated clock |
| `POST /api/merchants/{id}/scenario` | Load demo scenario |

## Theming

Uses CSS variables matching the Hermes desktop app theme:
- `var(--foreground)`, `var(--muted-foreground)`
- `var(--primary)`, `var(--success)`, `var(--warning)`, `var(--destructive)`
- `var(--background)`, `var(--card)`, `var(--border)`