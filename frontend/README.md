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


## Live workflow

The UI now calls the FastAPI service for document processing, compliance evaluation and PDF report generation. Set `VITE_API_BASE_URL` for the backend URL.

Evidence returned with page numbers and normalized bounding boxes is rendered as highlights and clickable audit pins. Selecting an evidence item navigates to its source page.

The control score is calculated from the current rule findings (PASS = 100% contribution, REVIEW = 50%, FAIL = 0%) and is therefore a UI summary metric, not a statutory audit opinion.


## PDF evidence overlay

PDF documents are rendered with PDF.js. Document AI normalized coordinates are overlaid on the rendered page so findings can display true source highlights and clickable audit pins. Evidence coordinates are expected as normalized `x/y/width/height` values in the 0–1 range.
