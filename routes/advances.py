from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from database import get_db
from auth import get_current_user, require_financial_access
from models import AdvanceCreate, AdvanceUpdate

router = APIRouter(prefix="/api/advances", tags=["Advances"])


@router.post("")
async def create_advance(advance: AdvanceCreate, user=Depends(require_financial_access)):
    db = get_db()
    # Verify labour exists
    labour = await db.labours.find_one({"_id": ObjectId(advance.labour_id)})
    if not labour:
        raise HTTPException(status_code=404, detail="Labour not found")

    advance_doc = {
        **advance.model_dump(),
        "created_by": str(user["_id"]),
        "created_by_name": user.get("name", "Unknown"),
        "created_by_role": user.get("role", "Unknown"),
    }
    result = await db.advances.insert_one(advance_doc)
    advance_doc["id"] = str(result.inserted_id)
    advance_doc.pop("_id", None)
    return advance_doc


@router.get("")
async def get_advances(labour_id: str = None, user=Depends(get_current_user)):
    db = get_db()
    query = {}
    if labour_id:
        query["labour_id"] = labour_id

    advances = []
    async for adv in db.advances.find(query).sort("date", -1):
        adv["id"] = str(adv.pop("_id"))
        # Get labour name
        try:
            labour = await db.labours.find_one({"_id": ObjectId(adv["labour_id"])})
            adv["labour_name"] = labour["name"] if labour else "Unknown"
        except Exception:
            adv["labour_name"] = "Unknown"
        advances.append(adv)
    return advances


@router.put("/{advance_id}")
async def update_advance(advance_id: str, update: AdvanceUpdate, user=Depends(require_financial_access)):
    db = get_db()
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = await db.advances.update_one({"_id": ObjectId(advance_id)}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Advance not found")

    advance = await db.advances.find_one({"_id": ObjectId(advance_id)})
    advance["id"] = str(advance.pop("_id"))
    return advance


@router.delete("/{advance_id}")
async def delete_advance(advance_id: str, user=Depends(require_financial_access)):
    db = get_db()
    result = await db.advances.delete_one({"_id": ObjectId(advance_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Advance not found")
    return {"message": "Advance deleted"}
