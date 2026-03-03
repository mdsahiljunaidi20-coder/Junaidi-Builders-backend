from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from database import get_db
from auth import get_current_user, require_contractor
from models import SiteCreate, SiteUpdate

router = APIRouter(prefix="/api/sites", tags=["Sites"])


@router.post("")
async def create_site(site: SiteCreate, user=Depends(require_contractor)):
    db = get_db()
    site_doc = {
        **site.model_dump(),
        "created_by": str(user["_id"]),
    }
    result = await db.sites.insert_one(site_doc)
    site_doc["id"] = str(result.inserted_id)
    site_doc.pop("_id", None)
    return site_doc


@router.get("")
async def get_sites(status: str = None, user=Depends(get_current_user)):
    db = get_db()
    query = {}
    if status:
        query["status"] = status
    sites = []
    async for site in db.sites.find(query).sort("name", 1):
        site["id"] = str(site.pop("_id"))
        sites.append(site)
    return sites


@router.get("/{site_id}")
async def get_site(site_id: str, user=Depends(get_current_user)):
    db = get_db()
    site = await db.sites.find_one({"_id": ObjectId(site_id)})
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    site["id"] = str(site.pop("_id"))
    return site


@router.put("/{site_id}")
async def update_site(site_id: str, update: SiteUpdate, user=Depends(require_contractor)):
    db = get_db()
    update_data = {k: v for k, v in update.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = await db.sites.update_one({"_id": ObjectId(site_id)}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Site not found")
    site = await db.sites.find_one({"_id": ObjectId(site_id)})
    site["id"] = str(site.pop("_id"))
    return site


@router.delete("/{site_id}")
async def delete_site(site_id: str, user=Depends(require_contractor)):
    db = get_db()
    result = await db.sites.delete_one({"_id": ObjectId(site_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Site not found")
    # Also delete related data
    oid = ObjectId(site_id)
    await db.labours.delete_many({"site_id": site_id})
    await db.attendance.delete_many({"site_id": site_id})
    await db.expenses.delete_many({"site_id": site_id})
    return {"message": "Site and all related data deleted"}


@router.get("/{site_id}/profit-loss")
async def get_profit_loss(site_id: str, user=Depends(get_current_user)):
    db = get_db()
    site = await db.sites.find_one({"_id": ObjectId(site_id)})
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    # Calculate labour cost from attendance wage snapshots
    labour_cost = 0
    async for att in db.attendance.find({"site_id": site_id, "status": {"$ne": "absent"}}):
        labour_cost += att.get("wage_earned", 0)

    # Calculate total expenses
    total_expenses = 0
    async for exp in db.expenses.find({"site_id": site_id}):
        total_expenses += exp.get("amount", 0)

    # Calculate total advances for labours in this site
    total_advances = 0
    labour_ids = []
    async for labour in db.labours.find({"site_id": site_id}):
        labour_ids.append(str(labour["_id"]))
    if labour_ids:
        async for adv in db.advances.find({"labour_id": {"$in": labour_ids}}):
            total_advances += adv.get("amount", 0)

    contract_value = site.get("contract_value", 0)
    total_cost = labour_cost + total_expenses
    profit_loss = contract_value - total_cost

    return {
        "site_id": site_id,
        "site_name": site.get("name", ""),
        "contract_value": contract_value,
        "labour_cost": labour_cost,
        "total_expenses": total_expenses,
        "total_cost": total_cost,
        "profit_loss": profit_loss,
        "total_advances": total_advances,
        "is_profit": profit_loss >= 0,
    }
