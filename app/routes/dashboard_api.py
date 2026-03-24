"""
Dashboard API routes.
  GET /api/dashboard/stats — aggregated stats for the dashboard
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.db_models import Order, CallLog, User
from app.services.auth_service import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/stats")
async def dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get aggregated stats for the dashboard."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)

    # ── Today's stats ─────────────────────────────────────────────────────────

    # Orders today
    result = await db.execute(
        select(func.count(Order.id)).where(Order.created_at >= today_start)
    )
    orders_today = result.scalar() or 0

    # Revenue today
    result = await db.execute(
        select(func.coalesce(func.sum(Order.total), 0)).where(Order.created_at >= today_start)
    )
    revenue_today = round(result.scalar() or 0, 2)

    # Calls today
    result = await db.execute(
        select(func.count(CallLog.id)).where(CallLog.started_at >= today_start)
    )
    calls_today = result.scalar() or 0

    # Avg call duration today
    result = await db.execute(
        select(func.coalesce(func.avg(CallLog.duration_seconds), 0))
        .where(CallLog.started_at >= today_start)
    )
    avg_duration_today = round(result.scalar() or 0)

    # ── All-time stats ────────────────────────────────────────────────────────

    result = await db.execute(select(func.count(Order.id)))
    total_orders = result.scalar() or 0

    result = await db.execute(
        select(func.coalesce(func.sum(Order.total), 0))
    )
    total_revenue = round(result.scalar() or 0, 2)

    result = await db.execute(select(func.count(CallLog.id)))
    total_calls = result.scalar() or 0

    # ── Weekly order trend (last 7 days) ──────────────────────────────────────
    weekly_orders = []
    for i in range(6, -1, -1):
        day_start = today_start - timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        result = await db.execute(
            select(func.count(Order.id)).where(
                Order.created_at >= day_start,
                Order.created_at < day_end,
            )
        )
        count = result.scalar() or 0
        weekly_orders.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "day": day_start.strftime("%a"),
            "orders": count,
        })

    # ── Recent orders ─────────────────────────────────────────────────────────
    result = await db.execute(
        select(Order).order_by(Order.created_at.desc()).limit(5)
    )
    recent_orders = result.scalars().all()

    # ── Pending orders ────────────────────────────────────────────────────────
    result = await db.execute(
        select(func.count(Order.id)).where(Order.status.in_(["pending", "confirmed", "preparing"]))
    )
    pending_orders = result.scalar() or 0

    return {
        "today": {
            "orders": orders_today,
            "revenue": revenue_today,
            "calls": calls_today,
            "avg_call_duration": avg_duration_today,
        },
        "totals": {
            "orders": total_orders,
            "revenue": total_revenue,
            "calls": total_calls,
        },
        "pending_orders": pending_orders,
        "weekly_trend": weekly_orders,
        "recent_orders": [
            {
                "id": o.id,
                "customer_name": o.customer_name,
                "total": o.total,
                "status": o.status,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in recent_orders
        ],
    }
