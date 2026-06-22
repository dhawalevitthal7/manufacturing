"""Phase 8: External KR value ingest (SCADA / MES / SAP webhooks)."""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from server.database import get_db
from server.services.kr_ingest_service import process_kr_ingest

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


class KRIngestPayload(BaseModel):
    source_metric_tag: str
    value: float
    timestamp: Optional[str] = None


@router.post("/kr-ingest")
def kr_ingest(
    body: KRIngestPayload,
    request: Request,
    db: Session = Depends(get_db),
    x_ingest_token: Optional[str] = Header(None, alias="X-Ingest-Token"),
):
    """
    Ingest a metric value for a configured KR (no JWT — token in X-Ingest-Token header).
    Rate-limited to 60 requests/minute per ingest source.
    """
    if not x_ingest_token:
        raise HTTPException(401, "X-Ingest-Token header required")

    ip = request.client.host if request.client else None
    return process_kr_ingest(
        db,
        source_metric_tag=body.source_metric_tag,
        value=body.value,
        raw_token=x_ingest_token,
        timestamp=body.timestamp,
        ip_address=ip,
    )
