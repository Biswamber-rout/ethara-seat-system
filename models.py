"""
SQLAlchemy database models for Ethara Seat Allocation & Project Mapping System.
"""
from sqlalchemy import (
    Column, Integer, String, Date, DateTime, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    description = Column(String, nullable=True)
    manager_name = Column(String, nullable=True)
    status = Column(String, default="Active")  # Active / Inactive
    created_at = Column(DateTime, default=datetime.utcnow)

    employees = relationship("Employee", back_populates="project")


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    employee_code = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    department = Column(String, nullable=True)
    role = Column(String, nullable=True)
    joining_date = Column(Date, nullable=False)
    status = Column(String, default="Active")  # Active / Inactive / Pending Allocation
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    seat_allocation_status = Column(String, default="Unallocated")  # Allocated / Unallocated / Pending
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="employees")
    allocations = relationship("SeatAllocation", back_populates="employee")


class Seat(Base):
    __tablename__ = "seats"

    id = Column(Integer, primary_key=True, index=True)
    floor = Column(Integer, nullable=False, index=True)
    zone = Column(String, nullable=False, index=True)
    bay = Column(String, nullable=False)
    seat_number = Column(String, nullable=False, index=True)
    status = Column(String, default="Available", index=True)  # Available/Occupied/Reserved/Maintenance
    created_at = Column(DateTime, default=datetime.utcnow)

    allocations = relationship("SeatAllocation", back_populates="seat")

    __table_args__ = (
        UniqueConstraint("floor", "zone", "seat_number", name="uq_seat_floor_zone_number"),
    )


class SeatAllocation(Base):
    __tablename__ = "seat_allocations"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    seat_id = Column(Integer, ForeignKey("seats.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    allocation_status = Column(String, default="Active")  # Active / Released
    allocation_date = Column(DateTime, default=datetime.utcnow)
    released_date = Column(DateTime, nullable=True)

    employee = relationship("Employee", back_populates="allocations")
    seat = relationship("Seat", back_populates="allocations")
