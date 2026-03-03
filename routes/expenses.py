from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from database import get_db
from auth import get_current_user, require_contractor
from models import ExpenseCreate, ExpenseUpdate

router = APIRouter(prefix="/api/expenses", tags=["Expenses"])


@router.post("")
async def create_expense(expense: ExpenseCreate, user=Depends(get_current_user)):
    db = get_db()
    # Verify site exists
    site = await db.sites.find_one({"_id": ObjectId(expense.site_id)})
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    expense_doc = {
        **expense.model_dump(),
        "created_by": str(user["_id"]),
    }
    result = await db.expenses.insert_one(expense_doc)
    expense_doc["id"] = str(result.inserted_id)
    expense_doc.pop("_id", None)
    return expense_doc


@router.get("")
async def get_expenses(site_id: str = None, user=Depends(get_current_user)):
    db = get_db()
    query = {}
    if site_id:
        query["site_id"] = site_id

    expenses = []
    async for exp in db.expenses.find(query).sort("date", -1):
        exp["id"] = str(exp.pop("_id"))
        expenses.append(exp)
    return expenses


@router.put("/{expense_id}")
async def update_expense(expense_id: str, update: ExpenseUpdate, user=Depends(get_current_user)):
    db = get_db()
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = await db.expenses.update_one({"_id": ObjectId(expense_id)}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Expense not found")

    expense = await db.expenses.find_one({"_id": ObjectId(expense_id)})
    expense["id"] = str(expense.pop("_id"))
    return expense


@router.delete("/{expense_id}")
async def delete_expense(expense_id: str, user=Depends(get_current_user)):
    db = get_db()
    result = await db.expenses.delete_one({"_id": ObjectId(expense_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Expense not found")
    return {"message": "Expense deleted"}
