"""
Menu management API routes.
  GET    /api/menu            — list all menu items
  POST   /api/menu            — add a menu item
  PUT    /api/menu/{id}       — update a menu item
  DELETE /api/menu/{id}       — delete a menu item
  POST   /api/menu/upload     — bulk upload from CSV/Excel
  GET    /api/menu/template   — download Excel template
  GET    /api/menu/categories — list categories
"""

import logging
from typing import Optional
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
import io

from app.database import get_db
from app.models.db_models import MenuItemDB, Category, User
from app.models.menu import load_menu_from_db
from app.services.auth_service import get_current_user
from app.services.csv_service import parse_menu_file, import_menu_items, generate_excel_template

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class MenuItemCreate(BaseModel):
    name: str
    price: float
    description: str = ""
    category: str = "uncategorized"
    available: bool = True
    customisations: list[str] = []

class MenuItemUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    description: Optional[str] = None
    category: Optional[str] = None
    available: Optional[bool] = None
    customisations: Optional[list[str]] = None

class BulkDeleteRequest(BaseModel):
    ids: list[int]

class MenuItemResponse(BaseModel):
    id: int
    name: str
    price: float
    description: str
    category_name: str
    available: bool
    customisations: list

    class Config:
        from_attributes = True


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/")
async def list_menu_items(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all menu items with categories."""
    result = await db.execute(
        select(MenuItemDB)
        .options(selectinload(MenuItemDB.category))
        .order_by(MenuItemDB.category_id, MenuItemDB.name)
    )
    items = result.scalars().all()

    return [
        {
            "id": item.id,
            "name": item.name,
            "price": item.price,
            "description": item.description,
            "category": item.category.name if item.category else "Uncategorized",
            "available": item.available,
            "customisations": item.customisations or [],
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }
        for item in items
    ]


@router.post("/")
async def create_menu_item(
    body: MenuItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a new menu item."""
    # Get or create category
    result = await db.execute(
        select(Category).where(func.lower(Category.name) == body.category.lower())
    )
    category = result.scalar_one_or_none()
    if not category:
        category = Category(name=body.category.title())
        db.add(category)
        await db.flush()

    item = MenuItemDB(
        name=body.name,
        price=body.price,
        description=body.description,
        category_id=category.id,
        available=body.available,
        customisations=body.customisations,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    # Reload menu cache
    await load_menu_from_db(db)

    return {"id": item.id, "message": f"Menu item '{item.name}' created"}


@router.put("/{item_id}")
async def update_menu_item(
    item_id: int,
    body: MenuItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a menu item."""
    result = await db.execute(select(MenuItemDB).where(MenuItemDB.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")

    if body.name is not None:
        item.name = body.name
    if body.price is not None:
        item.price = body.price
    if body.description is not None:
        item.description = body.description
    if body.available is not None:
        item.available = body.available
    if body.customisations is not None:
        item.customisations = body.customisations

    if body.category is not None:
        result = await db.execute(
            select(Category).where(func.lower(Category.name) == body.category.lower())
        )
        cat = result.scalar_one_or_none()
        if not cat:
            cat = Category(name=body.category.title())
            db.add(cat)
            await db.flush()
        item.category_id = cat.id

    await db.commit()

    # Reload menu cache
    await load_menu_from_db(db)

    return {"message": f"Menu item '{item.name}' updated"}


@router.delete("/{item_id}")
async def delete_menu_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a menu item."""
    result = await db.execute(select(MenuItemDB).where(MenuItemDB.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")

    await db.delete(item)
    await db.commit()

    # Reload menu cache
    await load_menu_from_db(db)

    return {"message": f"Menu item '{item.name}' deleted"}


@router.post("/bulk-delete")
async def bulk_delete_menu_items(
    body: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete multiple menu items."""
    if not body.ids:
        return {"message": "No items to delete", "deleted": 0}

    # Delete items that match the IDs
    from sqlalchemy import delete
    result = await db.execute(
        delete(MenuItemDB).where(MenuItemDB.id.in_(body.ids))
    )
    deleted_count = result.rowcount
    await db.commit()

    # Reload menu cache
    await load_menu_from_db(db)

    return {"message": f"Deleted {deleted_count} menu items", "deleted": deleted_count}


@router.post("/upload")
async def upload_menu(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a CSV or Excel file to bulk-import menu items."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    allowed_types = (".csv", ".xlsx", ".xls")
    if not any(file.filename.lower().endswith(ext) for ext in allowed_types):
        raise HTTPException(status_code=400, detail="File must be .csv, .xlsx, or .xls")

    file_bytes = await file.read()
    if len(file_bytes) > 5 * 1024 * 1024:  # 5MB limit
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")

    try:
        items = parse_menu_file(file_bytes, file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not items:
        raise HTTPException(status_code=400, detail="No valid menu items found in file")

    result = await import_menu_items(db, items)

    # Reload menu cache
    await load_menu_from_db(db)

    return result


@router.get("/template")
async def download_template(
    current_user: User = Depends(get_current_user),
):
    """Download the Excel template for menu upload."""
    template_bytes = generate_excel_template()
    return StreamingResponse(
        io.BytesIO(template_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=menu_template.xlsx"},
    )


@router.get("/categories")
async def list_categories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all menu categories."""
    result = await db.execute(select(Category).order_by(Category.display_order, Category.name))
    categories = result.scalars().all()
    return [{"id": c.id, "name": c.name, "display_order": c.display_order} for c in categories]
