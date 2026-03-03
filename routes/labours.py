from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from database import get_db
from auth import get_current_user, require_contractor, require_worker_management_access
from models import LabourCreate, LabourUpdate

router = APIRouter(prefix="/api/labours", tags=["Labours"])


@router.get("/unassigned")
async def get_unassigned_labours(date: str, user=Depends(get_current_user)):
    """Fetch labours not allocated to ANY site on a specific date."""
    db = get_db()
    
    # 1. Get all allocated labour IDs for this date
    allocated = await db.allocations.distinct("labour_id", {"date": date})
    
    # 2. Find labours NOT in that list
    query = {"_id": {"$nin": [ObjectId(lid) for lid in allocated]}}
    
    labours = []
    async for labour in db.labours.find(query).sort("name", 1):
        labour["id"] = str(labour.pop("_id"))
        labours.append(labour)
    return labours


@router.post("")
async def create_labour(labour: LabourCreate, user=Depends(require_worker_management_access)):
    db = get_db()
    
    # Global creation: verification of site_id is optional as it's meant to be global/pool now
    if labour.site_id:
        site = await db.sites.find_one({"_id": ObjectId(labour.site_id)})
        if not site:
            raise HTTPException(status_code=404, detail="Site not found")

    doc = labour.model_dump()
    doc["created_by"] = str(user["_id"])
    doc["total_earned"] = 0
    doc["total_advances"] = 0
    doc["payable"] = 0
    
    result = await db.labours.insert_one(doc)
    labour_id = str(result.inserted_id)

    # If joining fee is provided, create an initial advance record
    if labour.joining_fee > 0:
        from datetime import datetime
        advance_doc = {
            "labour_id": labour_id,
            "amount": labour.joining_fee,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "note": "Joining Fee (Fees for joining)",
            "is_joining_fee": True,
            "created_by": str(user["_id"]),
            "created_by_name": user.get("name", "Unknown"),
            "created_by_role": user.get("role", "Unknown"),
        }
        await db.advances.insert_one(advance_doc)
        # Note: total_advances will be updated by background task or on next fetch
    
    return {"id": labour_id, **doc}


@router.get("")
async def get_labours(site_id: str = None, user=Depends(get_current_user)):
    db = get_db()
    query = {}
    if site_id == "unassigned":
        query["site_id"] = {"$in": [None, ""]}
    elif site_id:
        query["site_id"] = site_id
    
    # Fetch all labours first
    labours_cursor = db.labours.find(query).sort("name", 1)
    labours_list = await labours_cursor.to_list(length=None) # Convert cursor to list

    # Calculate stats for each labour
    # Note: In a real app, use aggregation for efficiency
    for labour in labours_list:
        labour["id"] = str(labour.pop("_id"))
        
        # Earned: From attendance
        attendance = await db.attendance.find({"labour_id": labour["id"]}).to_list(None)
        earned = sum([
            (labour["daily_wage"] if a["status"] == "present" else labour["daily_wage"] * 0.5 if a["status"] == "half_day" else 0)
            for a in attendance
        ])
        
        # Advances: Exclude joining fee from weekly payable
        advances = await db.advances.find({"labour_id": labour["id"]}).to_list(None)
        total_advances = sum([a["amount"] for a in advances])
        joining_fee_sum = sum([a["amount"] for a in advances if a.get("is_joining_fee")])
        
        labour["total_earned"] = earned
        labour["total_advances"] = total_advances
        # Weekly Payable = Earned - (Advances that are NOT joining fees)
        labour["payable"] = earned - (total_advances - joining_fee_sum)
        labour["joining_fee"] = joining_fee_sum or labour.get("joining_fee", 0)
    
    return labours_list


@router.get("/{labour_id}")
async def get_labour(labour_id: str, user=Depends(get_current_user)):
    db = get_db()
    labour = await db.labours.find_one({"_id": ObjectId(labour_id)})
    if not labour:
        raise HTTPException(status_code=404, detail="Labour not found")
    labour["id"] = str(labour.pop("_id"))

    # Calculate totals
    attendance = await db.attendance.find({"labour_id": labour["id"]}).to_list(None)
    total_earned = sum([
        (labour["daily_wage"] if a["status"] == "present" else labour["daily_wage"] * 0.5 if a["status"] == "half_day" else 0)
        for a in attendance
    ])

    advances = await db.advances.find({"labour_id": labour["id"]}).to_list(None)
    total_advances = sum([a["amount"] for a in advances])
    joining_fee_sum = sum([a["amount"] for a in advances if a.get("is_joining_fee")])

    labour["total_earned"] = total_earned
    labour["total_advances"] = total_advances
    # Weekly Payable = Earned - (Advances - Joining Fee)
    labour["payable"] = total_earned - (total_advances - joining_fee_sum)
    labour["joining_fee"] = joining_fee_sum or labour.get("joining_fee", 0)

    return labour


@router.put("/{labour_id}")
async def update_labour(labour_id: str, update: LabourUpdate, user=Depends(get_current_user)):
    db = get_db()
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}

    # Contractors and Subcontractors can update wages
    if "daily_wage" in update_data and user.get("role") not in ("admin", "contractor", "subcontractor"):
        raise HTTPException(status_code=403, detail="You do not have permission to update wages")

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = await db.labours.update_one({"_id": ObjectId(labour_id)}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Labour not found")

    labour = await db.labours.find_one({"_id": ObjectId(labour_id)})
    labour["id"] = str(labour.pop("_id"))
    return labour


@router.delete("/{labour_id}")
async def delete_labour(labour_id: str, user=Depends(require_worker_management_access)):
    db = get_db()
    result = await db.labours.delete_one({"_id": ObjectId(labour_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Labour not found")
    # Clean up related data
    await db.attendance.delete_many({"labour_id": labour_id})
    await db.advances.delete_many({"labour_id": labour_id})
    return {"message": "Labour and related data deleted"}
