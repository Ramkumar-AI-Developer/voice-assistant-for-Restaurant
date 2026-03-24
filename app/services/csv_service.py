"""
CSV/Excel parser for menu uploads.
Parses uploaded files and upserts menu items into the database.
"""

import io
import logging
from typing import Optional

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.db_models import MenuItemDB, Category

logger = logging.getLogger(__name__)

# Expected columns
REQUIRED_COLUMNS = {"name", "price", "category"}
OPTIONAL_COLUMNS = {"description", "available", "customisations"}
ALL_COLUMNS = REQUIRED_COLUMNS | OPTIONAL_COLUMNS


def parse_menu_file(file_bytes: bytes, filename: str) -> list[dict]:
    """
    Parse a CSV or Excel file into a list of menu item dicts.

    Returns:
        List of dicts with keys: name, price, description, category, available, customisations
    """
    filename_lower = filename.lower()

    try:
        if filename_lower.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_bytes))
        elif filename_lower.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(file_bytes))
        else:
            raise ValueError(f"Unsupported file type: {filename}. Use .csv, .xlsx, or .xls")
    except Exception as exc:
        raise ValueError(f"Failed to parse file: {exc}")

    # Normalise column names
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Validate required columns
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    items = []
    for idx, row in df.iterrows():
        name = str(row.get("name", "")).strip()
        if not name:
            continue

        try:
            price = float(row.get("price", 0))
        except (ValueError, TypeError):
            logger.warning(f"Row {idx + 1}: Invalid price for '{name}', skipping")
            continue

        category = str(row.get("category", "uncategorized")).strip()
        description = str(row.get("description", "")).strip() if pd.notna(row.get("description")) else ""

        # Parse available column
        available_val = row.get("available", "yes")
        if pd.isna(available_val):
            available = True
        else:
            available = str(available_val).strip().lower() in ("yes", "true", "1", "y")

        # Parse customisations (comma-separated string → list)
        custom_val = row.get("customisations", "")
        if pd.isna(custom_val) or not str(custom_val).strip():
            customisations = []
        else:
            customisations = [c.strip() for c in str(custom_val).split(",") if c.strip()]

        items.append({
            "name": name,
            "price": price,
            "description": description,
            "category": category,
            "available": available,
            "customisations": customisations,
        })

    logger.info(f"Parsed {len(items)} menu items from '{filename}'")
    return items


async def import_menu_items(db: AsyncSession, items: list[dict]) -> dict:
    """
    Import parsed menu items into the database.
    Creates categories as needed. Updates existing items by name.

    Returns:
        {"created": int, "updated": int, "total": int}
    """
    created = 0
    updated = 0

    for item_data in items:
        # Get or create category
        cat_name = item_data["category"].lower()
        result = await db.execute(
            select(Category).where(func.lower(Category.name) == cat_name)
        )
        category = result.scalar_one_or_none()

        if not category:
            category = Category(name=item_data["category"].title())
            db.add(category)
            await db.flush()

        # Check if item already exists
        result = await db.execute(
            select(MenuItemDB).where(
                func.lower(MenuItemDB.name) == item_data["name"].lower()
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.price = item_data["price"]
            existing.description = item_data["description"]
            existing.category_id = category.id
            existing.available = item_data["available"]
            existing.customisations = item_data["customisations"]
            updated += 1
        else:
            new_item = MenuItemDB(
                name=item_data["name"],
                price=item_data["price"],
                description=item_data["description"],
                category_id=category.id,
                available=item_data["available"],
                customisations=item_data["customisations"],
            )
            db.add(new_item)
            created += 1

    await db.commit()
    logger.info(f"Menu import: {created} created, {updated} updated")
    return {"created": created, "updated": updated, "total": created + updated}


def generate_excel_template() -> bytes:
    """Generate a sample Excel template for menu upload."""
    data = {
        "Name": ["Garlic Bread", "Classic Burger", "Margherita Pizza"],
        "Price": [3.99, 12.99, 13.99],
        "Description": [
            "Toasted bread with garlic butter",
            "Beef patty, lettuce, tomato, pickles",
            "Tomato, fresh mozzarella, basil",
        ],
        "Category": ["Starters", "Mains", "Mains"],
        "Available": ["Yes", "Yes", "Yes"],
        "Customisations": [
            "",
            "no onion, extra cheese, gluten-free bun",
            "thin crust, gluten-free base, extra cheese",
        ],
    }
    df = pd.DataFrame(data)
    output = io.BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")
    output.seek(0)
    return output.getvalue()
