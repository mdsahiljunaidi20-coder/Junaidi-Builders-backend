from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from database import get_db
from auth import get_current_user
from models import AttendanceCreate, AttendanceBulkCreate

router = APIRouter(prefix="/api/attendance", tags=["Attendance"])


@router.post("")
async def mark_attendance(att: AttendanceCreate, user=Depends(get_current_user)):
    """Mark attendance for a single labour with WAGE SNAPSHOTTING."""
    db = get_db()

    # Get labour to snapshot their current wage
    labour = await db.labours.find_one({"_id": ObjectId(att.labour_id)})
    if not labour:
        raise HTTPException(status_code=404, detail="Labour not found")

    # Calculate wage earned based on status
    daily_wage = labour["daily_wage"]
    if att.status == "present":
        wage_earned = daily_wage
    elif att.status == "half_day":
        wage_earned = daily_wage / 2
    else:  # absent
        wage_earned = 0

    # Check for duplicate (same labour, same date)
    existing = await db.attendance.find_one({
        "labour_id": att.labour_id,
        "date": att.date,
    })
    if existing:
        # Update existing record
        await db.attendance.update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "status": att.status,
                "wage_snapshot": daily_wage,  # CRITICAL: Snapshot current wage
                "wage_earned": wage_earned,
                "marked_by": str(user["_id"]),
            }}
        )
        updated = await db.attendance.find_one({"_id": existing["_id"]})
        updated["id"] = str(updated.pop("_id"))
        return updated

    # Create new attendance record
    att_doc = {
        "labour_id": att.labour_id,
        "site_id": att.site_id,
        "date": att.date,
        "status": att.status,
        "wage_snapshot": daily_wage,  # CRITICAL: Snapshot current wage
        "wage_earned": wage_earned,
        "marked_by": str(user["_id"]),
    }
    result = await db.attendance.insert_one(att_doc)
    att_doc["id"] = str(result.inserted_id)
    att_doc.pop("_id", None)
    return att_doc


@router.post("/bulk")
async def mark_bulk_attendance(bulk: AttendanceBulkCreate, user=Depends(get_current_user)):
    """Mark attendance for multiple labours at once."""
    db = get_db()
    results = []
    for record in bulk.records:
        labour_id = record.get("labour_id")
        status = record.get("status", "present")

        labour = await db.labours.find_one({"_id": ObjectId(labour_id)})
        if not labour:
            continue

        daily_wage = labour["daily_wage"]
        if status == "present":
            wage_earned = daily_wage
        elif status == "half_day":
            wage_earned = daily_wage / 2
        else:
            wage_earned = 0

        # Upsert attendance
        existing = await db.attendance.find_one({
            "labour_id": labour_id,
            "date": bulk.date,
        })
        if existing:
            await db.attendance.update_one(
                {"_id": existing["_id"]},
                {"$set": {
                    "status": status,
                    "site_id": bulk.site_id,
                    "wage_snapshot": daily_wage,
                    "wage_earned": wage_earned,
                    "marked_by": str(user["_id"]),
                }}
            )
        else:
            await db.attendance.insert_one({
                "labour_id": labour_id,
                "site_id": bulk.site_id,
                "date": bulk.date,
                "status": status,
                "wage_snapshot": daily_wage,
                "wage_earned": wage_earned,
                "marked_by": str(user["_id"]),
            })
        results.append({"labour_id": labour_id, "status": status, "wage_earned": wage_earned})

    return {"message": f"Marked attendance for {len(results)} labours", "records": results}


@router.get("")
async def get_attendance(
    site_id: str = None,
    labour_id: str = None,
    date: str = None,
    user=Depends(get_current_user)
):
    db = get_db()
    query = {}
    if site_id:
        query["site_id"] = site_id
    if labour_id:
        query["labour_id"] = labour_id
    if date:
        query["date"] = date

    records = []
    async for att in db.attendance.find(query).sort("date", -1):
        att["id"] = str(att.pop("_id"))
        # Get labour name
        try:
            labour = await db.labours.find_one({"_id": ObjectId(att["labour_id"])})
            att["labour_name"] = labour["name"] if labour else "Unknown"
        except Exception:
            att["labour_name"] = "Unknown"
        records.append(att)
    return records


@router.delete("/{att_id}")
async def delete_attendance(att_id: str, user=Depends(get_current_user)):
    db = get_db()
    result = await db.attendance.delete_one({"_id": ObjectId(att_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    return {"message": "Attendance record deleted"}
