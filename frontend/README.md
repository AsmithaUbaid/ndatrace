# NDATrace Frontend

Next.js + React + TypeScript client for the NDATrace NDA requirement review system. Talks to the
FastAPI backend (`../backend/`, see `../docs/api.md` for the full endpoint reference) — this app
has no server-side logic of its own beyond Next.js routing.

## What it does

- **`/` — frozen RAG batch review (`POST /review`).** Submit an NDA
  (paste text or upload a PDF) and pick which of the 17 standard confidentiality requirements to
  check (checkbox multi-select, all selected by default). Results show the verdict, explanation,
  exact evidence, and source-clause provenance; results are saved to SQLite.
- **`/history`** — browse past batch reviews (`GET /results`, `GET /review/{id}`).
- **`/experiments`** — the final TEST comparison (`GET /experiments`, reads
  `results/final/v2/`).

`/` and the single-requirement backend endpoint use the same frozen top-5 RAG classifier path.
The UI uses the batch adapter so one document index can serve multiple selected requirements.

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
| `app/page.tsx` | Batch review screen — NDA input, checkbox picker for the 17 requirements, submits to frozen-RAG `POST /review` |
| `app/history/page.tsx` | Past batch reviews (`GET /results`, `GET /review/{id}`) |
| `app/experiments/page.tsx` | Final TEST comparison (`GET /experiments`, reads `results/final/v2/`) |
| `components/RequirementCard.tsx` | One result: verdict, explanation, source-validated evidence, and subtle retrieval provenance |
| `components/ResultsSummaryBar.tsx`, `components/FilterTabs.tsx` | Batch-review result filtering by verdict/needs-attention |
| `components/Checkbox.tsx` | Custom-styled checkbox for the requirement picker |
| `components/LimitationsPanel.tsx` | Collapsible panel stating the system's known limitations (reviewer aid only, human final authority, NotMentioned/injection caveats) |
| `components/NavBar.tsx` | Top navigation (Review / History / Experiments) |
| `lib/api.ts` | Fetch wrappers + TypeScript types for every backend endpoint in `../docs/api.md` |
| `lib/verdict.ts` | Label → normalized verdict (color/icon/filter-key) mapping and review-attention helpers |
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
