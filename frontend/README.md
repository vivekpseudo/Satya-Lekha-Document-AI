# Satya-Lekha Frontend

Vite + React + TypeScript + Tailwind CSS + Ant Design frontend for the Satya-Lekha compliance platform.

## Run

```bash
cd frontend
npm install
npm run dev
```

Build:

```bash
npm run build
```

## UX direction

The UI is based on the supplied audit/verification references, adapted for Satya-Lekha:

- left-side source financial statement / PDF preview
- right-side compliance and verification panel
- PASS / FAIL / REVIEW findings
- regulatory evidence
- financial variance cards
- audit pins
- document upload
- compliance run
- PDF report export
- responsive mobile layout

The current screen uses representative fixture data. Connect the existing FastAPI endpoints to replace the fixture state with live Document AI and compliance results.

## Planned API integration

- `POST /api/v1/documents/process`
- `POST /api/v1/documents/process-and-store`
- `POST /api/v1/compliance/evaluate`
- `POST /api/v1/compliance/report`
- `POST /api/v1/regulations/search`
