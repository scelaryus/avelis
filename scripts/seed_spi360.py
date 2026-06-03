"""Seed SPI 360 data: daily scores for 60 days, monthly aggregates, tasks, deliverables, configs."""
import random
from decimal import Decimal
from datetime import date, timedelta, datetime, timezone
from app.db import SessionLocal
from app.models.core import (
    Employee, Company, SpiDaily, SpiMonthly, SpiConfig, SpiTask, SpiDeliverable,
)

random.seed(42)
db = SessionLocal()

# ── Seed SPI Configs per position ──
positions_config = {
    "Agent Commercial": {"planification": 30, "qualite": 20, "comportement": 20, "performance": 30},
    "Comptable": {"planification": 30, "qualite": 30, "comportement": 25, "performance": 15},
    "Chef de Chantier": {"planification": 35, "qualite": 25, "comportement": 20, "performance": 20},
    "Gestionnaire ADV": {"planification": 30, "qualite": 25, "comportement": 25, "performance": 20},
    "DRH": {"planification": 25, "qualite": 25, "comportement": 25, "performance": 25},
}
db.query(SpiConfig).delete()
default_co = db.query(Company).first()
for pos, weights in positions_config.items():
    db.add(SpiConfig(company_id=default_co.id, job_position=pos, pillar_weights=weights))
db.commit()
print(f"Seeded {len(positions_config)} SPI configs")

# ── Seed daily SPI for all employees, last 60 days ──
employees = db.query(Employee).filter(Employee.is_deleted == False).all()
db.query(SpiDaily).delete()
db.query(SpiMonthly).delete()
db.query(SpiTask).delete()
db.query(SpiDeliverable).delete()
db.commit()

today = date(2026, 3, 26)
daily_count = 0

for emp in employees:
    base_spi = random.uniform(55, 95)
    streak_inactive = 0

    for day_offset in range(60):
        d = today - timedelta(days=59 - day_offset)
        if d.weekday() >= 5:
            continue

        p1 = min(max(base_spi + random.uniform(-10, 15), 0), 150)
        p2 = min(max(base_spi + random.uniform(-8, 10), 0), 150)
        p3 = min(max(100 - random.uniform(0, 25), 0), 100)
        p4 = min(max(base_spi + random.uniform(-15, 20), 0), 150)

        cfg = positions_config.get(emp.position, {"planification": 30, "qualite": 25, "comportement": 25, "performance": 20})
        w1, w2, w3, w4 = cfg["planification"] / 100, cfg["qualite"] / 100, cfg["comportement"] / 100, cfg["performance"] / 100

        spi_raw = Decimal(str(round(p1 * w1 + p2 * w2 + p3 * w3 + p4 * w4, 2)))
        tasks_done = random.randint(0, 4)
        is_inactive = tasks_done == 0 and random.random() < 0.1
        streak_inactive = streak_inactive + 1 if is_inactive else 0
        counter_bonus = tasks_done * random.randint(1, 3) if tasks_done > 0 else 0
        counter_malus = 10 if is_inactive else 0
        spi_adj = spi_raw + Decimal(str(counter_bonus)) - Decimal(str(counter_malus))

        db.add(SpiDaily(
            company_id=emp.company_id, employee_id=emp.id, date=d,
            pillar_planification=Decimal(str(round(p1, 2))),
            pillar_qualite=Decimal(str(round(p2, 2))),
            pillar_comportement=Decimal(str(round(p3, 2))),
            pillar_performance=Decimal(str(round(p4, 2))),
            counter_bonus=counter_bonus, counter_malus=counter_malus,
            spi_raw=spi_raw, spi_adjusted=spi_adj, spi_final=max(spi_adj, Decimal("0")),
            tasks_completed=tasks_done, deliverables_validated=random.randint(0, 2),
            is_inactive_day=is_inactive, consecutive_inactive_days=streak_inactive,
        ))
        daily_count += 1

    # Seed tasks
    task_titles = [
        "Rapprochement bancaire", "Relance dossier ADV", "Mise a jour BIM",
        "Preparation G50", "Suivi chantier", "Analyse CFF", "Validation situation",
        "Classement GED", "Verification paie", "Rapport mensuel",
    ]
    for _ in range(random.randint(5, 12)):
        task_date = today - timedelta(days=random.randint(0, 25))
        due = task_date + timedelta(days=random.randint(1, 5))
        completed = task_date + timedelta(days=random.randint(0, 4))
        status = random.choice(["COMPLETEE", "COMPLETEE", "COMPLETEE", "EN_RETARD", "ASSIGNEE"])
        val_algo = "PASS" if status == "COMPLETEE" else "PENDING"
        val_mgr = random.choice(["VALIDE", "VALIDE", "PENDING"]) if status == "COMPLETEE" else "PENDING"
        counts = val_algo == "PASS" and val_mgr == "VALIDE"
        db.add(SpiTask(
            company_id=emp.company_id, employee_id=emp.id,
            title=random.choice(task_titles),
            date_assigned=task_date, date_due=due,
            date_completed=completed if status in ("COMPLETEE", "EN_RETARD") else None,
            status=status, validation_algo=val_algo, validation_manager=val_mgr,
            counts_toward_spi=counts,
            spi_points=Decimal(str(random.randint(5, 15))) if counts else Decimal("0"),
        ))

    # Seed deliverables
    deliv_titles = ["Rapport mensuel", "Dossier client", "PV reception", "Fiche technique", "Analyse budget"]
    quality_map = {
        "VALIDE_SANS_RETOUR": 100, "VALIDE_AVEC_RETOUR": 70,
        "REFUSE_PUIS_CORRIGE": 50, "REFUSE_DEFINITIF": 0,
    }
    for _ in range(random.randint(2, 6)):
        qs = random.choice(["VALIDE_SANS_RETOUR", "VALIDE_SANS_RETOUR", "VALIDE_AVEC_RETOUR", "REFUSE_PUIS_CORRIGE"])
        db.add(SpiDeliverable(
            company_id=emp.company_id, employee_id=emp.id,
            title=random.choice(deliv_titles),
            date_submitted=today - timedelta(days=random.randint(0, 25)),
            quality_status=qs, quality_score=Decimal(str(quality_map[qs])),
        ))

db.commit()
print(f"Seeded {daily_count} daily SPI records for {len(employees)} employees")

# ── Aggregate monthly ──
for emp in employees:
    for period in ["2026-01", "2026-02", "2026-03"]:
        y, m = int(period[:4]), int(period[5:])
        next_m = m + 1 if m < 12 else 1
        next_y = y if m < 12 else y + 1
        dailies = db.query(SpiDaily).filter(
            SpiDaily.employee_id == emp.id,
            SpiDaily.date >= date(y, m, 1),
            SpiDaily.date < date(next_y, next_m, 1),
        ).all()
        if not dailies:
            continue
        scores = [float(d.spi_final) for d in dailies]
        avg = sum(scores) / len(scores)
        inactive_days = sum(1 for d in dailies if d.is_inactive_day)

        bonus_pct = Decimal("0")
        malus_pct = Decimal("0")
        tier = "STANDARD"
        if avg >= 130:
            bonus_pct = Decimal("50"); tier = "EXCEPTIONNEL"
        elif avg >= 110:
            bonus_pct = Decimal("35"); tier = "EXCELLENT"
        elif avg >= 90:
            bonus_pct = Decimal("20"); tier = "BON"
        elif avg >= 70:
            tier = "STANDARD"
        elif avg >= 50:
            malus_pct = Decimal("15"); tier = "INSUFFISANT"
        else:
            malus_pct = Decimal("30"); tier = "CRITIQUE"

        bonus_amt = Decimal(str(emp.salary_base)) * bonus_pct / 100
        malus_amt = Decimal(str(emp.salary_base)) * malus_pct / 100

        db.add(SpiMonthly(
            company_id=emp.company_id, employee_id=emp.id, period=period,
            avg_spi=Decimal(str(round(avg, 2))),
            min_spi=Decimal(str(round(min(scores), 2))),
            max_spi=Decimal(str(round(max(scores), 2))),
            days_counted=len(dailies), days_inactive=inactive_days,
            bonus_tier=tier if bonus_pct > 0 else None,
            bonus_percentage=bonus_pct, bonus_amount=bonus_amt,
            malus_tier=tier if malus_pct > 0 else None,
            malus_percentage=malus_pct, malus_amount=malus_amt,
            salary_freeze_active=inactive_days >= 5,
            is_termination_candidate=False,
            status="VALIDE" if period != "2026-03" else "CALCULE",
        ))

db.commit()
monthly_count = db.query(SpiMonthly).count()
print(f"Seeded {monthly_count} monthly SPI aggregates")

# Summary
task_count = db.query(SpiTask).count()
deliv_count = db.query(SpiDeliverable).count()
print(f"Tasks: {task_count}, Deliverables: {deliv_count}")

db.close()
print("Done!")
