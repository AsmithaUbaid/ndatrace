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
| `app/page.tsx` | Main review screen — NDA/requirement input (with a sample NDA for demo use) submitted to `POST /api/review`, the final architecture |
| `app/history/page.tsx` | Past legacy reviews (`GET /results`, `GET /review/{id}`) — the legacy RAG+agent pipeline's saved history, not `/api/review` |
| `app/experiments/page.tsx` | Offline experiment browser (`GET /experiments`) |
| `components/ResultCard.tsx` | One `POST /api/review` result: label, evidence, `needs_human_review`/`source_valid` state — no fabricated confidence score |
| `components/RequirementCard.tsx` | One legacy per-hypothesis result (label, evidence, confidence, agent/cost details) — used by the `/history` view |
| `components/LimitationsPanel.tsx` | Collapsible panel stating the system's known limitations (reviewer aid only, human final authority, NotMentioned/injection caveats) |
| `components/NavBar.tsx` | Top navigation (Review / History / Experiments) |
| `lib/api.ts` | Fetch wrappers + TypeScript types for every backend endpoint in `../docs/api.md` |
| `lib/verdict.ts` | Label → normalized verdict (color/icon/filter-key) mapping shared across components |

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
