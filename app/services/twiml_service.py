"""
TwiML response builders.
Minimal set retained for error fallbacks only.
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


def _xml(root: Element) -> str:
    return '<?xml version="1.0" encoding="UTF-8"?>' + tostring(root, encoding="unicode")


# ── Public builders ───────────────────────────────────────────────────────────

def error_twiml(message: str = "Sorry, something went wrong on our end. Please try calling back.") -> str:
    root = _response()
    _say(root, message)
    SubElement(root, "Hangup")
    return _xml(root)
