"""Structured types for the Campus Customs vendor desk agent."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class VendorQuote(BaseModel):
    """The agent's final answer for one vendor document."""

    vendor: Optional[str] = Field(
        description="Vendor company name as written in the document, or null if not stated."
    )
    sku: Optional[str] = Field(
        description="Campus Customs SKU the quote is for, e.g. CC-HD-006, or null if not stated."
    )
    unit_price: Optional[float] = Field(
        description="Quoted price per unit in USD, as a number (21.80 -> 21.8), or null if not stated."
    )
    lead_time_days: Optional[int] = Field(
        description="Lead time in days as stated by the vendor (business days count as days), or null."
    )
    min_order: Optional[int] = Field(
        description="Minimum order quantity in units, or null if not stated."
    )
    decision: Literal["recommend", "do_not_recommend"] = Field(
        description="recommend only if all four handbook purchasing checks pass."
    )
    reason: str = Field(
        description="One sentence that names the purchasing check that decided it."
    )

