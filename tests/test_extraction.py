import copy

import pytest

from conftest import GOOD_JSON, FakeLLM, make_pdf
from extractor.pdf_text import DocumentError, extract_text
from extractor.service import process_document


def test_reads_pdf_text(invoice_pdf):
    text = extract_text(invoice_pdf)
    assert "INV-2026-0042" in text and "Northwind Packaging Ltd" in text


def test_rejects_non_pdf():
    with pytest.raises(DocumentError, match="not a PDF"):
        extract_text(b"hello, I am a text file")


def test_rejects_pdf_without_text():
    with pytest.raises(DocumentError, match="no text layer"):
        extract_text(make_pdf([]))


def test_complete_extraction(invoice_pdf):
    llm = FakeLLM(GOOD_JSON)
    result = process_document(invoice_pdf, llm)
    assert result.status == "complete"
    assert result.missing_fields == [] and result.warnings == []
    assert result.data.currency == "USD"
    assert str(result.data.invoice_date) == "2026-11-02"
    assert "INV-2026-0042" in llm.calls[0]  # the model was given the PDF text


def test_missing_values_are_flagged_not_guessed(invoice_pdf):
    raw = copy.deepcopy(GOOD_JSON) | {"invoice_number": None, "total": None}
    result = process_document(invoice_pdf, FakeLLM(raw))
    assert result.status == "needs_review"
    assert result.missing_fields == ["invoice_number", "total"]
    assert result.data.total is None


def test_invalid_field_is_dropped_and_rest_kept(invoice_pdf):
    raw = copy.deepcopy(GOOD_JSON) | {"invoice_date": "next tuesday"}
    result = process_document(invoice_pdf, FakeLLM(raw))
    assert result.data.invoice_date is None
    assert result.data.vendor_name == "Northwind Packaging Ltd"
    assert "invoice_date" in result.missing_fields
    assert any("Dropped invoice_date" in w for w in result.warnings)


def test_totals_that_dont_add_up_are_flagged(invoice_pdf):
    raw = copy.deepcopy(GOOD_JSON) | {"total": 150.00}
    result = process_document(invoice_pdf, FakeLLM(raw))
    assert result.status == "needs_review"
    assert any("does not equal total" in w for w in result.warnings)


def test_bad_line_item_math_is_flagged(invoice_pdf):
    raw = copy.deepcopy(GOOD_JSON)
    raw["line_items"][0]["amount"] = 99.0
    result = process_document(invoice_pdf, FakeLLM(raw))
    assert any("Line 1" in w for w in result.warnings)


def test_non_object_response_raises(invoice_pdf):
    with pytest.raises(ValueError):
        process_document(invoice_pdf, FakeLLM(["not", "an", "object"]))
