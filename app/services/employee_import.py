"""Employee import and normalization helpers."""
from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime
from typing import Optional


def _normalize_space(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = " ".join(str(value).replace("\xa0", " ").strip().split())
    return normalized or None


def _normalize_header(value: str) -> str:
    clean = _normalize_space(value or "") or ""
    clean = clean.lower()
    clean = clean.replace("é", "e").replace("è", "e").replace("ê", "e")
    clean = clean.replace("à", "a").replace("â", "a")
    clean = clean.replace("î", "i").replace("ï", "i")
    clean = clean.replace("ô", "o")
    clean = clean.replace("ù", "u").replace("û", "u")
    clean = clean.replace("ç", "c")
    clean = re.sub(r"[^a-z0-9]+", "_", clean)
    return clean.strip("_")


def _normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _parse_optional_date(value: Optional[str]) -> Optional[date]:
    clean = _normalize_space(value)
    if not clean or clean.lower() == "nan":
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(clean, fmt).date()
        except ValueError:
            continue
    return None


def _parse_optional_float(value: Optional[str]) -> Optional[float]:
    clean = _normalize_space(value)
    if not clean or clean.lower() == "nan":
        return None
    numeric = clean.replace(" ", "")
    if "," in numeric and "." in numeric:
        numeric = numeric.replace(".", "").replace(",", ".")
    elif "," in numeric:
        numeric = numeric.replace(",", ".")
    try:
        return float(numeric)
    except ValueError:
        return None


def _parse_bool(value: Optional[str], default: bool = True) -> bool:
    clean = (_normalize_space(value) or "").lower()
    if not clean:
        return default
    if clean in {"1", "true", "vrai", "yes", "oui", "active", "actif"}:
        return True
    if clean in {"0", "false", "faux", "no", "non", "inactive", "inactif"}:
        return False
    return default


def _parse_csv_rows(text: str) -> list[dict[str, str]]:
    sniffer = csv.Sniffer()
    try:
        dialect = sniffer.sniff(text[:2000], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";"

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    rows: list[dict[str, str]] = []
    for row in reader:
        clean = {
            _normalize_header(key): _normalize_space(value) or ""
            for key, value in row.items()
            if key
        }
        rows.append(clean)
    return rows


def parse_tabular_employee_file(filename: str, content: bytes) -> list[dict[str, str]]:
    lower_name = filename.lower()
    if lower_name.endswith((".xlsx", ".xls")):
        try:
            import openpyxl
        except ImportError as exc:
            raise ValueError("Le support Excel nécessite openpyxl.") from exc

        workbook = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        sheet = workbook.active
        rows_iter = sheet.iter_rows(values_only=True)
        try:
            headers = [str(cell or "") for cell in next(rows_iter)]
        except StopIteration:
            workbook.close()
            return []
        csv_lines = [";".join(headers)]
        for row in rows_iter:
            csv_lines.append(";".join(str(cell or "") for cell in row))
        workbook.close()
        return _parse_csv_rows("\n".join(csv_lines))

    if lower_name.endswith((".csv", ".txt")):
        for encoding in ("utf-8", "utf-8-sig", "cp1252", "iso-8859-1", "latin-1"):
            try:
                return _parse_csv_rows(content.decode(encoding))
            except UnicodeDecodeError:
                continue
        raise ValueError("Impossible de décoder le fichier. Encodage non reconnu.")

    raise ValueError(f"Format non supporté: {filename}. Formats acceptés: .csv, .xlsx, .xls")


def split_employee_name(raw_name: str, email: Optional[str] = None) -> tuple[str, str]:
    clean_name = _normalize_space(raw_name) or ""
    parts = clean_name.split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0].title(), ""

    email_tokens: list[str] = []
    if email and "@" in email:
        local_part = email.split("@", 1)[0]
        email_tokens = [_normalize_token(token) for token in re.split(r"[._-]+", local_part) if token]

    first_token = _normalize_token(parts[0])
    last_token = _normalize_token(parts[-1])
    email_hint = email_tokens[0] if email_tokens else ""

    if email_hint:
        if email_hint == first_token and email_hint != last_token:
            return parts[0].title(), " ".join(parts[1:]).upper()
        if email_hint == last_token and email_hint != first_token:
            return " ".join(parts[1:]).title(), parts[0].upper()

    alpha_parts = [part for part in parts if re.search(r"[A-Za-zÀ-ÿ]", part)]
    all_upper = bool(alpha_parts) and all(part == part.upper() for part in alpha_parts)
    if all_upper or parts[0] == parts[0].upper():
        return " ".join(parts[1:]).title(), parts[0].upper()

    return parts[0].title(), " ".join(parts[1:]).upper()


def normalize_import_employee_row(row: dict[str, str]) -> Optional[dict]:
    full_name = row.get("nom_de_l_employe") or row.get("nom_complet") or row.get("employee_name") or row.get("name")
    email = row.get("adresse_email_professionnelle") or row.get("email_professionnel") or row.get("email")
    phone = row.get("telephone_professionnel") or row.get("telephone") or row.get("phone")
    first_name = row.get("prenom")
    last_name = row.get("nom")

    if first_name or last_name:
        normalized_first = (_normalize_space(first_name) or "").title()
        normalized_last = (_normalize_space(last_name) or "").upper()
    elif full_name:
        normalized_first, normalized_last = split_employee_name(full_name, email)
    else:
        return None

    if not normalized_first and not normalized_last:
        return None

    active = _parse_bool(row.get("actif") or row.get("is_active"), default=True)
    raw_status = _normalize_space(row.get("status") or row.get("statut"))
    normalized_status = "ACTIVE"
    if raw_status:
        lower = raw_status.lower()
        if lower in {"cancel", "cancelled", "canceled", "terminated", "resilie", "resiliee"}:
            normalized_status = "TERMINATED"
        elif lower in {"inactive", "inactif"}:
            normalized_status = "INACTIVE"
        elif lower in {"on_leave", "leave", "conge"}:
            normalized_status = "ON_LEAVE"
        else:
            normalized_status = "ACTIVE"
    elif not active:
        normalized_status = "INACTIVE"

    return {
        "employee_number": _normalize_space(row.get("matricule") or row.get("employee_number") or row.get("employee_id")),
        "first_name": normalized_first,
        "last_name": normalized_last,
        "email": _normalize_space(email),
        "phone": _normalize_space(phone),
        "professional_address": _normalize_space(row.get("adresse_professionnelle") or row.get("professional_address")),
        "activities": _normalize_space(row.get("activites") or row.get("activities")),
        "hire_date": _parse_optional_date(row.get("date_embauche") or row.get("hire_date")),
        "upcoming_activity_due_date": _parse_optional_date(row.get("date_limite_de_l_activite_a_venir") or row.get("upcoming_activity_due_date")),
        "department": _normalize_space(row.get("departement") or row.get("department")),
        "position": _normalize_space(row.get("poste") or row.get("position")),
        "manager_name": _normalize_space(row.get("manager")),
        "mentor_name": _normalize_space(row.get("mentor")),
        "company": _normalize_space(row.get("societe") or row.get("company")),
        "status": normalized_status,
        "is_active": active,
        "base_salary": _parse_optional_float(row.get("salaire_base") or row.get("base_salary")),
        "social_security_number": _normalize_space(row.get("numero_securite_sociale") or row.get("social_security_number")),
        "source_name": _normalize_space(full_name),
    }
