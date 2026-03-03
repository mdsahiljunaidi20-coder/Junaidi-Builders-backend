from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId
from database import get_db
from auth import hash_password, verify_password, create_access_token, get_current_user, require_contractor
from models import CreateUserRequest, UserLogin, UserResponse

router = APIRouter(prefix="/api/users", tags=["Users"])


# ═══════════════════════════════════════
# LOGIN (only public endpoint)
# ═══════════════════════════════════════

@router.post("/login")
async def login(creds: UserLogin):
    db = get_db()
    user = await db.users.find_one({"email": creds.email})
    if not user or not verify_password(creds.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(data={"sub": user["email"], "role": user["role"]})
    return {
        "token": token,
        "user": {
            "id": str(user["_id"]),
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
        }
    }


# ═══════════════════════════════════════
# GET CURRENT USER
# ═══════════════════════════════════════

@router.get("/me")
async def get_me(user=Depends(get_current_user)):
    return {
        "id": str(user["_id"]),
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
    }


# ═══════════════════════════════════════
# CREATE USER (hierarchical)
# Admin → creates Contractor
# Contractor → creates Subcontractor
# Subcontractor → cannot create anyone
# ═══════════════════════════════════════

ROLE_HIERARCHY = {
    "admin": "contractor",
    "contractor": "subcontractor",
}

@router.post("/create")
async def create_user(req: CreateUserRequest, creator=Depends(get_current_user)):
    db = get_db()
    creator_role = creator.get("role")

    # Determine what role the new user gets
    child_role = ROLE_HIERARCHY.get(creator_role)
    if not child_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to create users"
        )

    # Check if email already exists
    existing = await db.users.find_one({"email": req.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user_doc = {
        "name": req.name,
        "email": req.email,
        "password": hash_password(req.password),
        "role": child_role,
        "created_by": str(creator["_id"]),
    }
    result = await db.users.insert_one(user_doc)

    return {
        "message": f"{child_role.capitalize()} account created successfully",
        "user": {
            "id": str(result.inserted_id),
            "name": req.name,
            "email": req.email,
            "role": child_role,
        }
    }


# ═══════════════════════════════════════
# LIST USERS CREATED BY ME
# ═══════════════════════════════════════

@router.get("/managed")
async def get_managed_users(user=Depends(get_current_user)):
    db = get_db()
    creator_role = user.get("role")

    # Only admin and contractor can have managed users
    if creator_role not in ROLE_HIERARCHY:
        return []

    users = []
    async for u in db.users.find({"created_by": str(user["_id"])}).sort("name", 1):
        users.append({
            "id": str(u["_id"]),
            "name": u["name"],
            "email": u["email"],
            "role": u["role"],
        })
    return users


# ═══════════════════════════════════════
# DELETE USER CREATED BY ME
# ═══════════════════════════════════════

@router.delete("/{user_id}")
async def delete_user(user_id: str, user=Depends(get_current_user)):
    db = get_db()

    # Find the target user
    target = await db.users.find_one({"_id": ObjectId(user_id)})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # Only allow deleting users you created
    if target.get("created_by") != str(user["_id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete users you created"
        )

    await db.users.delete_one({"_id": ObjectId(user_id)})
    return {"message": "User deleted successfully"}
