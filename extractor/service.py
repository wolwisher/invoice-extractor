"""PDF -> text -> LLM -> validated JSON, plus an optional webhook with the result."""
import json
import logging
import urllib.request

from pydantic import ValidationError

from .pdf_text import extract_text
from .schema import REQUIRED, ExtractionResult, Invoice

log = logging.getLogger(__name__)
TOLERANCE = 0.01


def _drop_invalid_fields(raw: dict, warnings: list) -> dict:
    """Validate field by field so one bad value doesn't throw away the whole document."""
    clean = {}
    for name in Invoice.model_fields:
        if name not in raw or raw[name] is None:
            continue
        try:
            Invoice.model_validate({name: raw[name]})
            clean[name] = raw[name]
        except ValidationError as exc:
            warnings.append(f"Dropped {name}: {exc.errors()[0]['msg']}")
    return clean


def _cross_checks(inv: Invoice, warnings: list):
    if inv.subtotal is not None and inv.tax is not None and inv.total is not None:
        if abs(inv.subtotal + inv.tax - inv.total) > TOLERANCE:
            warnings.append(f"subtotal + tax ({inv.subtotal + inv.tax:.2f}) does not equal total ({inv.total:.2f})")
    for i, line in enumerate(inv.line_items, 1):
        if abs(line.quantity * line.unit_price - line.amount) > TOLERANCE:
            warnings.append(f"Line {i}: quantity x unit_price does not equal amount")


def process_document(pdf_bytes: bytes, llm) -> ExtractionResult:
    text = extract_text(pdf_bytes)
    raw = llm.extract(text, Invoice.model_json_schema())
    if not isinstance(raw, dict):
        raise ValueError("LLM did not return a JSON object")

    warnings: list[str] = []
    try:
        invoice = Invoice.model_validate(raw)
    except ValidationError:
        invoice = Invoice.model_validate(_drop_invalid_fields(raw, warnings))

    _cross_checks(invoice, warnings)
    missing = [f for f in REQUIRED if getattr(invoice, f) is None]
    status = "complete" if not missing and not warnings else "needs_review"
    return ExtractionResult(status=status, data=invoice, missing_fields=missing, warnings=warnings)


def send_webhook(url: str, result: ExtractionResult, timeout=10) -> bool:
    """POST the result as JSON. Returns False instead of raising so a slow webhook never loses the extraction."""
    req = urllib.request.Request(
        url, data=result.model_dump_json().encode(), headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 300
    except Exception as exc:  # network errors, timeouts, non-2xx
        log.warning("Webhook to %s failed: %s", url, exc)
        return False
