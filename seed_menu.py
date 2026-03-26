"""
seed_menu.py
────────────
One-shot script to clear the existing menu categories & items from
PostgreSQL and populate them with the new restaurant menu.

Run from the project root:
    python seed_menu.py

Requires a valid DATABASE_URL in .env (or environment).
"""

import asyncio
import logging

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.db_models import Base, Category, MenuItemDB

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


# ── Full menu definition ──────────────────────────────────────────────────────
# Format: (category_name, display_order, [(item_name, price, description, customisations)])

MENU_DATA = [
    ("Soup Bowl", 1, [
        ("Hot & Sour Veg Soup",  4.99, "Hot and spicy thick soup made with sautéed fresh vegetables and soy sauce.", []),
        ("Sweet Corn Soup",      4.99, "Lightly spiced corn soup flavoured with pepper.", []),
        ("Mushroom Soup",        4.99, "Lightly spiced minced mushroom soup garnished with cream.", []),
        ("Pepper Rasam Soup",    4.50, "Traditional South Indian sour & spicy soup with diced fresh tomatoes & tamarind juice.", []),
    ]),
    ("Starters", 2, [
        ("Gobi 65",                        8.50, "Battered cauliflower florets deep fried with spices and chilli paste.", []),
        ("Paneer 65",                      8.99, "Batter deep fried Indian cottage cheese chunks flavoured with spicy paste.", []),
        ("Mogo 65",                        7.99, "Casava marinated in Indian & Chinese spices, dipped in gram flour batter & deep fried.", []),
        ("Mushroom 65",                    7.99, "Battered fried mushroom sautéed with spices & chilli paste.", []),
        ("Paneer Tikka",                   9.99, "Chunks of cottage cheese marinated in special herbs & spices & grilled in a clay oven.", []),
        ("Paneer Pepper Fry",              9.50, "Chunks of cottage cheese batter fried & sautéed with flavoured spices & pepper.", []),
        ("Mushroom Pepper Fry",            8.99, "Mushroom batter fried & sautéed with flavoured spices & pepper.", []),
        ("Chilly Paneer",                  8.99, "Cottage cheese diced marinated in an authentic South Indian chilli mix & pan cooked.", ["dry", "gravy"]),
        ("Chilly Baby Corn",               8.99, "Baby corn diced marinated in an authentic South Indian chilli mix & pan cooked.", ["dry", "gravy"]),
        ("Chilly Mogo",                    8.75, "Steamed tapioca pieces deep fried and tossed in chef's special chilli sauce & spices.", ["dry", "gravy"]),
        ("Chilly Gobi",                    8.50, "Steamed cauliflower pieces deep fried and tossed in chef's special chilli sauce & spices.", ["dry", "gravy"]),
        ("Veg Manchurian",                 8.99, "Minced vegetables deep fried in balls sautéed with onion & garlic in Manchurian sauce.", ["dry", "gravy"]),
        ("Paneer Manchurian",              8.99, "", ["dry", "gravy"]),
        ("Gobi Manchurian",                8.50, "", ["dry", "gravy"]),
        ("Mushroom Manchurian",            8.50, "", ["dry", "gravy"]),
        ("Veg Roll (2 pcs)",               4.99, "", []),
        ("Veg Samosa (3 pcs)",             4.50, "", []),
        ("Onion Pakoda",                   4.50, "", []),
        ("Vegetable Spring Roll (3 pcs)",  4.50, "", []),
        ("Plain Papadum",                  1.50, "", []),
        ("Masala Papadum",                 3.50, "", []),
        ("Chilly Idly",                    8.50, "", []),
        ("Cocktail Idly",                  7.50, "", []),
        ("Mini Podi Idly",                 6.99, "", []),
    ]),
    ("Chaat", 3, [
        ("Samosa Chaat",    6.99, "", []),
        ("Panipuri",        5.99, "", []),
        ("Dahi Batata Puri",5.99, "", []),
        ("Aloo Papdi Chaat",6.99, "", []),
    ]),
    ("Vada", 4, [
        ("Medhu Vada (2 pcs)", 4.50, "", []),
        ("Sambar Vada (2 pcs)",5.99, "", []),
        ("Rasa Vada (2 pcs)",  5.99, "", []),
        ("Thayir Vada (2 pcs)",5.99, "", []),
    ]),
    ("Idly", 5, [
        ("Idly (3 pcs)",           5.50, "", []),
        ("Idly (2 pcs) & Vada (1 pc)", 5.50, "", []),
        ("Sambar Idly (2 pcs)",    5.99, "", []),
        ("Mini Ghee Idly",         5.99, "", []),
        ("Podi Idly",              6.50, "", []),
    ]),
    ("South Indian Corner", 6, [
        ("Ghee Pongal",                   7.50, "", []),
        ("Pongal & Vada",                 7.99, "", []),
        ("Poori (2 pcs) Masala",          6.99, "", []),
        ("Chappathi (2 pcs) with Kurma",  6.99, "", []),
        ("Parotta (2 pcs) with Kurma",    7.99, "", []),
        ("Channa Bhatura",                7.99, "", []),
        ("Chilli Parotta",                8.99, "", []),
        ("Kothu Parotta",                 8.99, "", []),
    ]),
    ("Dosas", 7, [
        ("Plain Dosa",           5.50, "", []),
        ("Masala Dosa",          6.99, "", []),
        ("Onion Dosa",           6.50, "", []),
        ("Onion Masala Dosa",    7.99, "", []),
        ("Ghee Roast",           7.99, "", []),
        ("Ghee Masala Roast",    8.99, "", []),
        ("Butter Dosa",          7.99, "", []),
        ("Butter Masala Dosa",   8.99, "", []),
        ("Paper Roast",          8.50, "", []),
        ("Paper Masala Roast",   9.99, "", []),
        ("Kal Dosa (2 pcs)",     7.99, "", []),
        ("Podi Dosa",            7.50, "", []),
        ("Podi Masala Dosa",     8.99, "", []),
        ("Kara Podi Dosa",       8.50, "", []),
        ("Kara Podi Masala Dosa",9.99, "", []),
        ("Mysore Dosa",          7.50, "", []),
        ("Mysore Masala Dosa",   8.99, "", []),
        ("Paneer Masala Dosa",   9.99, "", []),
        ("Mushroom Masala Dosa", 9.99, "", []),
        ("Veg Masala Dosa",      9.99, "", []),
        ("VV Special Dosa",     10.99, "", []),
        ("Family Dosa",         16.99, "", []),
    ]),
    ("Rava Dosa", 8, [
        ("Rava Dosa",              7.99, "", []),
        ("Rava Masala Dosa",       8.99, "", []),
        ("Onion Rava Dosa",        8.99, "", []),
        ("Onion Rava Masala Dosa", 9.99, "", []),
    ]),
    ("Uthappam", 9, [
        ("Plain Uthappam",              6.99, "", []),
        ("Onion Uthappam",              7.50, "", []),
        ("Onion Chilli Uthappam",       7.99, "", []),
        ("Onion Tomato Uthappam",       7.99, "", []),
        ("Chilli Coriander Uthappam",   7.99, "", []),
        ("Onion Chilli Tomato Uthappam",8.99, "", []),
        ("Pizza Uthappam",              9.99, "", []),
        ("Mini Uthappam",               9.99, "", []),
        ("Mix Veg Uthappam",            8.99, "", []),
    ]),
    ("Mini Tiffin", 10, [
        ("Mini Tiffin \u2013 Basic",   9.99, "", []),
        ("Mini Tiffin \u2013 Classic",10.99, "", []),
    ]),
    ("Kids Choice", 11, [
        ("Kids Cone Dosa",  7.50, "", []),
        ("Cheese Dosa",     7.99, "", []),
        ("Chocolate Dosa",  7.99, "", []),
        ("French Fries",    3.99, "", []),
    ]),
    ("Meals", 12, [
        ("South Indian Meals", 10.99, "Eat In \u00a310.99 / Takeaway \u00a312.99. Full South Indian meal with rice, curries & accompaniments.", ["eat in", "takeaway"]),
        ("North Indian Meals", 10.99, "Eat In \u00a310.99 / Takeaway \u00a312.99. Full North Indian meal with rice, curries & accompaniments.", ["eat in", "takeaway"]),
        ("Mini Meals",          8.99, "Eat In \u00a38.99 / Takeaway \u00a39.99. Smaller meal with rice, curry & accompaniments.", ["eat in", "takeaway"]),
    ]),
    ("Variety Rice", 13, [
        ("Sambar Rice / Bisibelabath", 7.50, "", []),
        ("Curd Rice / Bagalabath",     6.99, "", []),
        ("Coconut Rice",               7.99, "", []),
        ("Lemon Rice",                 7.99, "", []),
        ("Tomato Rice",                7.99, "", []),
        ("Tamarind Rice",              7.99, "", []),
    ]),
    ("Biryani", 14, [
        ("Vegetable Dum Biryani",  7.99, "", []),
        ("Mushroom Biryani",       8.99, "", []),
        ("Paneer Biryani",         9.50, "", []),
        ("Chef's Special Biryani", 9.99, "", []),
    ]),
    ("Pulao Rice", 15, [
        ("Veg Pulao",    6.99, "", []),
        ("Paneer Pulao", 8.99, "", []),
        ("Cashew Pulao", 8.99, "", []),
        ("Jeera Pulao",  6.99, "", []),
        ("Mushroom Pulao",8.50, "", []),
    ]),
    ("Fried Rice", 16, [
        ("Veg Fried Rice",          8.50, "", []),
        ("Szechwan Fried Rice",     8.99, "", []),
        ("Paneer Fried Rice",       9.50, "", []),
        ("Chef's Special Fried Rice",9.99,"", []),
        ("Mushroom Fried Rice",     8.50, "", []),
    ]),
    ("Noodles", 17, [
        ("Veg Noodles",     7.99, "", []),
        ("Szechwan Noodles",8.99, "", []),
        ("Mushroom Noodles",8.50, "", []),
    ]),
    ("Curries", 18, [
        ("Mushroom Chettinad",    9.99, "", []),
        ("Bhindi Masala",         8.99, "", []),
        ("Mixed Vegetable Curry", 8.99, "", []),
        ("Baingan Masala",        8.99, "", []),
        ("Malai Kofta",           8.99, "", []),
        ("Paneer Chettinad",      9.99, "", []),
        ("Kadai Paneer",          9.99, "", []),
        ("Paneer Butter Masala",  9.50, "", []),
        ("Paneer Tikka Masala",   9.99, "", []),
        ("Paneer Shai Kurma",     9.99, "", []),
        ("Palak Paneer",          9.50, "", []),
        ("Paneer Burji",          9.99, "", []),
        ("Paneer Jal Frieze",     9.99, "", []),
        ("Mutter Paneer",         9.50, "", []),
        ("Dhal Butter Fry",       7.50, "", []),
        ("Dhal Makhani",          7.99, "", []),
        ("Aloo Gobi Masala",      8.50, "", []),
        ("Aloo Palak",            8.99, "", []),
        ("Vegetable Kadai",       8.99, "", []),
        ("Channa Masala",         7.50, "", []),
        ("Vegetable Kurma",       7.50, "", []),
    ]),
    ("Indian Breads", 19, [
        ("Plain Naan",    1.99, "", []),
        ("Butter Naan",   2.75, "", []),
        ("Garlic Naan",   2.99, "", []),
        ("Tandoori Roti", 2.25, "", []),
        ("Butter Roti",   2.75, "", []),
        ("Aloo Kulcha",   3.50, "", []),
        ("Paneer Kulcha", 3.99, "", []),
        ("Chapathi",      1.99, "", []),
        ("Parotta",       2.50, "", []),
    ]),
    ("Drinks", 20, [
        ("Lassi (Mango)",            4.99, "Mango / Sweet / Salt — glass.",   ["mango", "sweet", "salt"]),
        ("Lassi (Jug)",             16.99, "Mango / Sweet / Salt — jug.",     ["mango", "sweet", "salt"]),
        ("Strawberry Milkshake",     5.50, "", []),
        ("Chocolate Milkshake",      5.50, "", []),
        ("Vanilla Milkshake",        5.50, "", []),
        ("Mango Milkshake",          5.99, "", []),
        ("Ferrero Rocher Milkshake", 5.99, "", []),
        ("Oreo Milkshake",           5.99, "", []),
        ("Apple Juice",              5.99, "Fresh juice.", []),
        ("ABC Juice",                6.50, "Fresh apple, beetroot & carrot juice.", []),
        ("Orange Juice",             6.50, "Fresh juice.", []),
        ("Carrot Juice",             6.50, "Fresh juice.", []),
        ("Watermelon Juice",         6.50, "Fresh juice.", []),
        ("Passion Fruit Juice",      6.50, "Fresh juice.", []),
        ("Lime Juice",               6.50, "Fresh juice.", []),
    ]),
    ("Desserts", 21, [
        ("Falooda",         6.50, "", []),
        ("Gulab Jamun",     3.99, "", []),
        ("Kesari",          4.50, "", []),
        ("Milk Cake",       4.99, "", []),
        ("Payasam",         4.50, "", []),
        ("Carrot Halwa",    4.99, "", []),
        ("Motichoor Laddu", 1.50, "", []),
        ("Kaju Sweet",      1.99, "", []),
    ]),
    ("Ice Cream", 22, [
        ("Chocolate Ice Cream", 3.99, "", []),
        ("Vanilla Ice Cream",   3.50, "", []),
        ("Strawberry Ice Cream",3.50, "", []),
        ("Mango Ice Cream",     3.50, "", []),
    ]),
    ("Kulfi", 23, [
        ("Malai Kulfi",    2.99, "", []),
        ("Mango Kulfi",    2.99, "", []),
        ("Pistachio Kulfi",2.99, "", []),
    ]),
    ("Beverages", 24, [
        ("Rose Milk",           4.99, "", []),
        ("Butter Milk",         4.50, "", []),
        ("Soft Drinks",         2.50, "", []),
        ("Mineral Water (500ml)",1.99,"", []),
    ]),
    ("Hot Beverages", 25, [
        ("Masala Tea",     2.50, "", []),
        ("Filter Coffee",  2.50, "", []),
        ("Hot Milk",       2.50, "", []),
        ("Hot Badam Milk", 3.99, "", []),
    ]),
    ("Extras", 26, [
        ("Sweet Beeda", 2.50, "", []),
        ("Curd",        2.99, "", []),
        ("Raitha",      2.99, "", []),
        ("Green Salad", 3.99, "", []),
    ]),
]


async def seed():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        async with session.begin():
            # 1. Clear existing data (items first due to FK)
            logger.info("Clearing existing menu_items …")
            await session.execute(delete(MenuItemDB))
            logger.info("Clearing existing categories …")
            await session.execute(delete(Category))

        async with session.begin():
            # 2. Insert new categories + items
            total_items = 0
            for cat_name, display_order, items in MENU_DATA:
                cat = Category(name=cat_name, display_order=display_order)
                session.add(cat)
                await session.flush()  # get cat.id

                for name, price, description, customisations in items:
                    item = MenuItemDB(
                        name=name,
                        price=price,
                        description=description,
                        category_id=cat.id,
                        available=True,
                        customisations=customisations,
                    )
                    session.add(item)
                    total_items += 1

            logger.info(f"Inserted {len(MENU_DATA)} categories and {total_items} items.")

    await engine.dispose()
    logger.info("✅ Menu seeding complete.")


if __name__ == "__main__":
    asyncio.run(seed())
