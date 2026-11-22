# Invoice Extractor

Turn PDF invoices into **validated, structured JSON** using an LLM, with a REST API, a simple upload page,
a webhook for automation, and tests that run without calling any paid API.

```
PDF ──> text (pypdf) ──> LLM (JSON mode) ──> Pydantic validation + math checks ──> JSON result ──> webhook
```

## Why it's built this way

- **No guessing.** The model is told to return `null` for anything not clearly written. Required fields that
  are missing are listed in `missing_fields` and the result is marked `needs_review`.
- **Code checks the AI.** Pydantic validates types, dates and currencies. If one field is bad (e.g. a date of
  "next tuesday"), only that field is dropped and the rest is kept. Totals are re-checked:
  `subtotal + tax = total` and `quantity x unit_price = amount` for every line.
- **Provider-agnostic.** The pipeline accepts any object with `extract(text, json_schema)`. An OpenAI client
  is included (standard library only); tests use a fake model so they are fast, free and repeatable.
- **Automation-ready.** Set `WEBHOOK_URL` and every result is POSTed there. A failing webhook never loses the result.

## Run it

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...        # optional: OPENAI_MODEL (default gpt-4o-mini), WEBHOOK_URL
python app.py                        # open http://localhost:8000
```

With Docker:

```bash
docker build -t invoice-extractor .
docker run -p 8000:8000 -e OPENAI_API_KEY=sk-... invoice-extractor
```

Tests (no API key needed):

```bash
python -m pytest -q    # 17 tests
```

## API

**`POST /api/extract`** (multipart form, field `file`): returns the job with its result.

```json
{
  "id": "3f6c…",
  "filename": "invoice.pdf",
  "status": "complete",
  "webhook_delivered": true,
  "result": {
    "status": "complete",
    "missing_fields": [],
    "warnings": [],
    "data": {
      "invoice_number": "INV-2026-0042",
      "invoice_date": "2026-11-02",
      "due_date": "2026-12-02",
      "vendor_name": "Northwind Packaging Ltd",
      "customer_name": "Green Valley Foods",
      "currency": "USD",
      "subtotal": 120.0, "tax": 21.6, "total": 141.6,
      "line_items": [{"description": "PET Bottle 500ml", "quantity": 1000, "unit_price": 0.12, "amount": 120.0}]
    }
  }
}
```

| Endpoint | Description |
| --- | --- |
| `POST /api/extract` | Upload a PDF, get structured data. `422` for unreadable files, `502` if the model call fails |
| `GET /api/jobs/<id>` | Status and result of a previous job |
| `GET /health` | Health check |
| `GET /` | Upload page |

## Project layout

```
extractor/
  pdf_text.py   # PDF -> text, rejects non-PDFs and scans without text
  schema.py     # Pydantic models and required fields
  llm.py        # OpenAI client (swap for Claude, Gemini or a local model)
  service.py    # pipeline, validation, cross-checks, webhook
app.py          # Flask API + upload page
tests/          # pytest suite with a fake LLM and a local webhook server
```

## Limits and next steps

- Scanned PDFs need OCR first (e.g. Tesseract) before extraction.
- Jobs are kept in memory; use Redis or Postgres and a task queue for production.
- To support another document type, add a new Pydantic model and required-field list.

## Tech

Python 3, Flask, Pydantic v2, pypdf, OpenAI API, pytest, Docker.
