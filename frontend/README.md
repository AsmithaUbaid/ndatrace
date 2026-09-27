# NDATrace Frontend

Next.js + React + TypeScript client for the NDATrace NDA requirement review system. Talks to the
FastAPI backend (`../backend/`, see `../docs/api.md` for the full endpoint reference) — this app
has no server-side logic of its own beyond Next.js routing.

## What it does

Two review flows, plus history and the experiment comparison:

- **`/` — batch review (legacy RAG + selective-agent pipeline, `POST /review`).** Submit an NDA
  (paste text or upload a PDF) and pick which of the 17 standard confidentiality requirements to
  check (checkbox multi-select, all selected by default). Results show label, self-reported
  confidence, agent-escalation status, and evidence per requirement; results are saved to SQLite.
- **`/final` — single-requirement review (final architecture, `POST /api/review`).** Submit an NDA
  and one free-text requirement. Results show label, cited evidence, and
  `source_valid`/`needs_human_review` state — no fabricated confidence score, no persistence.
- **`/history`** — browse past batch reviews (`GET /results`, `GET /review/{id}`).
- **`/experiments`** — the reconstruction-v2 final TEST comparison (`GET /experiments`, reads
  `results/final/reconstruction_v2/`).

`/` is the legacy, restored batch-review flow, not the selected final architecture — `/final` is.
Both are real, working flows; see `docs/architecture.md` for which one is scientifically final.

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
| `app/page.tsx` | Batch review screen — NDA input, checkbox picker for the 17 requirements, submits to legacy `POST /review` |
| `app/final/page.tsx` | Single-requirement review screen — NDA + free-text requirement, submits to `POST /api/review` (the final architecture) |
| `app/history/page.tsx` | Past batch reviews (`GET /results`, `GET /review/{id}`) |
| `app/experiments/page.tsx` | Reconstruction-v2 final TEST comparison (`GET /experiments`, reads `results/final/reconstruction_v2/`) |
| `components/RequirementCard.tsx` | One legacy batch-review result: label, confidence, agent-escalation status, evidence |
| `components/ResultsSummaryBar.tsx`, `components/FilterTabs.tsx` | Batch-review result filtering by verdict/needs-attention |
| `components/Checkbox.tsx` | Custom-styled checkbox for the requirement picker |
| `components/ResultCard.tsx` | One `POST /api/review` result: label, evidence, `needs_human_review`/`source_valid` state — no fabricated confidence score |
| `components/LimitationsPanel.tsx` | Collapsible panel stating the system's known limitations (reviewer aid only, human final authority, NotMentioned/injection caveats) |
| `components/NavBar.tsx` | Top navigation (Review / History / Final / Experiments) |
| `lib/api.ts` | Fetch wrappers + TypeScript types for every backend endpoint in `../docs/api.md` |
| `lib/verdict.ts` | Label → normalized verdict (color/icon/filter-key) mapping, plus legacy confidence/attention helpers, shared across components |
| `lib/export.ts` | Copy-to-clipboard / download-as-text/JSON for a completed batch review |

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
