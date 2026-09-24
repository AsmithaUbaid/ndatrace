# NDATrace Frontend

Next.js + React + TypeScript client for the NDATrace NDA requirement review system. Talks to the
FastAPI backend (`../backend/`, see `../docs/api.md` for the full endpoint reference) — this app
has no server-side logic of its own beyond Next.js routing.

## What it does

- Submit an NDA (paste text or upload a PDF, extracted server-side via `POST /extract-pdf`) and
  select which of the 17 standard confidentiality requirements to check.
- Display results per requirement: label (Entailment/Contradiction/NotMentioned), confidence,
  cited evidence, whether the selective agent was escalated, and per-case cost/latency.
- Browse past reviews (`/history`) and offline experiment results (`/experiments`).
- Export/copy a review's results as text or JSON.

## Local development

Requires the backend running separately first (see the root `README.md`):

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The dev server proxies API calls to
`http://localhost:8000` by default (see Environment variables below).

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Base URL of the FastAPI backend (`lib/api.ts`) |

No `.env.local` is required for local development against a locally-running backend on the default
port; set `NEXT_PUBLIC_API_URL` only to point at a different backend host/port.

## Main screens / components

| Path | Purpose |
|---|---|
| `app/page.tsx` | Main review screen — NDA input, requirement selection, results display |
| `app/history/page.tsx` | Past live reviews (`GET /results`) |
| `app/experiments/page.tsx` | Offline experiment browser (`GET /experiments`) |
| `components/RequirementCard.tsx` | One requirement's result: label, evidence, confidence, agent/cost details |
| `components/ResultsSummaryBar.tsx` | Headline + clickable Entailment/Contradiction/NotMentioned count chips |
| `components/FilterTabs.tsx` | Filter results by label or "needs attention" (low confidence / agent-escalated) |
| `components/ConfidenceBar.tsx` | Visual confidence indicator |
| `components/LabelBadge.tsx` | Colored label chip |
| `components/Checkbox.tsx` | Custom-styled checkbox (requirement selection) |
| `components/NavBar.tsx` | Top navigation |
| `lib/api.ts` | Fetch wrappers for every backend endpoint in `../docs/api.md` |
| `lib/verdict.ts` | Label → color/icon/filter-key mapping shared across components |
| `lib/export.ts` | Copy-to-clipboard / download-as-text/JSON for a completed review |

## Build / production commands

```bash
npm run build
npm start
```

`npm run lint` runs Next.js's default ESLint config.

## Known limitations

- No authentication — this is a local academic-project demo, not a deployed multi-user product
  (see the root README's "Do Not Build" list: no SSO/RBAC/multi-tenancy is in scope).
- CORS on the backend is currently permissive (`allow_origins=["*"]`) for local development
  convenience — see `docs/architecture.md`.
