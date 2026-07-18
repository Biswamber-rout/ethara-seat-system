from pydantic import BaseModel, EmailStr
from datetime import date, datetime
from typing import Optional


# ---------- Project ----------
class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    manager_name: Optional[str] = None
    status: Optional[str] = "Active"


class ProjectOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    manager_name: Optional[str]
    status: str

    class Config:
        from_attributes = True


# ---------- Employee ----------
class EmployeeCreate(BaseModel):
    employee_code: str
    name: str
    email: EmailStr
    department: Optional[str] = None
    role: Optional[str] = None
    joining_date: date
    project_id: Optional[int] = None
    status: Optional[str] = "Active"


class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    department: Optional[str] = None
    role: Optional[str] = None
    project_id: Optional[int] = None
    status: Optional[str] = None


class EmployeeOut(BaseModel):
    id: int
    employee_code: str
    name: str
    email: str
    department: Optional[str]
    role: Optional[str]
    joining_date: date
    status: str
    project_id: Optional[int]
    seat_allocation_status: str

    class Config:
        from_attributes = True


# ---------- Seat ----------
class SeatCreate(BaseModel):
    floor: int
    zone: str
    bay: str
    seat_number: str
    status: Optional[str] = "Available"


class SeatOut(BaseModel):
    id: int
    floor: int
    zone: str
    bay: str
    seat_number: str
    status: str

    class Config:
        from_attributes = True


class SeatAllocateRequest(BaseModel):
    employee_id: int
    seat_id: Optional[int] = None  # if not given, system auto-suggests
    project_id: Optional[int] = None
    preferred_zone: Optional[str] = None


class SeatReleaseRequest(BaseModel):
    employee_id: Optional[int] = None
    seat_id: Optional[int] = None


# ---------- AI Assistant ----------
class AIQueryRequest(BaseModel):
    query: str
    email: Optional[str] = None
    employee_id: Optional[int] = None


class AIQueryResponse(BaseModel):
    answer: str
    intent: Optional[str] = None
