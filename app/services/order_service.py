"""
Order processor: applies structured LLM actions to a CallSession.
Now also persists orders to PostgreSQL and sends WhatsApp notifications.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.menu import find_menu_item, OrderItem
from app.models.session import CallSession, CallStage
from app.models.db_models import Order, OrderItemDB, CallLog, CallMessage
from app.services.whatsapp_service import send_order_to_cook
from app.services.sms_service import send_order_sms_async

logger = logging.getLogger(__name__)


def apply_actions(session: CallSession, actions: list[dict]) -> None:
    """
    Mutate `session` in-place based on the action list from the LLM.

    Supported action types:
        add          — add item(s) to the order
        remove       — remove an item by name
        confirm      — mark order as completed
        cancel       — clear order and mark as abandoned
        repeat_order — no mutation (LLM reply handles the readback)
        set_name     — set customer name
        set_type     — set order type (pickup/delivery)
        none         — no mutation
    """
    for action in actions:
        atype = action.get("type", "none")

        if atype == "add":
            item_name = action.get("item_name", "").strip()
            quantity  = max(1, int(action.get("quantity") or 1))
            notes     = action.get("notes", "").strip()

            menu_item = find_menu_item(item_name)
            if menu_item:
                session.add_item(OrderItem(menu_item=menu_item, quantity=quantity, notes=notes))
                session.stage = CallStage.TAKING_ORDER
                logger.info(f"[{session.call_sid}] +{quantity}× {menu_item.name} (notes='{notes}')")
            else:
                logger.warning(f"[{session.call_sid}] Item not found on menu: '{item_name}'")

        elif atype == "remove":
            item_name = action.get("item_name", "").strip()
            removed = session.remove_item(item_name)
            logger.info(f"[{session.call_sid}] Remove '{item_name}': {'ok' if removed else 'not found'}")

        elif atype == "confirm":
            if session.order_items:
                session.stage = CallStage.COMPLETED
                logger.info(f"[{session.call_sid}] Order confirmed — total ${session.order_total:.2f}")
            else:
                logger.warning(f"[{session.call_sid}] Confirm with empty order — ignored")

        elif atype == "cancel":
            session.order_items.clear()
            session.stage = CallStage.ABANDONED
            logger.info(f"[{session.call_sid}] Order cancelled")

        elif atype == "set_name":
            name = action.get("name", "").strip()
            if name:
                session.customer_name = name
                logger.info(f"[{session.call_sid}] Customer name set: {name}")

        elif atype in ("repeat_order", "none", "set_type"):
            pass  # handled purely in the LLM reply text

        else:
            logger.debug(f"[{session.call_sid}] Unknown action type: {atype}")


async def save_order_to_db(session: CallSession, db: AsyncSession) -> int:
    """
    Persist a completed order to the database.
    Returns the order ID.
    """
    order = Order(
        customer_name=session.customer_name or "Unknown",
        customer_phone=session.phone_number,
        order_type="pickup",
        status="confirmed",
        total=session.order_total,
        call_sid=session.call_sid,
    )
    db.add(order)
    await db.flush()  # Get the order ID

    for oi in session.order_items:
        order_item = OrderItemDB(
            order_id=order.id,
            menu_item_name=oi.menu_item.name,
            quantity=oi.quantity,
            unit_price=oi.menu_item.price,
            notes=oi.notes,
            subtotal=oi.subtotal,
        )
        db.add(order_item)

    await db.commit()
    logger.info(f"[{session.call_sid}] Order #{order.id} saved to database")

    # Send WhatsApp notification to cook
    try:
        send_order_to_cook(
            customer_name=session.customer_name or "Unknown",
            customer_phone=session.phone_number,
            order_items=[oi.to_dict() for oi in session.order_items],
            total=session.order_total,
        )
    except Exception as exc:
        logger.error(f"WhatsApp send failed (non-blocking): {exc}")

    # Send SMS receipt to caller
    try:
        total = sum((oi.menu_item.price * oi.quantity) for oi in session.order_items)
        import asyncio
        asyncio.create_task(
            send_order_sms_async(
                phone_number=session.phone_number,
                order_id=order.id,
                items=session.order_items,
                total=total,
            )
        )
    except Exception as exc:
        logger.error(f"Failed to queue SMS receipt: {exc}")

    return order.id


async def save_call_log(session: CallSession, db: AsyncSession, order_id: int = None) -> None:
    """Persist call log and full transcript to the database."""
    import time
    from sqlalchemy import select

    result = await db.execute(select(CallLog).where(CallLog.call_sid == session.call_sid))
    call_log = result.scalar_one_or_none()

    from app.models.db_models import CallStatus
    from app.models.session import CallStage

    # Map conversational stage to formal call status for the database logger
    if session.stage == CallStage.COMPLETED:
        mapped_status = CallStatus.COMPLETED.value
    elif session.stage == CallStage.ABANDONED:
        mapped_status = CallStatus.ABANDONED.value
    else:
        # If the call ends while greeting, taking order, etc. without completing
        mapped_status = CallStatus.ABANDONED.value

    if call_log:
        call_log.customer_name = session.customer_name or "Unknown"
        call_log.status = mapped_status
        call_log.duration_seconds = int(time.time() - session.created_at)
        call_log.order_id = order_id
    else:
        call_log = CallLog(
            call_sid=session.call_sid,
            phone_number=session.phone_number,
            customer_name=session.customer_name or "Unknown",
            status=mapped_status,
            duration_seconds=int(time.time() - session.created_at),
            order_id=order_id,
        )
        db.add(call_log)
        
    await db.flush()

    # Save all conversation messages
    for msg in session.conversation:
        if msg.role == "system":
            continue  # Don't store system prompts
        call_msg = CallMessage(
            call_log_id=call_log.id,
            role=msg.role,
            content=msg.content,
        )
        db.add(call_msg)

    await db.commit()
    logger.info(f"[{session.call_sid}] Call log saved with {len(session.conversation)} messages")
