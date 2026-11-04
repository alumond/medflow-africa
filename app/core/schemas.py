"""Strict input contracts shared by ingestion, API and test fixtures."""

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SafeID = str


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Facility(Contract):
    facility_id: SafeID = Field(pattern=r"^[A-Za-z0-9_-]{1,50}$")
    facility_name: str = Field(min_length=1, max_length=120)
    facility_type: Literal["hospital", "health_centre", "clinic"]
    location_type: Literal["urban", "peri_urban", "rural"]
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    lead_time_days: int = Field(ge=0, le=365)
    reporting_target: float = Field(ge=0, le=1)
    active: bool = True


class Medicine(Contract):
    medicine_id: SafeID = Field(pattern=r"^[A-Za-z0-9_-]{1,50}$")
    medicine_name: str = Field(min_length=1, max_length=120)
    category: Literal[
        "antibiotic",
        "antimalarial",
        "maternal_health",
        "analgesic",
        "rehydration",
        "chronic_care",
        "nutrition",
    ]
    pack_size: int = Field(gt=0, le=100000)
    safety_stock_days: int = Field(ge=0, le=365)
    minimum_shelf_life_days: int = Field(ge=0, le=730)
    active: bool = True


class Inventory(Contract):
    record_id: SafeID = Field(pattern=r"^[A-Za-z0-9_-]{1,50}$")
    reporting_date: date
    facility_id: str
    medicine_id: str
    opening_balance: int = Field(ge=0)
    quantity_received: int = Field(ge=0)
    quantity_dispensed: int = Field(ge=0)
    adjustments: int = Field(ge=-10000000, le=10000000)
    closing_balance: int = Field(ge=0)
    stockout_days: int = Field(ge=0, le=7)
    expiry_date: Optional[date] = None
    quantity_near_expiry: int = Field(ge=0)
    report_submitted_on_time: bool

    @model_validator(mode="after")
    def reconcile(self):
        """Reject inconsistent usable balances instead of repairing them."""
        if (
            self.closing_balance
            != self.opening_balance + self.quantity_received - self.quantity_dispensed + self.adjustments
        ):
            raise ValueError("BALANCE: closing balance does not reconcile")
        if self.quantity_near_expiry > self.closing_balance:
            raise ValueError("EXPIRY_QUANTITY: near-expiry quantity exceeds stock")
        if self.expiry_date and self.expiry_date < self.reporting_date and self.closing_balance:
            raise ValueError("EXPIRY_DATE: usable stock has already expired")
        return self


class Order(Contract):
    order_id: SafeID = Field(pattern=r"^[A-Za-z0-9_-]{1,50}$")
    facility_id: str
    medicine_id: str
    order_date: date
    quantity_ordered: int = Field(gt=0)
    expected_delivery_date: date
    actual_delivery_date: Optional[date] = None
    quantity_delivered: int = Field(ge=0)
    order_status: Literal["pending", "partial", "fulfilled", "cancelled"]

    @model_validator(mode="after")
    def delivery(self):
        """Enforce date, quantity and order-state coherence."""
        if self.expected_delivery_date < self.order_date:
            raise ValueError("ORDER_DATE: expected date precedes order")
        if self.actual_delivery_date and self.actual_delivery_date < self.order_date:
            raise ValueError("DELIVERY_DATE: delivery precedes order")
        if self.order_status in ("fulfilled", "partial") and not self.actual_delivery_date:
            raise ValueError("DELIVERY_DATE: delivered orders require a date")
        if self.order_status == "fulfilled" and self.quantity_delivered != self.quantity_ordered:
            raise ValueError("FULFILMENT: fulfilled quantity must match order")
        if self.order_status == "partial" and not 0 < self.quantity_delivered < self.quantity_ordered:
            raise ValueError("FULFILMENT: partial quantity must be below order")
        if self.order_status == "pending" and (self.actual_delivery_date or self.quantity_delivered):
            raise ValueError("FULFILMENT: pending order cannot have deliveries")
        return self


class ReviewRequest(Contract):
    decision: Literal["accepted", "edited", "rejected"]
    reviewer: str = Field(min_length=2, max_length=80)
    note: str = Field(min_length=5, max_length=1000)
    expected_version: int = Field(ge=1)
    quantity: Optional[int] = Field(default=None, gt=0)
    acknowledged: Literal[True]


class Action(Contract):
    finding_id: str
    action: str = Field(min_length=5, max_length=600)
    owner: str = Field(min_length=2, max_length=80)
    due_date: date
    status: Literal["open", "in_progress", "closed"] = "open"


class CopilotRequest(Contract):
    question: str = Field(min_length=5, max_length=600)
    window: Literal[7, 14, 30] = 14
    use_gemini: bool = True
    finding_id: Optional[str] = Field(default=None, max_length=60)
    recommendation_id: Optional[str] = Field(default=None, max_length=60)


class ReportRequest(Contract):
    window: Literal[7, 14, 30] = 14
    narrative_mode: Literal["deterministic", "gemini"] = "deterministic"
    management_note: str = Field(default="", max_length=3000)
    prepared_by: str = Field(default="District supply team", max_length=100)
    selected_findings: Optional[list[str]] = None
    actions: list[Action] = Field(default_factory=list, max_length=100)

    @field_validator("prepared_by")
    @classmethod
    def author_required(cls, value):
        if not value.strip():
            raise ValueError("Prepared by is required")
        return value
