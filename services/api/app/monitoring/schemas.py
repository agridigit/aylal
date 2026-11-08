"""Strict request bodies of the F3 routes (ObservationInput is generated from the Zod schema)."""
from pydantic import BaseModel, ConfigDict, Field

from app.generated.models import ObservationInput

__all__ = ["ObservationInput", "SummarySettings"]


class SummarySettings(BaseModel):
    """Hour of the daily summary and alerts switch; both belong to the caller. No token or key is accepted."""

    model_config = ConfigDict(extra="forbid")
    summary_hour: int = Field(ge=0, le=23)
    alerts_enabled: bool
