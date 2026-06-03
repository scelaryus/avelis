"""
GFI v7.0 — Pydantic response/request schemas for all API endpoints.
"""
from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ── Generic wrappers ─────────────────────────────────────────────────────────
class Meta(BaseModel):
    total: int = 0
    limit: int = 50
    offset: int = 0

class ApiResponse(BaseModel):
    data: Any
    meta: Meta = Meta()
    errors: list[str] = []

# ── Auth ─────────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

# ── Foundation ───────────────────────────────────────────────────────────────
class EntityOut(BaseModel):
    id: str; code: str; legal_name: str; legal_form: str; status: str
    cnas_regime: str | None = None; nif: str | None = None
    class Config: from_attributes = True

class ProjectOut(BaseModel):
    id: str; code: str; name: str; status: str; company_id: str
    client_count: int | None = None; terrain_cost_estimate: str | None = None
    class Config: from_attributes = True

class AssociateOut(BaseModel):
    id: str; canonical_name: str; is_founder: bool; role: str | None = None
    class Config: from_attributes = True

class AliasResolveRequest(BaseModel):
    input_name: str
    entity_type: str = "PROJECT"  # PROJECT, ASSOCIATE, COMPANY

class AliasResolveResponse(BaseModel):
    status: str  # EXACT, FUZZY, BLOCKED
    canonical_name: str | None = None
    confidence: float = 0
    suggestions: list[dict] = []

class FormulaireResponse(BaseModel):
    field_responses: dict

# ── Finance ──────────────────────────────────────────────────────────────────
class CffCalculateRequest(BaseModel):
    montant_ht: Decimal
    emitter_entity_id: str
    receiver_entity_id: str
    invoice_date: date

class CffResult(BaseModel):
    tva: str; tap: str; ibs_base: str; ibs: str; stamp_duty: str
    cff_total: str
    distribution: list[dict]

class CcaWithdrawRequest(BaseModel):
    entity_id: str
    amount: Decimal
    justification: str

# ── ADV ──────────────────────────────────────────────────────────────────────
class LotLockResponse(BaseModel):
    lot_id: str; locked_by: str; expires_at: str; status: str

class PaymentRequest(BaseModel):
    dossier_id: str; type_rf: str; mode_reglement: str
    montant: Decimal; reference: str | None = None

class EtatDetailleRequest(BaseModel):
    cheque_ref: str; montant_global: Decimal
    lignes: list[dict]

class DossierTransitionRequest(BaseModel):
    target_state: str

# ── Operations ───────────────────────────────────────────────────────────────
class OperationOut(BaseModel):
    id: str; code_operation: str; intitule: str; categorie: str
    statut: str; montant_engage_ttc: str | None = None
    class Config: from_attributes = True

class TaskUpdateRequest(BaseModel):
    avancement_pct: Decimal | None = None
    date_debut_reelle: date | None = None
    date_fin_reelle: date | None = None
    notes: str | None = None
