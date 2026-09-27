# NDATrace Frontend

Next.js + React + TypeScript client for the NDATrace NDA requirement review system. Talks to the
FastAPI backend (`../backend/`, see `../docs/api.md` for the full endpoint reference) — this app
has no server-side logic of its own beyond Next.js routing.

## What it does

- Submit an NDA (paste text or upload a PDF, extracted server-side via `POST /extract-pdf`) and a
  confidentiality requirement (free text, with the 17 standard ContractNLI requirements offered as
  suggested starting text).
- Display the result: label (Entailment/Contradiction/NotMentioned), cited evidence,
  `source_valid`/`needs_human_review` state — no fabricated confidence score.
- Browse the reconstruction-v2 final TEST comparison (`/experiments`).

There is no review-history feature — `POST /api/review` doesn't persist results, and the backend
has no database.

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
| `app/page.tsx` | Main review screen — NDA/requirement input (with a sample NDA for demo use) submitted to `POST /api/review`, the sole review endpoint |
| `app/experiments/page.tsx` | Reconstruction-v2 final TEST comparison (`GET /experiments`, reads `results/final/reconstruction_v2/`) |
| `components/ResultCard.tsx` | One `POST /api/review` result: label, evidence, `needs_human_review`/`source_valid` state — no fabricated confidence score |
| `components/LimitationsPanel.tsx` | Collapsible panel stating the system's known limitations (reviewer aid only, human final authority, NotMentioned/injection caveats) |
| `components/NavBar.tsx` | Top navigation (Review / Experiments) |
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
