from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Literal
from datetime import datetime


# ═══════════════════════════════════════
# USER MODELS
# ═══════════════════════════════════════

class CreateUserRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str


# ═══════════════════════════════════════
# SITE MODELS
# ═══════════════════════════════════════

class SiteCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    location: str = Field("", max_length=300)
    contract_value: float = Field(..., ge=0)
    client_name: str = Field("", max_length=200)
    status: Literal["active", "completed", "paused"] = "active"


class SiteUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    contract_value: Optional[float] = None
    client_name: Optional[str] = None
    status: Optional[Literal["active", "completed", "paused"]] = None


# ═══════════════════════════════════════
# LABOUR MODELS
# ═══════════════════════════════════════

class LabourCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    phone: str = Field("", max_length=15)
    skill: str = Field("General", max_length=100)
    daily_wage: float = Field(..., ge=0)
    joining_fee: float = Field(0, ge=0)
    site_id: Optional[str] = None


class LabourUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    skill: Optional[str] = None
    daily_wage: Optional[float] = None
    joining_fee: Optional[float] = None
    site_id: Optional[str] = None


# ═══════════════════════════════════════
# ATTENDANCE MODELS
# ═══════════════════════════════════════

class AttendanceCreate(BaseModel):
    labour_id: str
    site_id: str
    date: str  # YYYY-MM-DD format
    status: Literal["present", "half_day", "absent"] = "present"


class AttendanceBulkCreate(BaseModel):
    site_id: str
    date: str  # YYYY-MM-DD format
    records: list[dict]  # [{labour_id, status}]


# ═══════════════════════════════════════
# EXPENSE MODELS
# ═══════════════════════════════════════

class ExpenseCreate(BaseModel):
    site_id: str
    description: str = Field(..., min_length=2, max_length=300)
    amount: float = Field(..., gt=0)
    category: str = Field("General", max_length=100)
    date: str  # YYYY-MM-DD format


class ExpenseUpdate(BaseModel):
    description: Optional[str] = None
    amount: Optional[float] = None
    category: Optional[str] = None
    date: Optional[str] = None


# ═══════════════════════════════════════
# ADVANCE MODELS
# ═══════════════════════════════════════

class AdvanceCreate(BaseModel):
    labour_id: str
    amount: float = Field(..., gt=0)
    date: str  # YYYY-MM-DD format
    note: str = Field("", max_length=300)
    is_joining_fee: bool = False
    is_settlement: bool = False


class AdvanceUpdate(BaseModel):
    labour_id: str
    amount: float
    date: str
    note: Optional[str] = None
    is_joining_fee: bool = False
    is_settlement: bool = False

# ═══════════════════════════════════════
# ALLOCATION MODELS
# ═══════════════════════════════════════

class AllocationCreate(BaseModel):
    labour_id: str
    site_id: str
    date: str  # YYYY-MM-DD
