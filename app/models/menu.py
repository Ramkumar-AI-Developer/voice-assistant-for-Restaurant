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
        lines.append(f"  • {item.name} — £{item.price:.2f}{opts}")
    return "\n".join(lines)


def find_menu_item(name: str) -> Optional[MenuItem]:
    """Case-insensitive match: exact name first, then substring fallback."""
    menu = get_menu()
    name_lower = name.lower().strip()
    # 1. Exact match
    for item in menu.values():
        if item.available and item.name.lower() == name_lower:
            return item
    # 2. Substring fallback
    for item in menu.values():
        if item.available and name_lower in item.name.lower():
            return item
    return None


# ── Static fallback menu ─────────────────────────────────────────────────────
# Note: Allergen warning — food prepared in a kitchen where Nuts, Sesame and
# other allergenic ingredients are used. Cannot guarantee traces-free products.

_STATIC_MENU: dict[str, MenuItem] = {
    # ── Soup Bowl ──────────────────────────────────────────────────────────
    "SB01": MenuItem("SB01", "Hot & Sour Veg Soup",    4.99, "Hot and spicy thick soup made with sautéed fresh vegetables and soy sauce.",                      "soup bowl"),
    "SB02": MenuItem("SB02", "Sweet Corn Soup",         4.99, "Lightly spiced corn soup flavoured with pepper.",                                                 "soup bowl"),
    "SB03": MenuItem("SB03", "Mushroom Soup",           4.99, "Lightly spiced minced mushroom soup garnished with cream.",                                       "soup bowl"),
    "SB04": MenuItem("SB04", "Pepper Rasam Soup",       4.50, "Traditional South Indian sour & spicy soup with diced fresh tomatoes & tamarind juice.",          "soup bowl"),

    # ── Starters ───────────────────────────────────────────────────────────
    "ST01": MenuItem("ST01", "Gobi 65",                 8.50, "Battered cauliflower florets deep fried with spices and chilli paste.",                           "starters"),
    "ST02": MenuItem("ST02", "Paneer 65",               8.99, "Batter deep fried Indian cottage cheese chunks flavoured with spicy paste.",                      "starters"),
    "ST03": MenuItem("ST03", "Mogo 65",                 7.99, "Casava marinated in Indian & Chinese spices, dipped in gram flour batter & deep fried.",          "starters"),
    "ST04": MenuItem("ST04", "Mushroom 65",             7.99, "Battered fried mushroom sautéed with spices & chilli paste.",                                     "starters"),
    "ST05": MenuItem("ST05", "Paneer Tikka",            9.99, "Chunks of cottage cheese marinated in special herbs & spices & grilled in a clay oven.",          "starters"),
    "ST06": MenuItem("ST06", "Paneer Pepper Fry",       9.50, "Chunks of cottage cheese batter fried & sautéed with flavoured spices & pepper.",                 "starters"),
    "ST07": MenuItem("ST07", "Mushroom Pepper Fry",     8.99, "Mushroom batter fried & sautéed with flavoured spices & pepper.",                                 "starters"),
    "ST08": MenuItem("ST08", "Chilly Paneer",           8.99, "Cottage cheese diced marinated in an authentic South Indian chilli mix & pan cooked.",            "starters",
                     customisations=["dry", "gravy"]),
    "ST09": MenuItem("ST09", "Chilly Baby Corn",        8.99, "Baby corn diced marinated in an authentic South Indian chilli mix & pan cooked.",                 "starters",
                     customisations=["dry", "gravy"]),
    "ST10": MenuItem("ST10", "Chilly Mogo",             8.75, "Steamed tapioca pieces deep fried and tossed in chef's special chilli sauce & spices.",           "starters",
                     customisations=["dry", "gravy"]),
    "ST11": MenuItem("ST11", "Chilly Gobi",             8.50, "Steamed cauliflower pieces deep fried and tossed in chef's special chilli sauce & spices.",       "starters",
                     customisations=["dry", "gravy"]),
    "ST12": MenuItem("ST12", "Veg Manchurian",          8.99, "Minced vegetables deep fried in balls sautéed with onion & garlic in Manchurian sauce.",          "starters",
                     customisations=["dry", "gravy"]),
    "ST13": MenuItem("ST13", "Paneer Manchurian",       8.99, "",                                                                                                "starters",
                     customisations=["dry", "gravy"]),
    "ST14": MenuItem("ST14", "Gobi Manchurian",         8.50, "",                                                                                                "starters",
                     customisations=["dry", "gravy"]),
    "ST15": MenuItem("ST15", "Mushroom Manchurian",     8.50, "",                                                                                                "starters",
                     customisations=["dry", "gravy"]),
    "ST16": MenuItem("ST16", "Veg Roll (2 pcs)",        4.99, "",                                                                                                "starters"),
    "ST17": MenuItem("ST17", "Veg Samosa (3 pcs)",      4.50, "",                                                                                                "starters"),
    "ST18": MenuItem("ST18", "Onion Pakoda",            4.50, "",                                                                                                "starters"),
    "ST19": MenuItem("ST19", "Vegetable Spring Roll (3 pcs)", 4.50, "",                                                                                          "starters"),
    "ST20": MenuItem("ST20", "Plain Papadum",           1.50, "",                                                                                                "starters"),
    "ST21": MenuItem("ST21", "Masala Papadum",          3.50, "",                                                                                                "starters"),
    "ST22": MenuItem("ST22", "Chilly Idly",             8.50, "",                                                                                                "starters"),
    "ST23": MenuItem("ST23", "Cocktail Idly",           7.50, "",                                                                                                "starters"),
    "ST24": MenuItem("ST24", "Mini Podi Idly",          6.99, "",                                                                                                "starters"),

    # ── Chaat Items ────────────────────────────────────────────────────────
    "CH01": MenuItem("CH01", "Samosa Chaat",            6.99, "",                                                                                                "chaat"),
    "CH02": MenuItem("CH02", "Panipuri",                5.99, "",                                                                                                "chaat"),
    "CH03": MenuItem("CH03", "Dahi Batata Puri",        5.99, "",                                                                                                "chaat"),
    "CH04": MenuItem("CH04", "Aloo Papdi Chaat",        6.99, "",                                                                                                "chaat"),

    # ── Vada ───────────────────────────────────────────────────────────────
    "VA01": MenuItem("VA01", "Medhu Vada (2 pcs)",      4.50, "",                                                                                                "vada"),
    "VA02": MenuItem("VA02", "Sambar Vada (2 pcs)",     5.99, "",                                                                                                "vada"),
    "VA03": MenuItem("VA03", "Rasa Vada (2 pcs)",       5.99, "",                                                                                                "vada"),
    "VA04": MenuItem("VA04", "Thayir Vada (2 pcs)",     5.99, "",                                                                                                "vada"),

    # ── Idly ───────────────────────────────────────────────────────────────
    "ID01": MenuItem("ID01", "Idly (3 pcs)",            5.50, "",                                                                                                "idly"),
    "ID02": MenuItem("ID02", "Idly (2 pcs) & Vada (1 pc)", 5.50, "",                                                                                            "idly"),
    "ID03": MenuItem("ID03", "Sambar Idly (2 pcs)",     5.99, "",                                                                                                "idly"),
    "ID04": MenuItem("ID04", "Mini Ghee Idly",          5.99, "",                                                                                                "idly"),
    "ID05": MenuItem("ID05", "Podi Idly",               6.50, "",                                                                                                "idly"),

    # ── South Indian Corner ────────────────────────────────────────────────
    "SI01": MenuItem("SI01", "Ghee Pongal",             7.50, "",                                                                                                "south indian corner"),
    "SI02": MenuItem("SI02", "Pongal & Vada",           7.99, "",                                                                                                "south indian corner"),
    "SI03": MenuItem("SI03", "Poori (2 pcs) Masala",    6.99, "",                                                                                                "south indian corner"),
    "SI04": MenuItem("SI04", "Chappathi (2 pcs) with Kurma", 6.99, "",                                                                                          "south indian corner"),
    "SI05": MenuItem("SI05", "Parotta (2 pcs) with Kurma",   7.99, "",                                                                                          "south indian corner"),
    "SI06": MenuItem("SI06", "Channa Bhatura",          7.99, "",                                                                                                "south indian corner"),
    "SI07": MenuItem("SI07", "Chilli Parotta",          8.99, "",                                                                                                "south indian corner"),
    "SI08": MenuItem("SI08", "Kothu Parotta",           8.99, "",                                                                                                "south indian corner"),

    # ── Dosas ──────────────────────────────────────────────────────────────
    "DO01": MenuItem("DO01", "Plain Dosa",              5.50, "",                                                                                                "dosas"),
    "DO02": MenuItem("DO02", "Masala Dosa",             6.99, "",                                                                                                "dosas"),
    "DO03": MenuItem("DO03", "Onion Dosa",              6.50, "",                                                                                                "dosas"),
    "DO04": MenuItem("DO04", "Onion Masala Dosa",       7.99, "",                                                                                                "dosas"),
    "DO05": MenuItem("DO05", "Ghee Roast",              7.99, "",                                                                                                "dosas"),
    "DO06": MenuItem("DO06", "Ghee Masala Roast",       8.99, "",                                                                                                "dosas"),
    "DO07": MenuItem("DO07", "Butter Dosa",             7.99, "",                                                                                                "dosas"),
    "DO08": MenuItem("DO08", "Butter Masala Dosa",      8.99, "",                                                                                                "dosas"),
    "DO09": MenuItem("DO09", "Paper Roast",             8.50, "",                                                                                                "dosas"),
    "DO10": MenuItem("DO10", "Paper Masala Roast",      9.99, "",                                                                                                "dosas"),
    "DO11": MenuItem("DO11", "Kal Dosa (2 pcs)",        7.99, "",                                                                                                "dosas"),
    "DO12": MenuItem("DO12", "Podi Dosa",               7.50, "",                                                                                                "dosas"),
    "DO13": MenuItem("DO13", "Podi Masala Dosa",        8.99, "",                                                                                                "dosas"),
    "DO14": MenuItem("DO14", "Kara Podi Dosa",          8.50, "",                                                                                                "dosas"),
    "DO15": MenuItem("DO15", "Kara Podi Masala Dosa",   9.99, "",                                                                                                "dosas"),
    "DO16": MenuItem("DO16", "Mysore Dosa",             7.50, "",                                                                                                "dosas"),
    "DO17": MenuItem("DO17", "Mysore Masala Dosa",      8.99, "",                                                                                                "dosas"),
    "DO18": MenuItem("DO18", "Paneer Masala Dosa",      9.99, "",                                                                                                "dosas"),
    "DO19": MenuItem("DO19", "Mushroom Masala Dosa",    9.99, "",                                                                                                "dosas"),
    "DO20": MenuItem("DO20", "Veg Masala Dosa",         9.99, "",                                                                                                "dosas"),
    "DO21": MenuItem("DO21", "VV Special Dosa",        10.99, "",                                                                                                "dosas"),
    "DO22": MenuItem("DO22", "Family Dosa",            16.99, "",                                                                                                "dosas"),

    # ── Rava Dosa ──────────────────────────────────────────────────────────
    "RD01": MenuItem("RD01", "Rava Dosa",               7.99, "",                                                                                                "rava dosa"),
    "RD02": MenuItem("RD02", "Rava Masala Dosa",        8.99, "",                                                                                                "rava dosa"),
    "RD03": MenuItem("RD03", "Onion Rava Dosa",         8.99, "",                                                                                                "rava dosa"),
    "RD04": MenuItem("RD04", "Onion Rava Masala Dosa",  9.99, "",                                                                                                "rava dosa"),

    # ── Uthappam ───────────────────────────────────────────────────────────
    "UT01": MenuItem("UT01", "Plain Uthappam",           6.99, "",                                                                                               "uthappam"),
    "UT02": MenuItem("UT02", "Onion Uthappam",           7.50, "",                                                                                               "uthappam"),
    "UT03": MenuItem("UT03", "Onion Chilli Uthappam",    7.99, "",                                                                                               "uthappam"),
    "UT04": MenuItem("UT04", "Onion Tomato Uthappam",    7.99, "",                                                                                               "uthappam"),
    "UT05": MenuItem("UT05", "Chilli Coriander Uthappam",7.99, "",                                                                                               "uthappam"),
    "UT06": MenuItem("UT06", "Onion Chilli Tomato Uthappam", 8.99, "",                                                                                           "uthappam"),
    "UT07": MenuItem("UT07", "Pizza Uthappam",           9.99, "",                                                                                               "uthappam"),
    "UT08": MenuItem("UT08", "Mini Uthappam",            9.99, "",                                                                                               "uthappam"),
    "UT09": MenuItem("UT09", "Mix Veg Uthappam",         8.99, "",                                                                                               "uthappam"),

    # ── Mini Tiffin ────────────────────────────────────────────────────────
    "MT01": MenuItem("MT01", "Mini Tiffin – Basic",      9.99, "",                                                                                               "mini tiffin"),
    "MT02": MenuItem("MT02", "Mini Tiffin – Classic",   10.99, "",                                                                                               "mini tiffin"),

    # ── Kids Choice ────────────────────────────────────────────────────────
    "KC01": MenuItem("KC01", "Kids Cone Dosa",           7.50, "",                                                                                               "kids choice"),
    "KC02": MenuItem("KC02", "Cheese Dosa",              7.99, "",                                                                                               "kids choice"),
    "KC03": MenuItem("KC03", "Chocolate Dosa",           7.99, "",                                                                                               "kids choice"),
    "KC04": MenuItem("KC04", "French Fries",             3.99, "",                                                                                               "kids choice"),

    # ── Meals ──────────────────────────────────────────────────────────────
    "ME01": MenuItem("ME01", "South Indian Meals",      10.99, "Eat In £10.99 / Takeaway £12.99. Full South Indian meal with rice, curries & accompaniments.",   "meals",
                     customisations=["eat in", "takeaway"]),
    "ME02": MenuItem("ME02", "North Indian Meals",      10.99, "Eat In £10.99 / Takeaway £12.99. Full North Indian meal with rice, curries & accompaniments.",   "meals",
                     customisations=["eat in", "takeaway"]),
    "ME03": MenuItem("ME03", "Mini Meals",               8.99, "Eat In £8.99 / Takeaway £9.99. Smaller meal with rice, curry & accompaniments.",                 "meals",
                     customisations=["eat in", "takeaway"]),

    # ── Variety Rice ───────────────────────────────────────────────────────
    "VR01": MenuItem("VR01", "Sambar Rice / Bisibelabath", 7.50, "",                                                                                             "variety rice"),
    "VR02": MenuItem("VR02", "Curd Rice / Bagalabath",  6.99, "",                                                                                                "variety rice"),
    "VR03": MenuItem("VR03", "Coconut Rice",            7.99, "",                                                                                                "variety rice"),
    "VR04": MenuItem("VR04", "Lemon Rice",              7.99, "",                                                                                                "variety rice"),
    "VR05": MenuItem("VR05", "Tomato Rice",             7.99, "",                                                                                                "variety rice"),
    "VR06": MenuItem("VR06", "Tamarind Rice",           7.99, "",                                                                                                "variety rice"),

    # ── Biryani ────────────────────────────────────────────────────────────
    "BI01": MenuItem("BI01", "Vegetable Dum Biryani",   7.99, "",                                                                                                "biryani"),
    "BI02": MenuItem("BI02", "Mushroom Biryani",        8.99, "",                                                                                                "biryani"),
    "BI03": MenuItem("BI03", "Paneer Biryani",          9.50, "",                                                                                                "biryani"),
    "BI04": MenuItem("BI04", "Chef's Special Biryani",  9.99, "",                                                                                                "biryani"),

    # ── Pulao Rice ─────────────────────────────────────────────────────────
    "PU01": MenuItem("PU01", "Veg Pulao",               6.99, "",                                                                                                "pulao rice"),
    "PU02": MenuItem("PU02", "Paneer Pulao",            8.99, "",                                                                                                "pulao rice"),
    "PU03": MenuItem("PU03", "Cashew Pulao",            8.99, "",                                                                                                "pulao rice"),
    "PU04": MenuItem("PU04", "Jeera Pulao",             6.99, "",                                                                                                "pulao rice"),
    "PU05": MenuItem("PU05", "Mushroom Pulao",          8.50, "",                                                                                                "pulao rice"),

    # ── Fried Rice ─────────────────────────────────────────────────────────
    "FR01": MenuItem("FR01", "Veg Fried Rice",          8.50, "",                                                                                                "fried rice"),
    "FR02": MenuItem("FR02", "Szechwan Fried Rice",     8.99, "",                                                                                                "fried rice"),
    "FR03": MenuItem("FR03", "Paneer Fried Rice",       9.50, "",                                                                                                "fried rice"),
    "FR04": MenuItem("FR04", "Chef's Special Fried Rice", 9.99, "",                                                                                              "fried rice"),
    "FR05": MenuItem("FR05", "Mushroom Fried Rice",     8.50, "",                                                                                                "fried rice"),

    # ── Noodles ────────────────────────────────────────────────────────────
    "NO01": MenuItem("NO01", "Veg Noodles",             7.99, "",                                                                                                "noodles"),
    "NO02": MenuItem("NO02", "Szechwan Noodles",        8.99, "",                                                                                                "noodles"),
    "NO03": MenuItem("NO03", "Mushroom Noodles",        8.50, "",                                                                                                "noodles"),

    # ── Curries ────────────────────────────────────────────────────────────
    "CU01": MenuItem("CU01", "Mushroom Chettinad",      9.99, "",                                                                                                "curries"),
    "CU02": MenuItem("CU02", "Bhindi Masala",           8.99, "",                                                                                                "curries"),
    "CU03": MenuItem("CU03", "Mixed Vegetable Curry",   8.99, "",                                                                                                "curries"),
    "CU04": MenuItem("CU04", "Baingan Masala",          8.99, "",                                                                                                "curries"),
    "CU05": MenuItem("CU05", "Malai Kofta",             8.99, "",                                                                                                "curries"),
    "CU06": MenuItem("CU06", "Paneer Chettinad",        9.99, "",                                                                                                "curries"),
    "CU07": MenuItem("CU07", "Kadai Paneer",            9.99, "",                                                                                                "curries"),
    "CU08": MenuItem("CU08", "Paneer Butter Masala",    9.50, "",                                                                                                "curries"),
    "CU09": MenuItem("CU09", "Paneer Tikka Masala",     9.99, "",                                                                                                "curries"),
    "CU10": MenuItem("CU10", "Paneer Shai Kurma",       9.99, "",                                                                                                "curries"),
    "CU11": MenuItem("CU11", "Palak Paneer",            9.50, "",                                                                                                "curries"),
    "CU12": MenuItem("CU12", "Paneer Burji",            9.99, "",                                                                                                "curries"),
    "CU13": MenuItem("CU13", "Paneer Jal Frieze",       9.99, "",                                                                                                "curries"),
    "CU14": MenuItem("CU14", "Mutter Paneer",           9.50, "",                                                                                                "curries"),
    "CU15": MenuItem("CU15", "Dhal Butter Fry",         7.50, "",                                                                                                "curries"),
    "CU16": MenuItem("CU16", "Dhal Makhani",            7.99, "",                                                                                                "curries"),
    "CU17": MenuItem("CU17", "Aloo Gobi Masala",        8.50, "",                                                                                                "curries"),
    "CU18": MenuItem("CU18", "Aloo Palak",              8.99, "",                                                                                                "curries"),
    "CU19": MenuItem("CU19", "Vegetable Kadai",         8.99, "",                                                                                                "curries"),
    "CU20": MenuItem("CU20", "Channa Masala",           7.50, "",                                                                                                "curries"),
    "CU21": MenuItem("CU21", "Vegetable Kurma",         7.50, "",                                                                                                "curries"),

    # ── Indian Breads ──────────────────────────────────────────────────────
    "BR01": MenuItem("BR01", "Plain Naan",              1.99, "",                                                                                                "indian breads"),
    "BR02": MenuItem("BR02", "Butter Naan",             2.75, "",                                                                                                "indian breads"),
    "BR03": MenuItem("BR03", "Garlic Naan",             2.99, "",                                                                                                "indian breads"),
    "BR04": MenuItem("BR04", "Tandoori Roti",           2.25, "",                                                                                                "indian breads"),
    "BR05": MenuItem("BR05", "Butter Roti",             2.75, "",                                                                                                "indian breads"),
    "BR06": MenuItem("BR06", "Aloo Kulcha",             3.50, "",                                                                                                "indian breads"),
    "BR07": MenuItem("BR07", "Paneer Kulcha",           3.99, "",                                                                                                "indian breads"),
    "BR08": MenuItem("BR08", "Chapathi",                1.99, "",                                                                                                "indian breads"),
    "BR09": MenuItem("BR09", "Parotta",                 2.50, "",                                                                                                "indian breads"),

    # ── Drinks ─────────────────────────────────────────────────────────────
    "DR01": MenuItem("DR01", "Lassi (Mango)",           4.99, "Mango lassi — glass.",                                                                            "drinks",
                     customisations=["mango", "sweet", "salt"]),
    "DR02": MenuItem("DR02", "Lassi (Jug)",            16.99, "Lassi jug.",                                                                                      "drinks",
                     customisations=["mango", "sweet", "salt"]),
    "DR03": MenuItem("DR03", "Strawberry Milkshake",    5.50, "",                                                                                                "drinks"),
    "DR04": MenuItem("DR04", "Chocolate Milkshake",     5.50, "",                                                                                                "drinks"),
    "DR05": MenuItem("DR05", "Vanilla Milkshake",       5.50, "",                                                                                                "drinks"),
    "DR06": MenuItem("DR06", "Mango Milkshake",         5.99, "",                                                                                                "drinks"),
    "DR07": MenuItem("DR07", "Ferrero Rocher Milkshake",5.99, "",                                                                                                "drinks"),
    "DR08": MenuItem("DR08", "Oreo Milkshake",          5.99, "",                                                                                                "drinks"),
    "DR09": MenuItem("DR09", "Apple Juice",             5.99, "Fresh juice.",                                                                                    "drinks"),
    "DR10": MenuItem("DR10", "ABC Juice",               6.50, "Fresh apple, beetroot & carrot juice.",                                                           "drinks"),
    "DR11": MenuItem("DR11", "Orange Juice",            6.50, "Fresh juice.",                                                                                    "drinks"),
    "DR12": MenuItem("DR12", "Carrot Juice",            6.50, "Fresh juice.",                                                                                    "drinks"),
    "DR13": MenuItem("DR13", "Watermelon Juice",        6.50, "Fresh juice.",                                                                                    "drinks"),
    "DR14": MenuItem("DR14", "Passion Fruit Juice",     6.50, "Fresh juice.",                                                                                    "drinks"),
    "DR15": MenuItem("DR15", "Lime Juice",              6.50, "Fresh juice.",                                                                                    "drinks"),

    # ── Desserts ───────────────────────────────────────────────────────────
    "DE01": MenuItem("DE01", "Falooda",                 6.50, "",                                                                                                "desserts"),
    "DE02": MenuItem("DE02", "Gulab Jamun",             3.99, "",                                                                                                "desserts"),
    "DE03": MenuItem("DE03", "Kesari",                  4.50, "",                                                                                                "desserts"),
    "DE04": MenuItem("DE04", "Milk Cake",               4.99, "",                                                                                                "desserts"),
    "DE05": MenuItem("DE05", "Payasam",                 4.50, "",                                                                                                "desserts"),
    "DE06": MenuItem("DE06", "Carrot Halwa",            4.99, "",                                                                                                "desserts"),
    "DE07": MenuItem("DE07", "Motichoor Laddu",         1.50, "",                                                                                                "desserts"),
    "DE08": MenuItem("DE08", "Kaju Sweet",              1.99, "",                                                                                                "desserts"),

    # ── Ice Cream ──────────────────────────────────────────────────────────
    "IC01": MenuItem("IC01", "Chocolate Ice Cream",     3.99, "",                                                                                                "ice cream"),
    "IC02": MenuItem("IC02", "Vanilla Ice Cream",       3.50, "",                                                                                                "ice cream"),
    "IC03": MenuItem("IC03", "Strawberry Ice Cream",    3.50, "",                                                                                                "ice cream"),
    "IC04": MenuItem("IC04", "Mango Ice Cream",         3.50, "",                                                                                                "ice cream"),

    # ── Kulfi ──────────────────────────────────────────────────────────────
    "KU01": MenuItem("KU01", "Malai Kulfi",             2.99, "",                                                                                                "kulfi"),
    "KU02": MenuItem("KU02", "Mango Kulfi",             2.99, "",                                                                                                "kulfi"),
    "KU03": MenuItem("KU03", "Pistachio Kulfi",         2.99, "",                                                                                                "kulfi"),

    # ── Beverages ──────────────────────────────────────────────────────────
    "BV01": MenuItem("BV01", "Rose Milk",               4.99, "",                                                                                                "beverages"),
    "BV02": MenuItem("BV02", "Butter Milk",             4.50, "",                                                                                                "beverages"),
    "BV03": MenuItem("BV03", "Soft Drinks",             2.50, "",                                                                                                "beverages"),
    "BV04": MenuItem("BV04", "Mineral Water (500ml)",   1.99, "",                                                                                                "beverages"),

    # ── Hot Beverages ──────────────────────────────────────────────────────
    "HB01": MenuItem("HB01", "Masala Tea",              2.50, "",                                                                                                "hot beverages"),
    "HB02": MenuItem("HB02", "Filter Coffee",           2.50, "",                                                                                                "hot beverages"),
    "HB03": MenuItem("HB03", "Hot Milk",                2.50, "",                                                                                                "hot beverages"),
    "HB04": MenuItem("HB04", "Hot Badam Milk",          3.99, "",                                                                                                "hot beverages"),

    # ── Extras ─────────────────────────────────────────────────────────────
    "EX01": MenuItem("EX01", "Sweet Beeda",             2.50, "",                                                                                                "extras"),
    "EX02": MenuItem("EX02", "Curd",                    2.99, "",                                                                                                "extras"),
    "EX03": MenuItem("EX03", "Raitha",                  2.99, "",                                                                                                "extras"),
    "EX04": MenuItem("EX04", "Green Salad",             3.99, "",                                                                                                "extras"),
}
