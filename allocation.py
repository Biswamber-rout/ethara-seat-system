"""
Seat allocation business logic.
Implements the business rules from the assessment brief:
  1. One employee can have only one active seat.
  2. One seat can be allocated to only one active employee.
  3. Released seats become available again.
  4. Reserved seats cannot be allocated unless status is changed.
  5. New joiners are prioritized for available seats near their project team.
  6. Duplicate employee email not allowed (enforced at DB level via unique constraint).
  7. Duplicate seat number on same floor/zone not allowed (enforced at DB level).
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from fastapi import HTTPException
import models


def find_best_seat(db: Session, employee: models.Employee, preferred_zone: str = None):
    """
    Suggest the best available seat for an employee.
    Priority:
      1. Available seat in a zone where teammates from the same project already sit.
      2. Available seat in preferred_zone, if given.
      3. Any available seat (lowest floor/zone/seat_number first).
    Reserved / Occupied / Maintenance seats are never suggested here.
    """
    # 1. Try to find a zone where the employee's project teammates are seated
    if employee.project_id:
        teammate_zone_row = (
            db.query(models.Seat.floor, models.Seat.zone, func.count(models.SeatAllocation.id).label("cnt"))
            .join(models.SeatAllocation, models.SeatAllocation.seat_id == models.Seat.id)
            .join(models.Employee, models.Employee.id == models.SeatAllocation.employee_id)
            .filter(
                models.Employee.project_id == employee.project_id,
                models.SeatAllocation.allocation_status == "Active",
            )
            .group_by(models.Seat.floor, models.Seat.zone)
            .order_by(func.count(models.SeatAllocation.id).desc())
            .first()
        )
        if teammate_zone_row:
            floor, zone, _ = teammate_zone_row
            seat = (
                db.query(models.Seat)
                .filter(models.Seat.status == "Available", models.Seat.floor == floor, models.Seat.zone == zone)
                .order_by(models.Seat.seat_number)
                .first()
            )
            if seat:
                return seat, f"Allocated near project team in Floor {floor}, Zone {zone}."

    # 2. Preferred zone requested explicitly
    if preferred_zone:
        seat = (
            db.query(models.Seat)
            .filter(models.Seat.status == "Available", models.Seat.zone == preferred_zone)
            .order_by(models.Seat.floor, models.Seat.seat_number)
            .first()
        )
        if seat:
            return seat, f"Allocated in preferred zone {preferred_zone}."

    # 3. Fallback: any available seat, alternate zone suggestion
    seat = (
        db.query(models.Seat)
        .filter(models.Seat.status == "Available")
        .order_by(models.Seat.floor, models.Seat.zone, models.Seat.seat_number)
        .first()
    )
    if seat:
        note = "Allocated in alternate zone (preferred zone/team zone had no availability)."
        return seat, note

    return None, "No available seats in the system."


def allocate_seat(db: Session, employee_id: int, seat_id: int = None, project_id: int = None, preferred_zone: str = None):
    employee = db.query(models.Employee).filter(models.Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Rule 1: employee must not already have an active seat
    existing = (
        db.query(models.SeatAllocation)
        .filter(models.SeatAllocation.employee_id == employee_id, models.SeatAllocation.allocation_status == "Active")
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Employee already has an active seat allocation. Release it first.")

    if project_id:
        employee.project_id = project_id

    if seat_id:
        seat = db.query(models.Seat).filter(models.Seat.id == seat_id).first()
        if not seat:
            raise HTTPException(status_code=404, detail="Seat not found")
        if seat.status != "Available":
            raise HTTPException(status_code=400, detail=f"Seat is not available (current status: {seat.status}).")
        note = "Manually assigned seat."
    else:
        seat, note = find_best_seat(db, employee, preferred_zone)
        if not seat:
            raise HTTPException(status_code=400, detail="No available seats to allocate.")

    # Rule 2: seat must not already be actively allocated
    active_on_seat = (
        db.query(models.SeatAllocation)
        .filter(models.SeatAllocation.seat_id == seat.id, models.SeatAllocation.allocation_status == "Active")
        .first()
    )
    if active_on_seat:
        raise HTTPException(status_code=400, detail="Seat already has an active allocation (race condition detected).")

    allocation = models.SeatAllocation(
        employee_id=employee.id,
        seat_id=seat.id,
        project_id=employee.project_id,
        allocation_status="Active",
        allocation_date=datetime.utcnow(),
    )
    seat.status = "Occupied"
    employee.seat_allocation_status = "Allocated"
    if employee.status == "Pending Allocation":
        employee.status = "Active"

    db.add(allocation)
    db.commit()
    db.refresh(allocation)

    return allocation, note


def release_seat(db: Session, employee_id: int = None, seat_id: int = None):
    query = db.query(models.SeatAllocation).filter(models.SeatAllocation.allocation_status == "Active")
    if employee_id:
        query = query.filter(models.SeatAllocation.employee_id == employee_id)
    if seat_id:
        query = query.filter(models.SeatAllocation.seat_id == seat_id)

    allocation = query.first()
    if not allocation:
        raise HTTPException(status_code=404, detail="No active allocation found for the given employee/seat.")

    allocation.allocation_status = "Released"
    allocation.released_date = datetime.utcnow()

    seat = db.query(models.Seat).filter(models.Seat.id == allocation.seat_id).first()
    if seat:
        seat.status = "Available"  # Rule 3: released seats become available again

    employee = db.query(models.Employee).filter(models.Employee.id == allocation.employee_id).first()
    if employee:
        employee.seat_allocation_status = "Unallocated"

    db.commit()
    db.refresh(allocation)
    return allocation
