"""Roster data and DB resolution for the SPI task dispatch agent (no scoring logic)."""
from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from app.models.core import Employee, SpiDaily, TaskAssignment

OPEN_STATUSES = (
    "PROPOSE",
    "PROPOSITION_SOUMISE",
    "EN_NEGOCIATION",
    "EN_COURS",
    "PREUVE_SOUMISE",
)


def build_employee_roster(db: Session) -> list[dict]:
    """Active employees with SPI and workload — fed to the dispatch agent."""
    employees = (
        db.query(Employee)
        .filter(Employee.status == "ACTIVE", Employee.is_deleted == False)
        .all()
    )
    roster = []
    for emp in employees:
        latest_spi = (
            db.query(SpiDaily)
            .filter(SpiDaily.employee_id == emp.id)
            .order_by(SpiDaily.date.desc())
            .first()
        )
        open_count = (
            db.query(TaskAssignment)
            .filter(
                TaskAssignment.assigned_employee_id == emp.id,
                TaskAssignment.status.in_(OPEN_STATUSES),
            )
            .count()
        )
        spi_val = (
            float(latest_spi.spi_final)
            if latest_spi and latest_spi.spi_final is not None
            else None
        )
        roster.append(
            {
                "employee_id": str(emp.id),
                "matricule": emp.matricule,
                "name": f"{emp.last_name} {emp.first_name}",
                "department": emp.department or "",
                "position": emp.position or "",
                "spi_latest": spi_val,
                "open_task_count": open_count,
            }
        )
    return roster


def roster_json_for_agent(roster: list[dict]) -> str:
    return json.dumps(roster, ensure_ascii=False, indent=2)


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def parse_agent_task(raw: dict, fallback_text: str = "") -> dict:
    """Normalize agent output fields without re-assigning employees."""
    title = (raw.get("title") or raw.get("titre") or fallback_text or "Tache")[:200].strip()
    desc = (raw.get("description") or raw.get("details") or title).strip()
    deliverable = (
        raw.get("expected_deliverable")
        or raw.get("livrable")
        or "Livrable a confirmer avec le manager"
    ).strip()
    complexity = str(raw.get("complexity", "MOYEN")).upper()
    if complexity not in ("SIMPLE", "MOYEN", "COMPLEXE"):
        complexity = "MOYEN"
    department = str(raw.get("department", "GENERAL") or "GENERAL").upper().strip()
    skills = raw.get("required_skills") or raw.get("skills") or []
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(",") if s.strip()]

    emp_id = (
        raw.get("assigned_employee_id")
        or raw.get("employee_id")
        or raw.get("assignee_id")
    )
    if emp_id is not None:
        emp_id = str(emp_id).strip()

    reason = (
        raw.get("assignment_reason")
        or raw.get("dispatch_reason")
        or raw.get("justification")
        or ""
    ).strip()

    est_hours = raw.get("estimated_duration_hours") or raw.get("duration_hours")
    est_bonus = raw.get("estimated_bonus_da") or raw.get("bonus_da")

    return {
        "title": title,
        "description": desc,
        "expected_deliverable": deliverable,
        "complexity": complexity,
        "department": department,
        "required_skills": skills,
        "assigned_employee_id": emp_id or None,
        "assigned_employee_name": (raw.get("assigned_employee_name") or raw.get("assignee_name") or "").strip(),
        "assigned_matricule": (raw.get("assigned_matricule") or raw.get("matricule") or "").strip(),
        "assignment_reason": reason,
        "estimated_duration_hours": est_hours,
        "estimated_bonus_da": est_bonus,
    }


def resolve_employee(db: Session, task: dict, roster: list[dict]) -> tuple[Employee | None, SpiDaily | None]:
    """Map agent-chosen id/name/matricule to an Employee row."""
    by_id = {r["employee_id"]: r for r in roster}
    eid = task.get("assigned_employee_id")
    if eid and eid in by_id:
        emp = db.query(Employee).filter(Employee.id == eid).first()
        if emp:
            return emp, _latest_spi(db, emp.id)

    matricule = task.get("assigned_matricule") or ""
    if matricule:
        emp = (
            db.query(Employee)
            .filter(Employee.matricule == matricule, Employee.is_deleted == False)
            .first()
        )
        if emp:
            return emp, _latest_spi(db, emp.id)

    name_hint = _norm(task.get("assigned_employee_name"))
    if name_hint:
        for r in roster:
            if name_hint in _norm(r["name"]) or _norm(r["name"]) in name_hint:
                emp = db.query(Employee).filter(Employee.id == r["employee_id"]).first()
                if emp:
                    return emp, _latest_spi(db, emp.id)

    return None, None


def _latest_spi(db: Session, employee_id) -> SpiDaily | None:
    return (
        db.query(SpiDaily)
        .filter(SpiDaily.employee_id == employee_id)
        .order_by(SpiDaily.date.desc())
        .first()
    )


def default_hours_bonus(complexity: str) -> tuple[int, int]:
    hours = {"SIMPLE": 2, "MOYEN": 4, "COMPLEXE": 8}.get(complexity, 4)
    bonus = {"SIMPLE": 2000, "MOYEN": 5000, "COMPLEXE": 12000}.get(complexity, 5000)
    return hours, bonus
