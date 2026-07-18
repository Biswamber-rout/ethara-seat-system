"""
Seed data generator for Ethara Seat Allocation & Project Mapping System.

Generates, per the assessment brief's minimums:
  - 5,000 employees
  - 5 floors, 10 zones
  - 5,500+ seats
  - 10+ projects
  - 500+ available seats
  - 100+ reserved seats
  - 50+ employees pending allocation

Run: python seed_data.py
"""
import random
from datetime import date, timedelta
from faker import Faker

from database import engine, SessionLocal
import models

fake = Faker()
random.seed(42)
Faker.seed(42)

PROJECTS = [
    ("Indigo", "Manoj Verma"), ("Indreed", "Priya Sharma"), ("Mydreed", "Arjun Nair"),
    ("Preed", "Sneha Iyer"), ("Serfy", "Rahul Gupta"), ("Oreed", "Kavya Menon"),
    ("Bedegreed", "Vikram Rao"), ("Opreed", "Ananya Das"), ("Serry", "Karthik Reddy"),
    ("Kaary", "Divya Pillai"), ("Mered", "Rohan Kapoor"),
]

DEPARTMENTS = ["Engineering", "AI/ML", "Data Annotation", "QA", "Product", "HR", "Growth", "Design", "DevOps"]
ROLES = ["Software Engineer", "Data Annotator", "ML Engineer", "QA Analyst", "Product Manager",
          "HR Executive", "Growth Associate", "UI/UX Designer", "DevOps Engineer", "Team Lead"]

FLOORS = [1, 2, 3, 4, 5]
ZONES = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]  # 10 zones
BAYS_PER_ZONE = 20
SEATS_PER_BAY = 28  # 5 floors * 10 zones * 20 bays * 28 seats -> 5600 seats total (target >= 5500)


def build_seats(db):
    seats = []
    seat_count = 0
    # Distribute zones across floors (each floor gets 2 zones, 5 floors * 2 = 10 zones)
    floor_zone_map = {}
    zone_idx = 0
    for floor in FLOORS:
        floor_zone_map[floor] = ZONES[zone_idx:zone_idx + 2]
        zone_idx += 2

    for floor, zones in floor_zone_map.items():
        for zone in zones:
            for bay_num in range(1, BAYS_PER_ZONE + 1):
                bay_label = f"Bay{bay_num}"
                for seat_num in range(1, SEATS_PER_BAY + 1):
                    seat_number = f"{zone}{bay_num}-{seat_num:02d}"
                    seats.append(models.Seat(
                        floor=floor,
                        zone=zone,
                        bay=bay_label,
                        seat_number=seat_number,
                        status="Available",  # set later
                    ))
                    seat_count += 1

    print(f"Generated {seat_count} seat records (target >= 5500).")
    db.bulk_save_objects(seats)
    db.commit()
    return seat_count


def build_projects(db):
    project_objs = []
    for name, manager in PROJECTS:
        project_objs.append(models.Project(
            name=name,
            description=f"{name} project delivering domain-specific AI/data solutions for Ethara clients.",
            manager_name=manager,
            status="Active",
        ))
    db.bulk_save_objects(project_objs)
    db.commit()
    return db.query(models.Project).all()


def build_employees(db, projects, total=5000):
    used_emails = set()
    employees = []
    for i in range(1, total + 1):
        first = fake.first_name()
        last = fake.last_name()
        name = f"{first} {last}"
        email_base = f"{first}.{last}{i}".lower().replace(" ", "")
        email = f"{email_base}@ethara.ai"
        while email in used_emails:
            email = f"{email_base}{random.randint(1,9999)}@ethara.ai"
        used_emails.add(email)

        joining_date = fake.date_between(start_date="-3y", end_date="today")
        project = random.choice(projects)
        # ~1.5% of employees recently joined and pending allocation (target >= 50 of 5000)
        pending = random.random() < 0.02

        employees.append(models.Employee(
            employee_code=f"ETH{i:05d}",
            name=name,
            email=email,
            department=random.choice(DEPARTMENTS),
            role=random.choice(ROLES),
            joining_date=joining_date,
            status="Pending Allocation" if pending else "Active",
            project_id=project.id,
            seat_allocation_status="Unallocated" if pending else "Allocated",
        ))
    db.bulk_save_objects(employees)
    db.commit()
    print(f"Generated {total} employee records.")
    return db.query(models.Employee).all()


def allocate_seats(db, employees, seats, reserved_target=550, available_target=520):
    """
    Allocate seats to non-pending employees, then mark some remaining seats
    Reserved / Maintenance so we clearly exceed the brief's minimums:
      >= 500 available, >= 100 reserved.
    """
    random.shuffle(seats)
    seat_iter = iter(seats)
    allocations = []
    allocated_count = 0

    non_pending = [e for e in employees if e.status != "Pending Allocation"]

    for emp in non_pending:
        try:
            seat = next(seat_iter)
        except StopIteration:
            break
        seat.status = "Occupied"
        allocations.append(models.SeatAllocation(
            employee_id=emp.id,
            seat_id=seat.id,
            project_id=emp.project_id,
            allocation_status="Active",
        ))
        allocated_count += 1

    db.bulk_save_objects(allocations)

    # Remaining seats: mark some reserved, a few under maintenance, rest stay available.
    # Sized so we comfortably clear the brief's minimums (>=500 available, >=100 reserved)
    # regardless of exact employee/seat counts.
    remaining = list(seat_iter)
    random.shuffle(remaining)
    reserved_count = min(150, len(remaining))
    maintenance_count = min(30, max(0, len(remaining) - reserved_count))

    for seat in remaining[:reserved_count]:
        seat.status = "Reserved"
    for seat in remaining[reserved_count:reserved_count + maintenance_count]:
        seat.status = "Maintenance"
    # everything else stays "Available"

    db.commit()
    print(f"Allocated seats to {allocated_count} employees.")
    print(f"Remaining unallocated seats: {len(remaining)} "
          f"(Reserved: {reserved_count}, Maintenance: ~30, Available: rest).")


def main():
    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        print("Clearing existing data...")
        db.query(models.SeatAllocation).delete()
        db.query(models.Employee).delete()
        db.query(models.Seat).delete()
        db.query(models.Project).delete()
        db.commit()

        print("Seeding projects...")
        projects = build_projects(db)

        print("Seeding seats...")
        build_seats(db)
        seats = db.query(models.Seat).all()

        print("Seeding employees...")
        employees = build_employees(db, projects, total=5000)

        print("Allocating seats...")
        allocate_seats(db, employees, seats)

        # Final verification against brief minimums
        total_employees = db.query(models.Employee).count()
        total_seats = db.query(models.Seat).count()
        available = db.query(models.Seat).filter(models.Seat.status == "Available").count()
        reserved = db.query(models.Seat).filter(models.Seat.status == "Reserved").count()
        pending = db.query(models.Employee).filter(models.Employee.status == "Pending Allocation").count()
        floors = db.query(models.Seat.floor).distinct().count()
        zones = db.query(models.Seat.zone).distinct().count()
        proj_count = db.query(models.Project).count()

        print("\n--- Seed Summary ---")
        print(f"Employees: {total_employees} (target 5000)")
        print(f"Seats: {total_seats} (target >= 5500)")
        print(f"Floors: {floors} (target >= 5)")
        print(f"Zones: {zones} (target >= 10)")
        print(f"Projects: {proj_count} (target >= 10)")
        print(f"Available seats: {available} (target >= 500)")
        print(f"Reserved seats: {reserved} (target >= 100)")
        print(f"Pending allocation employees: {pending} (target >= 50)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
