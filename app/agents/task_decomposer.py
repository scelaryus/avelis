"""SPI 360 agent: decompose DAF daily needs and dispatch tasks to employees."""
from __future__ import annotations

import json
import re

from openai import OpenAI

from app.agents.llm import MODEL, OPENROUTER_API_KEY, OPENROUTER_BASE_URL
from app.services.spi_task_assignment import (
    build_employee_roster,
    parse_agent_task,
    roster_json_for_agent,
)

client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=OPENROUTER_API_KEY)

SYSTEM_PROMPT = """Tu es l'Agent Orchestrateur SPI 360 du systeme Avelis ERP (promoteur immobilier, Algerie).
Le DAF soumet un besoin du jour en langage naturel. Tu recois aussi la liste JSON des employes actifs.

Tu dois en UNE seule analyse:
1. COMPRENDRE le besoin: extraire chaque action operationnelle distincte (relances, rapports, validations, mises a jour, etc.).
2. DECOMPOSER en 2 a 8 taches concretes, chacune realisable par UN employe en UNE journee maximum.
   - Ne fusionne pas des sujets differents (ex: ADV + compta + RH = au moins 3 taches).
   - Titres specifiques et actionnables (pas "traiter le besoin").
3. DISPATCHER chaque tache vers exactement UN employe de la liste fournie.
   - Copie l'UUID tel quel dans assigned_employee_id (champ employee_id dans la liste).
   - Repartis le travail entre plusieurs personnes quand le besoin couvre plusieurs metiers.
   - Ne assigne pas toutes les taches au meme employe sauf si le besoin ne concerne qu'un seul profil.
   - Tiens compte du departement, poste, SPI et open_task_count pour equilibrer la charge.
4. JUSTIFIER chaque choix dans assignment_reason (competence, disponibilite, SPI).

Pour chaque tache, retourne un objet JSON avec TOUS ces champs:
- title (string, max 120 caracteres)
- description (string, etapes concretes)
- expected_deliverable (string, preuve de fin)
- complexity: SIMPLE | MOYEN | COMPLEXE
- department: FINANCE | ADV | RH | JURIDIQUE | PROJETS | BIM | STOCK | GENERAL
- required_skills (array de strings)
- assigned_employee_id (string UUID — obligatoire, doit exister dans la liste)
- assigned_employee_name (string — nom pour verification)
- assignment_reason (string, 1-3 phrases en francais)
- estimated_duration_hours (number)
- estimated_bonus_da (number, indicatif: 2000 SIMPLE, 5000 MOYEN, 12000 COMPLEXE)

Reponds UNIQUEMENT avec un array JSON valide. Pas de markdown, pas de texte avant ou apres."""


def _parse_json_array(content: str) -> list | None:
    content = (content or "").strip()
    if content.startswith("```"):
        parts = content.split("```")
        content = parts[1] if len(parts) > 1 else content
        if content.lstrip().lower().startswith("json"):
            content = content[4:].lstrip()
    match = re.search(r"\[[\s\S]*\]", content)
    if match:
        content = match.group(0)
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return None
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "tasks" in data:
        tasks = data["tasks"]
        return tasks if isinstance(tasks, list) else None
    if isinstance(data, dict):
        return [data]
    return None


def _call_agent(need_text: str, roster: list[dict], *, retry: bool = False) -> list | None:
    team_json = roster_json_for_agent(roster)
    extra = ""
    if retry:
        extra = (
            "\n\nATTENTION: ta precedente reponse etait invalide. "
            "Retourne un array JSON strict avec assigned_employee_id pour chaque tache "
            "(UUID copies depuis la liste employes)."
        )

    user_message = (
        f"=== EMPLOYES ACTIFS (JSON) ===\n{team_json}\n\n"
        f"=== BESOIN DU JOUR ===\n{need_text}\n\n"
        "Analyse, decompose et dispatch chaque tache vers un employe de la liste."
        f"{extra}"
    )

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        max_tokens=4000,
        temperature=0.25,
    )
    content = response.choices[0].message.content or ""
    return _parse_json_array(content)


async def decompose_and_dispatch(need_text: str, db) -> list[dict]:
    """
    Agent-driven decomposition + dispatch.
    Returns parsed tasks with assigned_employee_id set by the LLM.
    Raises RuntimeError if the agent cannot produce valid output.
    """
    need_text = (need_text or "").strip()
    if not need_text:
        return []

    if db is None:
        raise RuntimeError("Base de donnees requise pour le dispatch agent")

    roster = build_employee_roster(db)
    if not roster:
        raise RuntimeError("Aucun employe actif — impossible de dispatcher")

    last_error = None
    for attempt in range(2):
        try:
            raw_list = _call_agent(need_text, roster, retry=(attempt == 1))
            if not raw_list:
                last_error = "Reponse agent vide ou JSON invalide"
                continue

            tasks = [parse_agent_task(item, need_text) for item in raw_list]
            valid_ids = {r["employee_id"] for r in roster}

            dispatched = [t for t in tasks if t.get("assigned_employee_id") in valid_ids]
            if not dispatched:
                last_error = "Aucune tache avec assigned_employee_id valide"
                continue

            return dispatched
        except Exception as e:
            last_error = str(e)
            print(f"Agent decompose+dispatch attempt {attempt + 1} failed: {e}")

    raise RuntimeError(last_error or "Echec agent decomposition/dispatch")
