import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def make_pdf(lines):
    """Build a minimal one-page PDF with a text layer, no extra libraries needed."""
    stream = "BT /F1 11 Tf 50 780 Td 14 TL\n" + "".join(
        "(" + line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ") Tj T*\n" for line in lines
    ) + "ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
    ]
    out, offsets = "%PDF-1.4\n", []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{obj}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n" + "".join(f"{o:010d} 00000 n \n" for o in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    return out.encode("latin-1")


INVOICE_LINES = [
    "INVOICE  INV-2026-0042",
    "Date: 2026-11-02    Due: 2026-12-02",
    "From: Northwind Packaging Ltd",
    "Bill to: Green Valley Foods",
    "PET Bottle 500ml   1000 x 0.12 = 120.00",
    "Subtotal 120.00   Tax 21.60   Total USD 141.60",
]

GOOD_JSON = {
    "invoice_number": "INV-2026-0042",
    "invoice_date": "2026-11-02",
    "due_date": "2026-12-02",
    "vendor_name": "Northwind Packaging Ltd",
    "customer_name": "Green Valley Foods",
    "currency": "usd",
    "subtotal": 120.00,
    "tax": 21.60,
    "total": 141.60,
    "line_items": [{"description": "PET Bottle 500ml", "quantity": 1000, "unit_price": 0.12, "amount": 120.00}],
}


class FakeLLM:
    """Stands in for the real model so tests are fast, free and deterministic."""

    def __init__(self, response):
        self.response = response
        self.calls = []

    def extract(self, text, json_schema):
        self.calls.append(text)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@pytest.fixture
def invoice_pdf():
    return make_pdf(INVOICE_LINES)
