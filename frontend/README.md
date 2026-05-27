# Frontend — Loan Officer Dashboard

SvelteKit UI for reviewing AI-generated SME loan risk summaries.

## Bootstrap

The folder is intentionally a placeholder until the dashboard work begins (Phase 5 in the proposal timeline). To initialise the SvelteKit project in place:

```bash
cd frontend
npm create svelte@latest .
# choose: Skeleton project, TypeScript, ESLint + Prettier
npm install
npm run dev -- --host
```

Until then, the frontend service in `docker-compose.yml` is commented out / will exit cleanly.

## Planned structure

```
src/
├── routes/
│   ├── login/
│   ├── applications/       # list + detail
│   └── applications/[id]/  # risk summary view, citations panel
├── lib/
│   ├── api/                # typed FastAPI client
│   └── components/
└── app.html
```
