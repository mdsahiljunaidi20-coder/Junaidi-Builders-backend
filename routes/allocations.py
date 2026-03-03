from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from database import get_db
from auth import get_current_user
from models import AllocationCreate

router = APIRouter(prefix="/api/allocations", tags=["Allocations"])

@router.post("")
async def create_allocation(alloc: AllocationCreate, user=Depends(get_current_user)):
    db = get_db()
    # Check if labour and site exist
    labour = await db.labours.find_one({"_id": ObjectId(alloc.labour_id)})
    if not labour:
        raise HTTPException(status_code=404, detail="Labour not found")
    
    site = await db.sites.find_one({"_id": ObjectId(alloc.site_id)})
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    # Prevent duplicate allocation for same labour on same date
    existing = await db.allocations.find_one({
        "labour_id": alloc.labour_id,
        "date": alloc.date
    })
    
    if existing:
        # Update existing allocation to new site
        await db.allocations.update_one(
            {"_id": existing["_id"]},
            {"$set": {"site_id": alloc.site_id, "allocated_by": str(user["_id"])}}
        )
        return {"message": "Allocation updated", "id": str(existing["_id"])}

    doc = alloc.model_dump()
    doc["allocated_by"] = str(user["_id"])
    result = await db.allocations.insert_one(doc)
    return {"id": str(result.inserted_id), **doc}

@router.get("")
async def get_allocations(date: str = None, site_id: str = None, labour_id: str = None, user=Depends(get_current_user)):
    db = get_db()
    query = {}
    if date: query["date"] = date
    if site_id: query["site_id"] = site_id
    if labour_id: query["labour_id"] = labour_id
    
    allocs = []
    async for a in db.allocations.find(query):
        a["id"] = str(a.pop("_id"))
        allocs.append(a)
    return allocs

@router.delete("/{alloc_id}")
async def delete_allocation(alloc_id: str, user=Depends(get_current_user)):
    db = get_db()
    result = await db.allocations.delete_one({"_id": ObjectId(alloc_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Allocation not found")
    return {"message": "Allocation deleted"}
