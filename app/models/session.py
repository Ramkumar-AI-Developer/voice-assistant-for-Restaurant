"""
Per-call session: conversation history, current order, call stage.
Used by the OpenAI Realtime API WebSocket handler.
"""

import time
from dataclasses import dataclass, field
from enum import Enum

from app.models.menu import OrderItem


class CallStage(str, Enum):
    GREETING     = "greeting"
    TAKING_ORDER = "taking_order"
    CONFIRMING   = "confirming"
    COMPLETED    = "completed"
    ABANDONED    = "abandoned"


@dataclass
class Message:
    role: str       # "system" | "user" | "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


@dataclass
class CallSession:
    call_sid: str
    phone_number: str
    customer_name: str           = ""       # Collected during call
    created_at: float            = field(default_factory=time.monotonic)
    last_active: float           = field(default_factory=time.time)
    stage: CallStage             = CallStage.GREETING
    order_items: list[OrderItem] = field(default_factory=list)
    conversation: list[Message]  = field(default_factory=list)
    silence_count: int           = 0
    error_count: int             = 0
    last_partial: str            = ""
    call_log_saved: bool         = False

    # ── Order helpers ─────────────────────────────────────────────────────────

    def add_item(self, item: OrderItem) -> None:
        """Add item, merging duplicates (same id + notes)."""
        for existing in self.order_items:
            if existing.menu_item.id == item.menu_item.id and existing.notes == item.notes:
                existing.quantity += item.quantity
                return
        self.order_items.append(item)

    def remove_item(self, name: str) -> bool:
        """Remove first item whose name contains `name` (case-insensitive)."""
        name_lower = name.lower()
        for i, oi in enumerate(self.order_items):
            if name_lower in oi.menu_item.name.lower():
                self.order_items.pop(i)
                return True
        return False

    @property
    def order_total(self) -> float:
        return round(sum(oi.subtotal for oi in self.order_items), 2)

    def order_summary_text(self) -> str:
        if not self.order_items:
            return "Your order is currently empty."
        lines = ["Here is your order:"]
        for oi in self.order_items:
            note = f" ({oi.notes})" if oi.notes else ""
            lines.append(f"  {oi.quantity} {oi.menu_item.name}{note} — £{oi.subtotal:.2f}")
        lines.append(f"  Total: £{self.order_total:.2f}")
        return "\n".join(lines)

    # ── Conversation helpers ──────────────────────────────────────────────────

    def add_message(self, role: str, content: str) -> None:
        self.conversation.append(Message(role=role, content=content))
        self.last_active = time.time()



    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "call_sid":      self.call_sid,
            "phone":         self.phone_number,
            "customer_name": self.customer_name,
            "stage":         self.stage.value,
            "order":         [oi.to_dict() for oi in self.order_items],
            "total":         self.order_total,
            "created_at":    self.created_at,
        }
