"""Task planning helpers — AI-powered assignment via LangGraph agent (GFI v7).

The user writes a free-text message (possibly containing many tasks).
An AI agent:
  1. Splits the message into individual tasks
  2. Generates a concise title + résumé for each task
  3. Selects the best-fit employee from the roster using semantic
     understanding of each person's role, department, and position
  4. Load-balances so one person doesn't receive every task

GFI v7 integration:
  - Creates TacheSPI records (SPI-tracked tasks) instead of HRTask
  - Tasks feed into C1 (Execution) and C2 (Quality) SPI components
  - Supports OffrePerformance (bonus/malus) negotiation per task
"""
from __future__ import annotations

import json
import uuid
import structlog
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from app.models.hr import Employee, HRTask
from app.models.planification import (
    TacheSPI, StatutTache, PrioriteTache, SourceTache,
)

logger = structlog.get_logger(__name__)

RATING_PERCENTAGES = {
    1: Decimal("-0.03"),
    2: Decimal("-0.01"),
    3: Decimal("0.00"),
    4: Decimal("0.01"),
    5: Decimal("0.03"),
}

# Map from AI required_role to SourceTache
_ROLE_TO_SOURCE = {
    "management": SourceTache.OBJECTIF_CEO,
    "hr": SourceTache.OBJECTIF_MANAGER,
    "operations": SourceTache.OBJECTIF_MANAGER,
    "finance": SourceTache.OBJECTIF_MANAGER,
    "sales": SourceTache.CRM,
    "marketing": SourceTache.OBJECTIF_MANAGER,
    "sav": SourceTache.MAINTENANCE,
    "security": SourceTache.MAINTENANCE,
    "support": SourceTache.OBJECTIF_MANAGER,
}

# Map from AI required_role to PrioriteTache
_ROLE_TO_PRIORITY = {
    "management": PrioriteTache.ELEVEE,
    "security": PrioriteTache.CRITIQUE,
    "sav": PrioriteTache.ELEVEE,
}

# ── System prompt for the AI task-planning agent ────────────────────────────

_SYSTEM_PROMPT = """\
You are an intelligent Task Planning Agent for AVELIS PROMOTION, an Algerian
real-estate company. You receive:

1. A free-text message from a manager that may contain ONE or MANY tasks
   (separated by line breaks, bullet points, semicolons, or just natural
    language).
2. A JSON roster of active employees with their id, name, position,
   department, and function_category.

Your job:
• Parse the message and extract every distinct task.
• For each task produce:
  - "title": a short (≤12 words) action-oriented title in the SAME LANGUAGE
    as the original text.
  - "summary": a 1-2 sentence résumé of what needs to be done (same language).
  - "employee_id": the id of the BEST employee for this task, chosen by
    matching the task's domain to the employee's position / department /
    function_category.  Use your understanding of the words to decide.
  - "required_role": one of finance, hr, sales, marketing, operations,
    management, sav, security, support — whichever domain best fits.
  - "priority": one of CRITIQUE, ELEVEE, NORMALE, BASSE — based on urgency.
  - "deadline_days": estimated number of days to complete (integer).
  - "criteres_acceptation": 1-2 sentences describing what constitutes
    successful completion (measurable criteria).
  - "reasoning": one sentence explaining WHY this employee was chosen.

CRITICAL domain distinctions — MARKETING vs SALES:
• MARKETING tasks: campagnes marketing, branding, identité visuelle, contenu,
  publications, réseaux sociaux, stratégie de marque, publicité, communication,
  design graphique, événements promotionnels, newsletters, SEO/SEM.
  → Assign to employees with function_category=MARKETING or "Marketing" in
    their position.  required_role = "marketing".
• SALES tasks: prospection, leads, clients, devis, appels d'offres, relances,
  facturation client, contrats de vente, pipeline commercial, closing.
  → Assign to employees with function_category=COMMERCIAL or "Sales" in
    their position.  required_role = "sales".
Do NOT confuse these two domains.  A "campagne marketing" is MARKETING, not
sales.  A "relance client" is SALES, not marketing.

Other domain hints:
• Finance / comptabilité / factures fournisseur → function_category=MANAGEMENT
  or position containing "Finance"
• RH / recrutement / paie → function_category=SUPPORT or position containing
  "RH" / "Office Manager"
• Nettoyage / sécurité / maintenance → function_category=SUPPORT
• Stock / achats / approvisionnement / logistique → function_category=OPERATIONS
• Réclamations / SAV / relation clients post-vente → function_category=SAV

IMPORTANT load-balancing rules:
• NEVER assign all tasks to the same employee unless there is truly only one
  person whose role fits.
• Spread tasks among qualified employees.  If two employees are equally
  qualified, prefer the one who has fewer tasks already assigned in this batch.
• If no employee clearly matches, pick the closest fit — do NOT leave
  employee_id empty.

Reply with a JSON object:  { "tasks": [ … ] }
Nothing else.  No markdown fences.
"""


def _build_employee_roster(employees: Iterable[Employee]) -> list[dict]:
    """Build a compact roster for the LLM prompt."""
    roster = []
    for emp in employees:
        roster.append({
            "id": emp.id,
            "name": f"{emp.first_name} {emp.last_name}".strip(),
            "position": emp.position or None,
            "department": emp.department or None,
            "function_category": getattr(emp, "function_category", None),
        })
    return roster


async def plan_tasks_from_text(
    raw_text: str,
    employees: Iterable[Employee],
    plan_date: date,
    tenant_id: str = "",
    assigneur_id: str = "",
) -> list[dict]:
    """Use the AI agent to split, summarise, and assign tasks.

    Returns a list of dicts with TacheSPI-compatible data.
    """
    from app.services.llm_graph import invoke_json_agent

    employees_list = list(employees)
    if not employees_list:
        return []

    roster = _build_employee_roster(employees_list)
    emp_by_id = {e.id: e for e in employees_list}

    user_prompt = (
        f"Manager's message:\n\"\"\"\n{raw_text}\n\"\"\"\n\n"
        f"Employee roster ({len(roster)} people):\n"
        f"{json.dumps(roster, ensure_ascii=False, indent=1)}"
    )

    try:
        result = await invoke_json_agent(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=4096,
        )
        ai_tasks = result["parsed_json"].get("tasks", [])
    except Exception as exc:
        logger.error("ai_task_planner_failed", error=str(exc))
        # Fallback: single task with first employee that has a position
        fallback_emp = next(
            (e for e in employees_list if e.position), employees_list[0]
        )
        return [
            {
                "title": raw_text[:80].strip().capitalize(),
                "description": raw_text,
                "plan_date": plan_date,
                "required_role": "operations",
                "employee": fallback_emp,
                "ai_reasoning": f"AI agent failed ({exc}), fallback assignment.",
                # TacheSPI fields
                "tache_spi": _build_tache_spi(
                    titre=raw_text[:80].strip().capitalize(),
                    description=raw_text,
                    employee=fallback_emp,
                    plan_date=plan_date,
                    tenant_id=tenant_id,
                    assigneur_id=assigneur_id,
                    source=SourceTache.OBJECTIF_MANAGER,
                    priorite=PrioriteTache.NORMALE,
                    criteres_acceptation=None,
                    deadline_days=7,
                ),
            }
        ]

    # Map AI output back to Employee objects
    tasks = []
    batch_counts: Counter = Counter()

    for t in ai_tasks:
        emp_id = t.get("employee_id", "")
        employee = emp_by_id.get(emp_id)

        # If the AI returned an invalid id, pick the least-loaded employee
        if not employee:
            least_loaded = min(
                employees_list,
                key=lambda e: batch_counts.get(e.id, 0),
            )
            employee = least_loaded

        batch_counts[employee.id] += 1

        required_role = t.get("required_role", "operations")
        source = _ROLE_TO_SOURCE.get(required_role, SourceTache.OBJECTIF_MANAGER)
        priority_str = t.get("priority", "NORMALE")
        try:
            priorite = PrioriteTache(priority_str)
        except (ValueError, KeyError):
            priorite = _ROLE_TO_PRIORITY.get(required_role, PrioriteTache.NORMALE)

        deadline_days = t.get("deadline_days", 7)

        tasks.append({
            "title": (t.get("title") or raw_text[:80]).strip(),
            "description": t.get("summary") or raw_text,
            "plan_date": plan_date,
            "required_role": required_role,
            "employee": employee,
            "ai_reasoning": t.get("reasoning", ""),
            # TacheSPI record ready to be added to DB
            "tache_spi": _build_tache_spi(
                titre=(t.get("title") or raw_text[:80]).strip(),
                description=t.get("summary") or raw_text,
                employee=employee,
                plan_date=plan_date,
                tenant_id=tenant_id,
                assigneur_id=assigneur_id,
                source=source,
                priorite=priorite,
                criteres_acceptation=t.get("criteres_acceptation"),
                deadline_days=deadline_days,
            ),
        })

    return tasks


def _build_tache_spi(
    titre: str,
    description: str,
    employee: Employee,
    plan_date: date,
    tenant_id: str,
    assigneur_id: str,
    source: SourceTache,
    priorite: PrioriteTache,
    criteres_acceptation: str | None,
    deadline_days: int,
) -> TacheSPI:
    """Build a TacheSPI record from AI output."""
    return TacheSPI(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id or employee.tenant_id,
        titre=titre,
        description=description,
        assignee_id=employee.id,
        assigneur_id=assigneur_id or None,
        source_type=source,
        priorite=priorite,
        statut=StatutTache.ASSIGNEE,
        date_debut_prevue=plan_date,
        date_fin_prevue=plan_date + timedelta(days=max(deadline_days, 1)),
        criteres_acceptation=criteres_acceptation,
    )


def apply_salary_adjustment(employee: Employee, task: HRTask, rating: int) -> Decimal:
    current_salary = Decimal(str(employee.base_salary or 0))
    new_adjustment = (current_salary * RATING_PERCENTAGES[rating]).quantize(Decimal("0.01"), ROUND_HALF_UP)
    task.salary_adjustment_amount = new_adjustment
    task.salary_adjustment_applied = True
    return new_adjustment
