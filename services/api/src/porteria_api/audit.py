"""Escribir en la bitácora de auditoría dentro de la transacción de quien hace el cambio."""

import enum
import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.orm import Session

from porteria_api.models import AuditAction, AuditLog, User
from porteria_api.models.audit import JSONScalar

USER_AUDIT_FIELDS = ("username", "full_name", "role", "status", "resident_id")
# Aunque alguien los pida por error, estos campos nunca llegan a la bitácora.
SECRET_FIELDS = frozenset({"password", "password_hash"})


def _json_value(field: str, value: object) -> JSONScalar:
    if isinstance(value, enum.Enum):
        value = value.value
    if value is None or isinstance(value, str | int | bool):
        return value
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"{field}: no se sabe guardar {type(value).__name__} en la auditoría")


def snapshot(obj: object, fields: Sequence[str]) -> dict[str, JSONScalar]:
    """Foto de `fields` de `obj` lista para JSON; solo lo que está en la lista."""
    secrets = SECRET_FIELDS.intersection(fields)
    if secrets:
        raise ValueError(f"campos secretos en la auditoría: {sorted(secrets)}")
    return {field: _json_value(field, getattr(obj, field)) for field in fields}


def record_audit(
    session: Session,
    *,
    actor: User | None,
    action: AuditAction,
    entity_type: str,
    entity_id: uuid.UUID | None,
    before: dict[str, JSONScalar] | None = None,
    after: dict[str, JSONScalar] | None = None,
) -> AuditLog:
    """Solo hace `session.add`: la fila se confirma o se deshace junto con el cambio."""
    log = AuditLog(
        actor_user_id=actor.id if actor is not None else None,
        action=action.value,
        entity_type=entity_type,
        entity_id=entity_id,
        before=before,
        after=after,
    )
    session.add(log)
    return log
