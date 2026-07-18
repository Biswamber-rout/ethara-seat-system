"""
Ethara Seat Allocation & Project Mapping System — Backend API
"""
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import Optional, List
import os

import models
import schemas
from database import engine, get_db
import allocation as alloc
import ai_assistant

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Ethara Seat Allocation & Project Mapping System",
    description="Manages seat allocation, project mapping, and AI-assisted queries for ~5,000 employees.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "ok", "service": "Ethara Seat Allocation API", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "healthy"}


# ============================== EMPLOYEE APIs ==============================

@app.post("/employees", response_model=schemas.EmployeeOut)
def create_employee(payload: schemas.EmployeeCreate, db: Session = Depends(get_db)):
    if db.query(models.Employee).filter(models.Employee.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Duplicate employee email is not allowed.")
    if db.query(models.Employee).filter(models.Employee.employee_code == payload.employee_code).first():
        raise HTTPException(status_code=400, detail="Duplicate employee code is not allowed.")

    employee = models.Employee(
        employee_code=payload.employee_code,
        name=payload.name,
        email=payload.email,
        department=payload.department,
        role=payload.role,
        joining_date=payload.joining_date,
        project_id=payload.project_id,
        status=payload.status or "Pending Allocation",
        seat_allocation_status="Unallocated",
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


@app.get("/employees", response_model=List[schemas.EmployeeOut])
def list_employees(
    skip: int = 0,
    limit: int = 50,
    name: Optional[str] = None,
    email: Optional[str] = None,
    employee_code: Optional[str] = None,
    project_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.Employee)
    if name:
        q = q.filter(models.Employee.name.ilike(f"%{name}%"))
    if email:
        q = q.filter(models.Employee.email.ilike(f"%{email}%"))
    if employee_code:
        q = q.filter(models.Employee.employee_code == employee_code)
    if project_id:
        q = q.filter(models.Employee.project_id == project_id)
    if status:
        q = q.filter(models.Employee.status == status)
    return q.offset(skip).limit(limit).all()


@app.get("/employees/{employee_id}", response_model=schemas.EmployeeOut)
def get_employee(employee_id: int, db: Session = Depends(get_db)):
    employee = db.query(models.Employee).filter(models.Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


@app.put("/employees/{employee_id}", response_model=schemas.EmployeeOut)
def update_employee(employee_id: int, payload: schemas.EmployeeUpdate, db: Session = Depends(get_db)):
    employee = db.query(models.Employee).filter(models.Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    for field, value in payload.dict(exclude_unset=True).items():
        setattr(employee, field, value)
    db.commit()
    db.refresh(employee)
    return employee


@app.delete("/employees/{employee_id}")
def deactivate_employee(employee_id: int, db: Session = Depends(get_db)):
    employee = db.query(models.Employee).filter(models.Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    employee.status = "Inactive"
    # release any active seat
    try:
        alloc.release_seat(db, employee_id=employee_id)
    except HTTPException:
        pass
    db.commit()
    return {"message": f"Employee {employee.name} deactivated."}


# ============================== PROJECT APIs ==============================

@app.post("/projects", response_model=schemas.ProjectOut)
def create_project(payload: schemas.ProjectCreate, db: Session = Depends(get_db)):
    if db.query(models.Project).filter(models.Project.name == payload.name).first():
        raise HTTPException(status_code=400, detail="Project with this name already exists.")
    project = models.Project(**payload.dict())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@app.get("/projects", response_model=List[schemas.ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return db.query(models.Project).all()


@app.get("/projects/{project_id}/employees", response_model=List[schemas.EmployeeOut])
def list_project_employees(project_id: int, db: Session = Depends(get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return db.query(models.Employee).filter(models.Employee.project_id == project_id).all()


# ============================== SEAT APIs ==============================

@app.post("/seats", response_model=schemas.SeatOut)
def create_seat(payload: schemas.SeatCreate, db: Session = Depends(get_db)):
    dup = (
        db.query(models.Seat)
        .filter(models.Seat.floor == payload.floor, models.Seat.zone == payload.zone, models.Seat.seat_number == payload.seat_number)
        .first()
    )
    if dup:
        raise HTTPException(status_code=400, detail="Duplicate seat number on same floor/zone is not allowed.")
    seat = models.Seat(**payload.dict())
    db.add(seat)
    db.commit()
    db.refresh(seat)
    return seat


@app.get("/seats", response_model=List[schemas.SeatOut])
def list_seats(
    skip: int = 0,
    limit: int = 50,
    floor: Optional[int] = None,
    zone: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(models.Seat)
    if floor:
        q = q.filter(models.Seat.floor == floor)
    if zone:
        q = q.filter(models.Seat.zone == zone)
    if status:
        q = q.filter(models.Seat.status == status)
    return q.offset(skip).limit(limit).all()


@app.get("/seats/available", response_model=List[schemas.SeatOut])
def list_available_seats(floor: Optional[int] = None, zone: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(models.Seat).filter(models.Seat.status == "Available")
    if floor:
        q = q.filter(models.Seat.floor == floor)
    if zone:
        q = q.filter(models.Seat.zone == zone)
    return q.all()


@app.post("/seats/allocate")
def allocate_seat(payload: schemas.SeatAllocateRequest, db: Session = Depends(get_db)):
    allocation, note = alloc.allocate_seat(
        db,
        employee_id=payload.employee_id,
        seat_id=payload.seat_id,
        project_id=payload.project_id,
        preferred_zone=payload.preferred_zone,
    )
    seat = db.query(models.Seat).filter(models.Seat.id == allocation.seat_id).first()
    return {
        "message": "Seat allocated successfully.",
        "note": note,
        "allocation_id": allocation.id,
        "seat": schemas.SeatOut.from_orm(seat),
    }


@app.post("/seats/release")
def release_seat(payload: schemas.SeatReleaseRequest, db: Session = Depends(get_db)):
    allocation = alloc.release_seat(db, employee_id=payload.employee_id, seat_id=payload.seat_id)
    return {"message": "Seat released successfully.", "allocation_id": allocation.id}


# ============================== DASHBOARD APIs ==============================

@app.get("/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db)):
    total_employees = db.query(func.count(models.Employee.id)).scalar()
    total_seats = db.query(func.count(models.Seat.id)).scalar()
    occupied = db.query(func.count(models.Seat.id)).filter(models.Seat.status == "Occupied").scalar()
    available = db.query(func.count(models.Seat.id)).filter(models.Seat.status == "Available").scalar()
    reserved = db.query(func.count(models.Seat.id)).filter(models.Seat.status == "Reserved").scalar()
    maintenance = db.query(func.count(models.Seat.id)).filter(models.Seat.status == "Maintenance").scalar()
    pending = db.query(func.count(models.Employee.id)).filter(models.Employee.status == "Pending Allocation").scalar()

    return {
        "total_employees": total_employees,
        "total_seats": total_seats,
        "occupied_seats": occupied,
        "available_seats": available,
        "reserved_seats": reserved,
        "maintenance_seats": maintenance,
        "new_joiners_pending_allocation": pending,
    }


@app.get("/dashboard/project-utilization")
def project_utilization(db: Session = Depends(get_db)):
    rows = (
        db.query(models.Project.name, func.count(models.SeatAllocation.id))
        .join(models.SeatAllocation, models.SeatAllocation.project_id == models.Project.id)
        .filter(models.SeatAllocation.allocation_status == "Active")
        .group_by(models.Project.name)
        .all()
    )
    return [{"project": name, "occupied_seats": count} for name, count in rows]


@app.get("/dashboard/floor-utilization")
def floor_utilization(db: Session = Depends(get_db)):
    rows = (
        db.query(models.Seat.floor, models.Seat.status, func.count(models.Seat.id))
        .group_by(models.Seat.floor, models.Seat.status)
        .all()
    )
    result = {}
    for floor, status, count in rows:
        result.setdefault(floor, {}).update({status: count})
    return [{"floor": f, **statuses} for f, statuses in sorted(result.items())]


# ============================== AI ASSISTANT API ==============================

@app.post("/ai/query", response_model=schemas.AIQueryResponse)
def ai_query(payload: schemas.AIQueryRequest, db: Session = Depends(get_db)):
    result = ai_assistant.answer_query(db, payload.query, email=payload.email, employee_id=payload.employee_id)
    return schemas.AIQueryResponse(answer=result["answer"], intent=result.get("intent"))


# Serve frontend static files if present (for single-service deployment)
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
