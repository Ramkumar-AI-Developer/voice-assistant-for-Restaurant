"""
WhatsApp notification service via Twilio REST API.
Sends order details to cook when a new order is placed.
(Using httpx to bypass Windows MAX_PATH limits in the official Twilio SDK)
"""

import logging
from datetime import datetime
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def send_order_to_cook(
    customer_name: str,
    customer_phone: str,
    order_items: list[dict],
    total: float = 0.0,
) -> bool:
    """
    Send a WhatsApp message to the cook with order details using direct Twilio REST API.
    """
    try:
        # Build order lines
        item_lines = []
        for item in order_items:
            line = f"- {item['item']} x{item['quantity']}"
            if item.get('notes'):
                line += f" ({item['notes']})"
            item_lines.append(line)
        items_text = "\n".join(item_lines)

        current_time = datetime.now().strftime("%I:%M %p")

        # Format the WhatsApp message
        message_body = (
            f"🆕 New Order (AI Call)\n\n"
            f"👤 Customer: {customer_name}\n"
            f"📞 Phone: {customer_phone}\n\n"
            f"🛒 Order:\n{items_text}\n\n"
            f"💰 Total: £{total:.2f}\n\n"
            f"⏰ Time: {current_time}\n\n"
            f"✅ Please confirm and enter into POS"
        )

        url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
        
        data = {
            "From": settings.TWILIO_WHATSAPP_FROM.replace(" ", ""),
            "To": settings.COOK_WHATSAPP_NUMBER.replace(" ", ""),
            "Body": message_body,
        }

        # Use sync or async httpx appropriately. Here we'll use sync to drop-in replace
        with httpx.Client() as client:
            response = client.post(
                url,
                data=data,
                auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
                timeout=10.0
            )

        if response.status_code in (200, 201):
            logger.info(f"WhatsApp order notification sent: SID={response.json().get('sid')}")
            return True
        else:
            logger.error(f"WhatsApp API failed: {response.status_code} {response.text}")
            return False

    except Exception as exc:
        logger.error(f"Failed to send WhatsApp notification: {exc}", exc_info=True)
        return False
