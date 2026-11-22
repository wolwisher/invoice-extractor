"""The fields we pull out of an invoice, and the checks they must pass."""
from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class LineItem(BaseModel):
    description: str
    quantity: float = Field(gt=0)
    unit_price: float = Field(ge=0)
    amount: float = Field(ge=0)


class Invoice(BaseModel):
    """Every field is optional: if the document doesn't clearly show a value we keep it null
    and list it in `missing_fields` instead of letting the model guess."""

    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    vendor_name: Optional[str] = None
    customer_name: Optional[str] = None
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    subtotal: Optional[float] = Field(default=None, ge=0)
    tax: Optional[float] = Field(default=None, ge=0)
    total: Optional[float] = Field(default=None, ge=0)
    line_items: list[LineItem] = []

    @field_validator("currency")
    @classmethod
    def upper_currency(cls, v):
        return v.upper() if v else v

    @model_validator(mode="after")
    def dates_in_order(self):
        if self.invoice_date and self.due_date and self.due_date < self.invoice_date:
            raise ValueError("due_date is before invoice_date")
        return self


REQUIRED = ["invoice_number", "invoice_date", "vendor_name", "total"]


class ExtractionResult(BaseModel):
    status: str  # "complete" | "needs_review"
    data: Invoice
    missing_fields: list[str]
    warnings: list[str]
