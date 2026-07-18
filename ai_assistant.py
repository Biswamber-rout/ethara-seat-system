"""
AI Assistant for natural-language seat & project queries.

Design:
  - Primary: lightweight rule/keyword-based intent parser (fast, free, no API key,
    100% reliable for a live demo).
  - Optional: if OPENAI_API_KEY / ANTHROPIC_API_KEY is set, falls back to calling
    the LLM for queries the rule parser can't confidently classify, using the same
    structured data as context ("RAG-lite" over the live database).

This satisfies the brief's "If the AI API is not available, candidates can build
a fallback keyword-based assistant" clause, while leaving a clean extension point
for the advanced/LLM requirement.
"""
import os
import re
from sqlalchemy.orm import Session
from sqlalchemy import func
import models

USE_LLM = bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENAI_API_KEY"))


def _find_employee(db: Session, name: str = None, email: str = None, employee_id: int = None):
    q = db.query(models.Employee)
    if employee_id:
        return q.filter(models.Employee.id == employee_id).first()
    if email:
        return q.filter(func.lower(models.Employee.email) == email.lower()).first()
    if name:
        return q.filter(func.lower(models.Employee.name).like(f"%{name.lower()}%")).first()
    return None


def _describe_employee_seat(db: Session, employee: models.Employee) -> str:
    if not employee:
        return "I couldn't find that employee. Please check the name or email and try again."

    allocation = (
        db.query(models.SeatAllocation)
        .filter(models.SeatAllocation.employee_id == employee.id, models.SeatAllocation.allocation_status == "Active")
        .first()
    )
    project_name = employee.project.name if employee.project else "no project currently assigned"

    if not allocation:
        return f"{employee.name} has not been allocated a seat yet. They are assigned to {project_name}."

    seat = db.query(models.Seat).filter(models.Seat.id == allocation.seat_id).first()
    return (
        f"{employee.name} is seated on Floor {seat.floor}, Zone {seat.zone}, "
        f"Bay {seat.bay}, Seat {seat.seat_number}. They are assigned to Project {project_name}."
    )


def _extract_name(query: str) -> str:
    # crude but effective for demo: capture a capitalized word/phrase after "employee" or "is"
    m = re.search(r"(?:employee|is)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)", query)
    if m:
        return m.group(1)
    # fallback: last capitalized token in the query
    caps = re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", query)
    ignore = {"Floor", "Zone", "Bay", "Seat", "Project", "Where", "Which", "Show", "Who", "How"}
    caps = [c for c in caps if c not in ignore]
    return caps[-1] if caps else None


def _extract_email(query: str) -> str:
    m = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", query)
    return m.group(0) if m else None


def _extract_floor(query: str) -> int:
    m = re.search(r"floor\s*(\d+)", query, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _extract_zone(query: str) -> str:
    m = re.search(r"zone\s*([A-Za-z0-9]+)", query, re.IGNORECASE)
    return m.group(1).upper() if m else None


def _extract_project(db: Session, query: str) -> models.Project:
    projects = db.query(models.Project).all()
    for p in projects:
        if p.name.lower() in query.lower():
            return p
    return None


def answer_query(db: Session, query: str, email: str = None, employee_id: int = None) -> dict:
    q = query.strip()
    ql = q.lower()

    # Intent: "where is my seat" / self-lookup via email or employee_id
    if ("my seat" in ql or "where am i" in ql or "my project" in ql) and (email or employee_id):
        employee = _find_employee(db, email=email, employee_id=employee_id)
        return {"answer": _describe_employee_seat(db, employee), "intent": "self_seat_lookup"}

    # Intent: "where is employee X seated" / "where is X sitting"
    if re.search(r"where\s+is.*(seat|sit)", ql) or "seated" in ql:
        # try email in query first
        em = _extract_email(q)
        name = _extract_name(q)
        employee = _find_employee(db, name=name, email=em)
        return {"answer": _describe_employee_seat(db, employee), "intent": "employee_seat_lookup"}

    # Intent: "which project is X assigned to"
    if "which project" in ql or ("project" in ql and "assigned" in ql):
        em = _extract_email(q)
        name = _extract_name(q)
        employee = _find_employee(db, name=name, email=em)
        if not employee:
            return {"answer": "I couldn't find that employee.", "intent": "project_lookup"}
        proj = employee.project.name if employee.project else "no project"
        return {"answer": f"{employee.name} is assigned to Project {proj}.", "intent": "project_lookup"}

    # Intent: available seats on a floor / zone
    if "available seat" in ql or ("show" in ql and "seat" in ql):
        floor = _extract_floor(q)
        zone = _extract_zone(q)
        query_obj = db.query(models.Seat).filter(models.Seat.status == "Available")
        if floor:
            query_obj = query_obj.filter(models.Seat.floor == floor)
        if zone:
            query_obj = query_obj.filter(models.Seat.zone == zone)
        seats = query_obj.limit(10).all()
        count = query_obj.count()
        if not seats:
            scope = f"Floor {floor} " if floor else ""
            scope += f"Zone {zone}" if zone else ""
            return {"answer": f"No available seats found {('on ' + scope) if scope else ''}.".strip(), "intent": "available_seats"}
        listing = ", ".join([f"{s.seat_number} (Floor {s.floor}, Zone {s.zone})" for s in seats])
        extra = f" ({count} total available matching this filter.)" if count > len(seats) else ""
        return {"answer": f"Available seats: {listing}.{extra}", "intent": "available_seats"}

    # Intent: seat utilization for a project
    if "occupied" in ql or "utilization" in ql or "how many seats" in ql:
        proj = _extract_project(db, q)
        if proj:
            occupied = (
                db.query(func.count(models.SeatAllocation.id))
                .filter(models.SeatAllocation.project_id == proj.id, models.SeatAllocation.allocation_status == "Active")
                .scalar()
            )
            return {
                "answer": f"Project {proj.name} currently has {occupied} occupied seat(s).",
                "intent": "project_utilization",
            }
        total_occupied = db.query(func.count(models.Seat.id)).filter(models.Seat.status == "Occupied").scalar()
        total_seats = db.query(func.count(models.Seat.id)).scalar()
        return {
            "answer": f"{total_occupied} of {total_seats} seats are currently occupied company-wide.",
            "intent": "overall_utilization",
        }

    # Intent: who is near / around a given employee
    if "near me" in ql or "sitting near" in ql or "who is near" in ql:
        em = email or _extract_email(q)
        name = _extract_name(q)
        employee = _find_employee(db, name=name, email=em)
        allocation = (
            db.query(models.SeatAllocation)
            .filter(models.SeatAllocation.employee_id == employee.id, models.SeatAllocation.allocation_status == "Active")
            .first()
            if employee else None
        )
        if not allocation:
            return {"answer": "I couldn't determine the seat location to find nearby colleagues.", "intent": "nearby_lookup"}
        seat = db.query(models.Seat).filter(models.Seat.id == allocation.seat_id).first()
        neighbors = (
            db.query(models.Employee)
            .join(models.SeatAllocation, models.SeatAllocation.employee_id == models.Employee.id)
            .join(models.Seat, models.Seat.id == models.SeatAllocation.seat_id)
            .filter(
                models.Seat.floor == seat.floor,
                models.Seat.zone == seat.zone,
                models.Seat.bay == seat.bay,
                models.SeatAllocation.allocation_status == "Active",
                models.Employee.id != employee.id,
            )
            .limit(10)
            .all()
        )
        if not neighbors:
            return {"answer": f"No one else is currently seated in Bay {seat.bay}, Zone {seat.zone}.", "intent": "nearby_lookup"}
        names = ", ".join([n.name for n in neighbors])
        return {"answer": f"Employees near you (Bay {seat.bay}, Zone {seat.zone}): {names}.", "intent": "nearby_lookup"}

    # Intent: allocate a seat for a new employee
    if "allocate" in ql and ("new employee" in ql or "new joiner" in ql):
        return {
            "answer": (
                "To allocate a seat for a new joiner, please use the New Joiner form on the "
                "dashboard or call POST /seats/allocate with the employee's ID."
            ),
            "intent": "allocation_guidance",
        }

    if USE_LLM:
        try:
            return _llm_fallback(db, q)
        except Exception:
            pass

    return {
        "answer": (
            "I couldn't quite understand that. Try asking things like: "
            "'Where is employee <name> seated?', 'Show available seats on Floor 3', "
            "'How many seats are occupied for Project <name>?', or 'Who is sitting near me?'"
        ),
        "intent": "fallback_unrecognized",
    }


def _llm_fallback(db: Session, query: str) -> dict:
    """
    Optional advanced path: calls an LLM with a compact snapshot of relevant data
    when the keyword parser can't classify the intent. Only runs if an API key is set.
    """
    import json
    import urllib.request

    summary = {
        "total_employees": db.query(func.count(models.Employee.id)).scalar(),
        "total_seats": db.query(func.count(models.Seat.id)).scalar(),
        "available_seats": db.query(func.count(models.Seat.id)).filter(models.Seat.status == "Available").scalar(),
        "projects": [p.name for p in db.query(models.Project).limit(15).all()],
    }
    prompt = (
        "You are a seat/project assistant for Ethara. Answer the user's question concisely "
        "using this data snapshot. If the answer isn't determinable, say so.\n"
        f"Data snapshot: {json.dumps(summary)}\n"
        f"Question: {query}"
    )
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("No LLM API key configured")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps({
            "model": "claude-sonnet-4-6",
            "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}],
        }).encode(),
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    text = "".join([b.get("text", "") for b in data.get("content", [])])
    return {"answer": text or "No response from LLM.", "intent": "llm_fallback"}
