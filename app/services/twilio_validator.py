import logging
import os
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from twilio.request_validator import RequestValidator
from app.config import settings

logger = logging.getLogger(__name__)

class TwilioValidator:
    """
    Validates the X-Twilio-Signature header on requests destined for Twilio webhooks.
    To avoid blocking local development, it can be bypassed if explicitly disabled.
    """
    def __init__(self):
        self.validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
        self.base_url = settings.BASE_URL.rstrip('/')

    async def __call__(self, request: Request):
        if os.environ.get("SKIP_TWILIO_VALIDATION") == "true":
            return
            
        signature = request.headers.get("X-Twilio-Signature")
        if not signature:
            logger.warning(f"Missing X-Twilio-Signature on {request.url.path}")
            raise HTTPException(status_code=403, detail="Missing Twilio signature")

        url_from_twilio = f"{self.base_url}{request.url.path}"
        if request.url.query:
            url_from_twilio = f"{url_from_twilio}?{request.url.query}"

        form_data = {}
        if request.method == "POST":
            # Safe to call inside a FastAPI dependency
            form = await request.form()
            form_data = {k: v for k, v in form.multi_items()}

        is_valid = self.validator.validate(url_from_twilio, form_data, signature)

        if not is_valid:
            logger.warning(f"Invalid Twilio signature on {request.url.path}")
            raise HTTPException(status_code=403, detail="Invalid Twilio signature")

validate_twilio_request = TwilioValidator()
