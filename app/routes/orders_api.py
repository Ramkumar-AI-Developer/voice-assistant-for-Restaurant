"""
Orders API routes.
  GET   /api/orders            — list orders with pagination
  GET   /api/orders/{id}       — single order detail
  GET   /api/orders/export     — download all orders as Excel
  PATCH /api/orders/{id}/status — update order status
"""

import io
import logging
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.db_models import Order, OrderItemDB, User
from app.services.auth_service import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


class StatusUpdate(BaseModel):
    status: str  # pending, confirmed, preparing, ready, completed, cancelled


@router.get("/")
async def list_orders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
):
    """List all orders with pagination."""
    query = select(Order).options(selectinload(Order.items)).order_by(desc(Order.created_at))

    if status:
        query = query.where(Order.status == status)

    # Count total
    count_query = select(func.count(Order.id))
    if status:
        count_query = count_query.where(Order.status == status)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    orders = result.scalars().unique().all()

    return {
        "orders": [
            {
                "id": o.id,
                "customer_name": o.customer_name,
                "customer_phone": o.customer_phone,
                "order_type": o.order_type,
                "status": o.status,
                "total": o.total,
                "call_sid": o.call_sid,
                "notes": o.notes,
                "items": [
                    {
                        "name": item.menu_item_name,
                        "quantity": item.quantity,
                        "unit_price": item.unit_price,
                        "notes": item.notes,
                        "subtotal": item.subtotal,
                    }
                    for item in o.items
                ],
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in orders
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
    }


@router.get("/export")
async def export_orders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export all orders as an Excel file."""
    result = await db.execute(
        select(Order).options(selectinload(Order.items)).order_by(desc(Order.created_at))
    )
    orders = result.scalars().unique().all()

    rows = []
    for o in orders:
        for item in o.items:
            rows.append({
                "Order ID": o.id,
                "Date": o.created_at.strftime("%Y-%m-%d %H:%M") if o.created_at else "",
                "Customer Name": o.customer_name,
                "Phone": o.customer_phone,
                "Item": item.menu_item_name,
                "Quantity": item.quantity,
                "Unit Price": item.unit_price,
                "Subtotal": item.subtotal,
                "Notes": item.notes,
                "Order Type": o.order_type,
                "Status": o.status,
                "Order Total": o.total,
            })

    if not rows:
        rows = [{"Message": "No orders found"}]

    df = pd.DataFrame(rows)
    output = io.BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=orders_export.xlsx"},
    )


@router.get("/{order_id}")
async def get_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single order with items."""
    result = await db.execute(
        select(Order).options(selectinload(Order.items)).where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return {
        "id": order.id,
        "customer_name": order.customer_name,
        "customer_phone": order.customer_phone,
        "order_type": order.order_type,
        "status": order.status,
        "total": order.total,
        "call_sid": order.call_sid,
        "notes": order.notes,
        "items": [
            {
                "name": item.menu_item_name,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "notes": item.notes,
                "subtotal": item.subtotal,
            }
            for item in order.items
        ],
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
    }


@router.patch("/{order_id}/status")
async def update_order_status(
    order_id: int,
    body: StatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update order status."""
    valid_statuses = {"pending", "confirmed", "preparing", "ready", "completed", "cancelled"}
    if body.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.status = body.status
    await db.commit()

    return {"message": f"Order #{order_id} status updated to '{body.status}'"}
