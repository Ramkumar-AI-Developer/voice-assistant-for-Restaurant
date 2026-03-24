"""
Restaurant menu definition and order dataclasses.
Supports both static fallback menu and dynamic loading from PostgreSQL.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

logger = logging.getLogger(__name__)


# ── Dataclasses (used in session / in-memory) ─────────────────────────────────

@dataclass
class MenuItem:
    id: str
    name: str
    price: float
    description: str
    category: str
    available: bool = True
    customisations: list[str] = field(default_factory=list)


@dataclass
class OrderItem:
    menu_item: MenuItem
    quantity: int
    notes: str = ""

    @property
    def subtotal(self) -> float:
        return round(self.menu_item.price * self.quantity, 2)

    def to_dict(self) -> dict:
        return {
            "item": self.menu_item.name,
            "quantity": self.quantity,
            "unit_price": self.menu_item.price,
            "subtotal": self.subtotal,
            "notes": self.notes,
        }


# ── Dynamic menu cache ────────────────────────────────────────────────────────

# Loaded from DB on startup, refreshed when menu is updated
_MENU_CACHE: dict[str, MenuItem] = {}


async def load_menu_from_db(db: AsyncSession) -> dict[str, MenuItem]:
    """Load all available menu items from the database into the in-memory cache."""
    global _MENU_CACHE

    from app.models.db_models import MenuItemDB, Category

    result = await db.execute(
        select(MenuItemDB)
        .options(selectinload(MenuItemDB.category))
        .where(MenuItemDB.available == True)
        .order_by(MenuItemDB.category_id, MenuItemDB.name)
    )
    db_items = result.scalars().all()

    menu = {}
    for item in db_items:
        menu_id = f"DB{item.id:03d}"
        menu[menu_id] = MenuItem(
            id=menu_id,
            name=item.name,
            price=item.price,
            description=item.description or "",
            category=item.category.name.lower() if item.category else "uncategorized",
            available=item.available,
            customisations=item.customisations or [],
        )

    if menu:
        _MENU_CACHE = menu
        logger.info(f"Loaded {len(menu)} menu items from database")
    else:
        logger.warning("No menu items in database, using static fallback")
        _MENU_CACHE = _STATIC_MENU.copy()

    return _MENU_CACHE


def get_menu() -> dict[str, MenuItem]:
    """Return the current menu (cached from DB or static fallback)."""
    if _MENU_CACHE:
        return _MENU_CACHE
    return _STATIC_MENU


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_menu_text() -> str:
    """Compact menu string injected into the LLM system prompt."""
    menu = get_menu()
    lines: list[str] = []
    current_cat: Optional[str] = None
    for item in menu.values():
        if not item.available:
            continue
        if item.category != current_cat:
            current_cat = item.category
            lines.append(f"\n[{current_cat.upper()}]")
        opts = f"  (options: {', '.join(item.customisations)})" if item.customisations else ""
        lines.append(f"  • {item.name} — ${item.price:.2f}{opts}")
    return "\n".join(lines)


def find_menu_item(name: str) -> Optional[MenuItem]:
    """Case-insensitive substring match on item name."""
    menu = get_menu()
    name_lower = name.lower()
    for item in menu.values():
        if item.available and name_lower in item.name.lower():
            return item
    return None


# ── Static fallback menu ─────────────────────────────────────────────────────

_STATIC_MENU: dict[str, MenuItem] = {
    "S001": MenuItem("S001", "Garlic Bread",          3.99, "Toasted bread with garlic butter",              "starters"),
    "S002": MenuItem("S002", "Caesar Salad",           7.99, "Romaine, croutons, parmesan, caesar dressing",  "starters"),
    "S003": MenuItem("S003", "Soup of the Day",        5.99, "Ask your server for today's selection",         "starters"),
    "M001": MenuItem("M001", "Classic Burger",        12.99, "Beef patty, lettuce, tomato, pickles",          "mains",
                     customisations=["no onion", "extra cheese", "gluten-free bun"]),
    "M002": MenuItem("M002", "Grilled Chicken",       14.99, "Herb-marinated chicken breast, seasonal veg",   "mains",
                     customisations=["no sauce", "extra veg"]),
    "M003": MenuItem("M003", "Margherita Pizza",      13.99, "Tomato, fresh mozzarella, basil",               "mains",
                     customisations=["thin crust", "gluten-free base", "extra cheese"]),
    "M004": MenuItem("M004", "Pasta Arrabiata",       11.99, "Penne, spicy tomato, garlic",                   "mains",
                     customisations=["no chilli", "add chicken +2"]),
    "M005": MenuItem("M005", "Fish and Chips",        15.99, "Beer-battered cod, chunky chips, mushy peas",   "mains"),
    "M006": MenuItem("M006", "Veggie Wrap",            9.99, "Falafel, hummus, roasted peppers, spinach",     "mains",
                     customisations=["gluten-free wrap", "no hummus"]),
    "D001": MenuItem("D001", "Chocolate Lava Cake",   6.99, "Warm cake with vanilla ice cream",              "desserts"),
    "D002": MenuItem("D002", "Cheesecake",             5.99, "New York style with berry compote",             "desserts"),
    "D003": MenuItem("D003", "Ice Cream",              4.99, "3 scoops: vanilla, chocolate, or strawberry",  "desserts"),
    "DR01": MenuItem("DR01", "Soft Drink",             2.99, "Coke, Diet Coke, Sprite, or Fanta",            "drinks"),
    "DR02": MenuItem("DR02", "Fresh Juice",            3.99, "Orange, apple, or mango",                      "drinks"),
    "DR03": MenuItem("DR03", "Sparkling Water",        2.49, "500 ml bottle",                                "drinks"),
    "DR04": MenuItem("DR04", "House Wine",             5.99, "Glass of red or white",                        "drinks"),
    "DR05": MenuItem("DR05", "Beer",                   4.99, "Domestic or imported",                         "drinks"),
    "DR06": MenuItem("DR06", "Coffee",                 2.99, "Espresso, Americano, Latte, or Cappuccino",    "drinks"),
}
