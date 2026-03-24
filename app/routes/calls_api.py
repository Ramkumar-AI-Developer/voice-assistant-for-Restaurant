"""
Call logs API routes.
  GET /api/calls      — list call logs with pagination
  GET /api/calls/{id} — single call with full transcript
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.db_models import CallLog, CallMessage, User
from app.services.auth_service import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def list_calls(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
):
    """List all call logs with pagination."""
    query = select(CallLog).order_by(desc(CallLog.started_at))

    if status:
        query = query.where(CallLog.status == status)

    # Count total
    count_query = select(func.count(CallLog.id))
    if status:
        count_query = count_query.where(CallLog.status == status)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    calls = result.scalars().all()

    return {
        "calls": [
            {
                "id": c.id,
                "call_sid": c.call_sid,
                "phone_number": c.phone_number,
                "customer_name": c.customer_name,
                "status": c.status,
                "started_at": c.started_at.isoformat() if c.started_at else None,
                "ended_at": c.ended_at.isoformat() if c.ended_at else None,
                "duration_seconds": c.duration_seconds,
                "order_id": c.order_id,
            }
            for c in calls
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
    }


@router.get("/{call_id}")
async def get_call_detail(
    call_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single call log with full conversation transcript."""
    result = await db.execute(
        select(CallLog)
        .options(selectinload(CallLog.messages))
        .where(CallLog.id == call_id)
    )
    call = result.scalar_one_or_none()
    if not call:
        raise HTTPException(status_code=404, detail="Call log not found")

    return {
        "id": call.id,
        "call_sid": call.call_sid,
        "phone_number": call.phone_number,
        "customer_name": call.customer_name,
        "status": call.status,
        "started_at": call.started_at.isoformat() if call.started_at else None,
        "ended_at": call.ended_at.isoformat() if call.ended_at else None,
        "duration_seconds": call.duration_seconds,
        "order_id": call.order_id,
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "timestamp": m.timestamp.isoformat() if m.timestamp else None,
            }
            for m in call.messages
        ],
    }
