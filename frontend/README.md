# Satya-Lekha web app

React + Vite + TypeScript + Tailwind CSS + Ant Design, with PDF.js for rendering. It talks to the FastAPI backend
described in the [main README](../README.md).

## Run

Start the backend first (`uvicorn app.main:app --reload` from the repository root), then:

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

Node 20.19+ or 22.12+ is required (a Vite requirement).

| Command | Purpose |
|---|---|
| `npm run dev` | dev server with hot reload |
| `npx tsc -b` | type check |
| `npm run build` | type check and production build into `dist/` |

## Where it finds the API

`VITE_API_BASE_URL` sets the backend URL at **build time**. Give the host only, with no `/api` on the end: every
request path the app uses already starts with `/api/v1`, so a base ending in `/api` would send requests to
`/api/api/v1/...`, which do not exist.

| Setup | Value |
|---|---|
| `npm run dev` (default) | `http://localhost:8000` |
| Served by the API itself, as in the Docker image | `/` (the same origin), set by the `Dockerfile` |
| UI and API on different hosts | the API's public URL |

In development the browser calls the API directly from `localhost:5173`, so that origin must be allowed by the
backend. It is by default; `CORS_ORIGINS` in the backend's `.env` changes the list. A Docker deployment serves
the UI from the same origin and needs no CORS setting. Rebuild after changing `VITE_API_BASE_URL`.

## What it does

- **Upload** a PDF. Before the first upload the page shows a placeholder statement, not real data.
- **Preview** the document with PDF.js. Selecting a finding highlights its evidence on the page and shows numbered
  audit pins; clicking evidence jumps to its page. Highlights need bounding boxes, which the local extractor and
  Document AI's OCR processors provide and Layout Parser does not.
- **Findings** are listed with their status, severity, confidence, evidence and regulatory evidence, and can be
  filtered by severity.
- **Cross-document checks.** Documents uploaded in a session are remembered (until the page is reloaded). From the
  second upload the app also calls `POST /api/v1/compliance/cross-check` and appends those findings (`XDOC-…`) to
  the document's own. Their evidence is labelled with the file it came from; clicking evidence from another file
  selects the finding but does not move the page.
- **Print report** and **Export PDF report** both use `POST /api/v1/compliance/report`, so they produce the same
  PDF. Print sends that PDF to the printer from a hidden frame (or opens it in a new tab if the browser will not
  print an embedded PDF).
- **Control score:** `PASS` counts 100%, `REVIEW` 50%, `FAIL` 0%, averaged over the findings. It is a summary for
  the screen, not an audit opinion.

## Layout

```
src/App.tsx      the screen: upload, preview, findings, session memory
src/api.ts       calls to the backend
src/types.ts     shared types
src/styles.css   styles
```

The Docker image builds this app and serves it from the API. `Dockerfile` and `nginx.conf` in this directory are
an alternative for serving the UI from its own Nginx container; they are not used by the default deployment.
