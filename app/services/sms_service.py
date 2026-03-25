import logging
from twilio.rest import Client
import asyncio
from typing import List

from app.config import settings
from app.models.menu import OrderItem

logger = logging.getLogger(__name__)

def send_order_sms(phone_number: str, order_id: int, items: List[OrderItem], total: float):
    """
    Sends an SMS receipt to the customer using Twilio.
    Executed in a background thread to avoid blocking the main async loop.
    """
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        logger.warning(f"Twilio credentials missing. Skipping SMS for order {order_id}")
        return

    # Validate phone number before attempting to send
    if not phone_number or phone_number == "unknown" or len(phone_number) < 8:
        logger.warning(f"Invalid phone number '{phone_number}'. Skipping SMS for order {order_id}")
        return

    try:
        from_number = settings.TWILIO_PHONE_NUMBER
        
        # Format the receipt
        receipt_lines = [f"🧾 The Golden Fork - Order #{order_id}"]
        receipt_lines.append("---")
        
        for item in items:
            line = f"{item.quantity}x {item.menu_item.name}"
            if item.notes:
                line += f" ({item.notes})"
            line += f" - £{item.quantity * item.menu_item.price:.2f}"
            receipt_lines.append(line)
            
        receipt_lines.append("---")
        receipt_lines.append(f"Total: £{total:.2f}")
        receipt_lines.append("Thank you for your order! We'll begin preparing it right away.")

        message_body = "\n".join(receipt_lines)

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        
        # Using to_number format parsing might be necessary based on database storage, 
        # but Twilio handles +E.164 formats automatically.
        to_number = phone_number if phone_number.startswith('+') else f"+{phone_number.lstrip('+')}"

        message = client.messages.create(
            body=message_body,
            from_=from_number,
            to=to_number
        )
        logger.info(f"SMS receipt sent to {to_number} (SID: {message.sid})")
        
    except Exception as e:
        logger.error(f"Failed to send SMS receipt to {phone_number}: {e}")

async def send_order_sms_async(phone_number: str, order_id: int, items: List[OrderItem], total: float):
    """Async wrapper around the Twilio sync sending client."""
    await asyncio.to_thread(send_order_sms, phone_number, order_id, items, total)
