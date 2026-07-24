"""Action Engine REST API — SDD §12.10.

Rules CRUD (admin only):
  POST   /v1/actions/rules
  GET    /v1/actions/rules
  GET    /v1/actions/rules/{id}
  PUT    /v1/actions/rules/{id}
  DELETE /v1/actions/rules/{id}
  POST   /v1/actions/rules/{id}/channels/{channel_id}   — bind channel
  DELETE /v1/actions/rules/{id}/channels/{channel_id}   — unbind channel

Channels CRUD (admin only):
  POST   /v1/actions/channels
  GET    /v1/actions/channels
  PUT    /v1/actions/channels/{id}
  DELETE /v1/actions/channels/{id}

Audit log (admin + operator read):
  GET    /v1/actions/log

SOP template factory (admin only):
  POST   /v1/actions/rules/from-template   — instantiate a pre-defined SOP template

Authorization: standard user JWT via require_tenant_user dependency (same
as backoffice).  RLS enforces tenant isolation — a rule belonging to
Tenant A can never be read or modified by Tenant B.
"""

from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

import jwt

from cloud import config
from cloud.db import user_conn

router = APIRouter(prefix="/v1/actions", tags=["actions"])

_bearer = HTTPBearer()

VALID_RULE_TYPES = (
    "threshold",
    "sop_staff_absent_checkout",
    "sop_late_opening",
    "sop_unattended_customer",
)
VALID_CHANNEL_TYPES = ("slack", "telegram", "email", "whatsapp")


# ── Auth dependency ───────────────────────────────────────────────────────────

def _require_user(
    creds: HTTPAuthorizationCredentials = Security(_bearer),
) -> dict:
    try:
        return jwt.decode(
            creds.credentials, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM]
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "token_expired")
    except jwt.PyJWTError:
        raise HTTPException(401, "invalid_token")


def _require_admin(token: dict = Depends(_require_user)) -> dict:
    if token.get("role") != "admin":
        raise HTTPException(403, "admin_required")
    return token


# ── Request / Response models ─────────────────────────────────────────────────

class RuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    rule_type: str
    site_id: Optional[str] = None
    zone_id: Optional[str] = None
    threshold_value: Optional[int] = None
    threshold_window_minutes: Optional[int] = None
    business_hours_start: Optional[str] = None  # "HH:MM"
    business_hours_end: Optional[str] = None
    enabled: bool = True


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    rule_type: Optional[str] = None
    site_id: Optional[str] = None
    zone_id: Optional[str] = None
    threshold_value: Optional[int] = None
    threshold_window_minutes: Optional[int] = None
    business_hours_start: Optional[str] = None
    business_hours_end: Optional[str] = None
    enabled: Optional[bool] = None


class ChannelCreate(BaseModel):
    name: str
    channel_type: str
    config_json: Dict[str, Any] = {}
    enabled: bool = True
    whatsapp_cost_per_conversation_usd: Optional[float] = None


class ChannelUpdate(BaseModel):
    name: Optional[str] = None
    channel_type: Optional[str] = None
    config_json: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None
    whatsapp_cost_per_conversation_usd: Optional[float] = None


class SopTemplateRequest(BaseModel):
    template: str   # 'staff_absent_checkout' | 'late_opening' | 'unattended_customer'
    name: str
    site_id: Optional[str] = None
    zone_id: Optional[str] = None
    threshold_value: Optional[int] = None
    threshold_window_minutes: int = 15
    business_hours_start: Optional[str] = None
    business_hours_end: Optional[str] = None


# ── SOP template defaults ─────────────────────────────────────────────────────

_SOP_DEFAULTS: Dict[str, Dict] = {
    "staff_absent_checkout": {
        "rule_type": "sop_staff_absent_checkout",
        "threshold_window_minutes": 15,
        "description": "SOP: Personal ausente en zona de caja durante horario de negocio.",
    },
    "late_opening": {
        "rule_type": "sop_late_opening",
        "threshold_window_minutes": 15,
        "description": "SOP: Apertura tardía de tienda — sin actividad tras inicio de horario.",
    },
    "unattended_customer": {
        "rule_type": "sop_unattended_customer",
        "threshold_window_minutes": 10,
        "description": "SOP: Cliente sin atender por más de N minutos.",
    },
}


# ── Rules endpoints ───────────────────────────────────────────────────────────

@router.post("/rules", status_code=201)
def create_rule(body: RuleCreate, token: dict = Depends(_require_admin)) -> Dict:
    if body.rule_type not in VALID_RULE_TYPES:
        raise HTTPException(422, f"invalid rule_type; valid: {VALID_RULE_TYPES}")
    with user_conn(token) as cur:
        cur.execute(
            """
            INSERT INTO action_rules
                (tenant_id, site_id, zone_id, name, description, rule_type,
                 threshold_value, threshold_window_minutes,
                 business_hours_start, business_hours_end, enabled, created_by)
            VALUES
                (%(tid)s, %(sid)s, %(zid)s, %(name)s, %(desc)s, %(rt)s,
                 %(tv)s, %(tw)s, %(bhs)s::time, %(bhe)s::time, %(en)s, %(uid)s)
            RETURNING id::text, name, rule_type, enabled, created_at::text
            """,
            {
                "tid": token["tid"],
                "sid": body.site_id,
                "zid": body.zone_id,
                "name": body.name,
                "desc": body.description,
                "rt": body.rule_type,
                "tv": body.threshold_value,
                "tw": body.threshold_window_minutes,
                "bhs": body.business_hours_start,
                "bhe": body.business_hours_end,
                "en": body.enabled,
                "uid": token["sub"],
            },
        )
        return dict(cur.fetchone())


@router.get("/rules")
def list_rules(token: dict = Depends(_require_user)) -> List[Dict]:
    with user_conn(token) as cur:
        cur.execute(
            """
            SELECT id::text, name, rule_type, site_id::text, zone_id::text,
                   threshold_value, threshold_window_minutes,
                   business_hours_start::text, business_hours_end::text,
                   enabled, created_at::text
            FROM action_rules
            ORDER BY created_at DESC
            """
        )
        return [dict(r) for r in cur.fetchall()]


@router.get("/rules/{rule_id}")
def get_rule(rule_id: str, token: dict = Depends(_require_user)) -> Dict:
    with user_conn(token) as cur:
        cur.execute(
            "SELECT id::text, name, rule_type, description, site_id::text, zone_id::text, "
            "threshold_value, threshold_window_minutes, business_hours_start::text, "
            "business_hours_end::text, enabled, created_at::text FROM action_rules WHERE id = %s",
            (rule_id,),
        )
        row = cur.fetchone()
    if row is None:
        raise HTTPException(404, "rule_not_found")
    return dict(row)


@router.put("/rules/{rule_id}")
def update_rule(rule_id: str, body: RuleUpdate, token: dict = Depends(_require_admin)) -> Dict:
    if body.rule_type and body.rule_type not in VALID_RULE_TYPES:
        raise HTTPException(422, "invalid rule_type")
    with user_conn(token) as cur:
        cur.execute(
            """
            UPDATE action_rules
            SET name                    = COALESCE(%(name)s, name),
                description             = COALESCE(%(desc)s, description),
                rule_type               = COALESCE(%(rt)s, rule_type),
                site_id                 = COALESCE(%(sid)s::uuid, site_id),
                zone_id                 = COALESCE(%(zid)s::uuid, zone_id),
                threshold_value         = COALESCE(%(tv)s, threshold_value),
                threshold_window_minutes= COALESCE(%(tw)s, threshold_window_minutes),
                business_hours_start    = COALESCE(%(bhs)s::time, business_hours_start),
                business_hours_end      = COALESCE(%(bhe)s::time, business_hours_end),
                enabled                 = COALESCE(%(en)s, enabled),
                updated_at              = now()
            WHERE id = %s
            RETURNING id::text, name, rule_type, enabled, updated_at::text
            """,
            {
                "name": body.name,
                "desc": body.description,
                "rt": body.rule_type,
                "sid": body.site_id,
                "zid": body.zone_id,
                "tv": body.threshold_value,
                "tw": body.threshold_window_minutes,
                "bhs": body.business_hours_start,
                "bhe": body.business_hours_end,
                "en": body.enabled,
            },
            (rule_id,),
        )
        row = cur.fetchone()
    if row is None:
        raise HTTPException(404, "rule_not_found")
    return dict(row)


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: str, token: dict = Depends(_require_admin)) -> None:
    with user_conn(token) as cur:
        cur.execute("DELETE FROM action_rules WHERE id = %s", (rule_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "rule_not_found")


@router.post("/rules/{rule_id}/channels/{channel_id}", status_code=204)
def bind_channel(rule_id: str, channel_id: str, token: dict = Depends(_require_admin)) -> None:
    with user_conn(token) as cur:
        cur.execute(
            "INSERT INTO action_rule_channels (rule_id, channel_id) VALUES (%s, %s) "
            "ON CONFLICT DO NOTHING",
            (rule_id, channel_id),
        )


@router.delete("/rules/{rule_id}/channels/{channel_id}", status_code=204)
def unbind_channel(rule_id: str, channel_id: str, token: dict = Depends(_require_admin)) -> None:
    with user_conn(token) as cur:
        cur.execute(
            "DELETE FROM action_rule_channels WHERE rule_id = %s AND channel_id = %s",
            (rule_id, channel_id),
        )


# ── SOP template factory ──────────────────────────────────────────────────────

@router.post("/rules/from-template", status_code=201)
def create_from_template(body: SopTemplateRequest, token: dict = Depends(_require_admin)) -> Dict:
    """Instantiate a pre-defined SOP compliance rule without writing it from scratch."""
    defaults = _SOP_DEFAULTS.get(body.template)
    if defaults is None:
        raise HTTPException(
            422,
            f"unknown template; valid: {list(_SOP_DEFAULTS.keys())}",
        )
    with user_conn(token) as cur:
        cur.execute(
            """
            INSERT INTO action_rules
                (tenant_id, site_id, zone_id, name, description, rule_type,
                 threshold_value, threshold_window_minutes,
                 business_hours_start, business_hours_end, enabled, created_by)
            VALUES
                (%(tid)s, %(sid)s, %(zid)s, %(name)s, %(desc)s, %(rt)s,
                 %(tv)s, %(tw)s, %(bhs)s::time, %(bhe)s::time, TRUE, %(uid)s)
            RETURNING id::text, name, rule_type, enabled, created_at::text
            """,
            {
                "tid": token["tid"],
                "sid": body.site_id,
                "zid": body.zone_id,
                "name": body.name,
                "desc": defaults["description"],
                "rt": defaults["rule_type"],
                "tv": body.threshold_value,
                "tw": body.threshold_window_minutes,
                "bhs": body.business_hours_start,
                "bhe": body.business_hours_end,
                "uid": token["sub"],
            },
        )
        return dict(cur.fetchone())


# ── Channels endpoints ────────────────────────────────────────────────────────

@router.post("/channels", status_code=201)
def create_channel(body: ChannelCreate, token: dict = Depends(_require_admin)) -> Dict:
    if body.channel_type not in VALID_CHANNEL_TYPES:
        raise HTTPException(422, f"invalid channel_type; valid: {VALID_CHANNEL_TYPES}")
    if body.channel_type == "whatsapp" and body.whatsapp_cost_per_conversation_usd is None:
        raise HTTPException(
            422,
            "whatsapp_cost_per_conversation_usd required for WhatsApp channels "
            "(must reflect Meta cost explicitly — not absorbed in COGS)",
        )
    with user_conn(token) as cur:
        cur.execute(
            """
            INSERT INTO action_channels
                (tenant_id, name, channel_type, config_json, enabled,
                 whatsapp_cost_per_conversation_usd)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id::text, name, channel_type, enabled,
                      whatsapp_cost_per_conversation_usd, created_at::text
            """,
            (
                token["tid"],
                body.name,
                body.channel_type,
                psycopg2.extras.Json(body.config_json),
                body.enabled,
                body.whatsapp_cost_per_conversation_usd,
            ),
        )
        return dict(cur.fetchone())


@router.get("/channels")
def list_channels(token: dict = Depends(_require_user)) -> List[Dict]:
    with user_conn(token) as cur:
        cur.execute(
            """
            SELECT id::text, name, channel_type, enabled,
                   whatsapp_cost_per_conversation_usd, created_at::text
            FROM action_channels ORDER BY created_at DESC
            """
        )
        return [dict(r) for r in cur.fetchall()]


@router.put("/channels/{channel_id}")
def update_channel(
    channel_id: str, body: ChannelUpdate, token: dict = Depends(_require_admin)
) -> Dict:
    with user_conn(token) as cur:
        cur.execute(
            """
            UPDATE action_channels
            SET name          = COALESCE(%(name)s, name),
                channel_type  = COALESCE(%(ct)s, channel_type),
                config_json   = COALESCE(%(cfg)s, config_json),
                enabled       = COALESCE(%(en)s, enabled),
                whatsapp_cost_per_conversation_usd =
                    COALESCE(%(wc)s, whatsapp_cost_per_conversation_usd)
            WHERE id = %s
            RETURNING id::text, name, channel_type, enabled,
                      whatsapp_cost_per_conversation_usd
            """,
            {
                "name": body.name,
                "ct": body.channel_type,
                "cfg": psycopg2.extras.Json(body.config_json) if body.config_json is not None else None,
                "en": body.enabled,
                "wc": body.whatsapp_cost_per_conversation_usd,
            },
            (channel_id,),
        )
        row = cur.fetchone()
    if row is None:
        raise HTTPException(404, "channel_not_found")
    return dict(row)


@router.delete("/channels/{channel_id}", status_code=204)
def delete_channel(channel_id: str, token: dict = Depends(_require_admin)) -> None:
    with user_conn(token) as cur:
        cur.execute("DELETE FROM action_channels WHERE id = %s", (channel_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "channel_not_found")


# ── Audit log ─────────────────────────────────────────────────────────────────

@router.get("/log")
def get_action_log(
    limit: int = 100,
    token: dict = Depends(_require_user),
) -> List[Dict]:
    with user_conn(token) as cur:
        cur.execute(
            """
            SELECT al.id::text, al.rule_id::text, al.site_id::text,
                   al.triggered_at::text, al.channel_id::text, al.status,
                   al.payload_summary, al.meta_cost_usd, al.error_detail
            FROM action_log al
            ORDER BY al.triggered_at DESC
            LIMIT %s
            """,
            (min(limit, 500),),
        )
        return [dict(r) for r in cur.fetchall()]
