"""
TwiML response builders.

All XML is constructed here so routes stay clean.

Barge-in / interrupt design:
  • Every <Gather> includes partialResultCallback so Twilio fires a webhook
    the moment the caller starts speaking — even mid-TTS playback.
  • actionOnEmptyResult="true" ensures we always get a callback (silence too).
  • speechModel="phone_call" + enhanced="true" gives highest accuracy on
    telephony audio.
"""

from xml.etree.ElementTree import Element, SubElement, tostring

from app.config import settings


# ── Internal helpers ──────────────────────────────────────────────────────────

def _response() -> Element:
    return Element("Response")


def _say(parent: Element, text: str) -> None:
    el = SubElement(parent, "Say")
    el.set("voice", settings.TWILIO_VOICE)
    el.set("language", settings.TWILIO_LANGUAGE)
    el.text = text


def _gather(parent: Element, action_path: str) -> Element:
    g = SubElement(parent, "Gather")
    g.set("input", "speech")
    g.set("action", f"{settings.BASE_URL}{action_path}")
    g.set("method", "POST")
    g.set("speechTimeout", "0.5")                 # Fast 1s timeout after speech ends
    g.set("speechModel", "phone_call")
    g.set("enhanced", "true")
    g.set("partialResultCallback", f"{settings.BASE_URL}/webhook/partial")
    g.set("partialResultCallbackMethod", "POST")
    g.set("actionOnEmptyResult", "true")
    return g


def _redirect(parent: Element, path: str) -> None:
    el = SubElement(parent, "Redirect")
    el.set("method", "POST")
    el.text = f"{settings.BASE_URL}{path}"


def _xml(root: Element) -> str:
    return '<?xml version="1.0" encoding="UTF-8"?>' + tostring(root, encoding="unicode")


# ── Public builders ───────────────────────────────────────────────────────────

def greeting_twiml(greeting_text: str) -> str:
    """Play greeting then open listening loop."""
    root = _response()
    gather = _gather(root, "/webhook/speech")
    _say(gather, greeting_text)
    # Fallback if caller says nothing after greeting
    _say(root, "I didn't catch that. Whenever you're ready, go ahead and tell me what you'd like.")
    _redirect(root, "/webhook/speech")
    return _xml(root)


def listen_twiml(prompt_text: str) -> str:
    """Say a reply then listen for the next utterance."""
    root = _response()
    gather = _gather(root, "/webhook/speech")
    _say(gather, prompt_text)
    # Silence fallback
    _say(root, "Still there? Feel free to tell me your order whenever you're ready.")
    _redirect(root, "/webhook/speech")
    return _xml(root)


def confirm_order_twiml(order_summary: str) -> str:
    """Read back the full order and ask for yes/no confirmation."""
    root = _response()
    gather = _gather(root, "/webhook/confirm")
    _say(gather, (
        f"{order_summary}. "
        "Shall I go ahead and place that order? "
        "Say yes to confirm or no to make changes."
    ))
    # Repeat if no answer
    _say(root, "I didn't catch your answer. Let me repeat your order.")
    _redirect(root, "/webhook/speech")
    return _xml(root)


def order_placed_twiml(total: float) -> str:
    """Thank the caller, state total, hang up."""
    root = _response()
    _say(root, (
        f"Perfect! Your order has been placed and your total is £{total:.2f}. "
        "We will have it ready for you shortly. "
        "Thank you for calling Shiva Vilas. Goodbye!"
    ))
    SubElement(root, "Hangup")
    return _xml(root)


def cancelled_twiml() -> str:
    root = _response()
    _say(root, "No problem — your order has been cancelled. Have a great day. Goodbye!")
    SubElement(root, "Hangup")
    return _xml(root)


def error_twiml(message: str = "Sorry, something went wrong on our end. Please try calling back.") -> str:
    root = _response()
    _say(root, message)
    SubElement(root, "Hangup")
    return _xml(root)


def silence_twiml(prompt: str) -> str:
    """Re-prompt after silence without an additional assistant message."""
    root = _response()
    gather = _gather(root, "/webhook/speech")
    _say(gather, prompt)
    _redirect(root, "/webhook/speech")
    return _xml(root)
