from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as OrmSession

from apps.api.deps import get_db, get_identity
from apps.api.schemas import MemoryCreate, MemoryHitOut, MemoryOut, MemoryUpdate
from core.auth import Identity
from core.db.repositories import MemoryRepository
from core.db.models import Memory as _Memory
from core.memory.service import MemoryService

router = APIRouter(tags=["memory"])


def _svc(db, embedder=None):
    return MemoryService(db, embedder=embedder)


@router.get("/categories")
def categories() -> list[str]:
    from core.memory.service import MemoryCategory

    return [c.value for c in MemoryCategory]


@router.get("/search")
def search_memory(
    q: str = "",
    type: str | None = None,
    limit: int = 8,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> list[MemoryHitOut]:
    service = _svc(db)
    types = [type] if type else None
    hits = service.search(user_id=identity.user_id, query=q, types=types, limit=limit)
    out = []
    for h in hits:
        out.append(MemoryHitOut(memory=MemoryOut.model_validate(h.memory), score=h.score))
    return out


@router.get("")
def list_memory(
    type: str | None = Query(default=None),
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> list[MemoryOut]:
    repo = MemoryRepository(db)
    types = [type] if type else None
    rows = repo.list_for_user(identity.user_id, types=types)
    return [MemoryOut.model_validate(r) for r in rows]


@router.post("")
def create_memory(
    body: MemoryCreate,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> dict:
    service = _svc(db)
    result = service.propose(
        user_id=identity.user_id,
        content=body.content,
        type=body.type,
        importance=body.importance,
        confidence=body.confidence,
        source=body.source,
        structured_ref=body.structured_ref,
    )
    out = None
    if result.memory_id:
        row = db.get(_Memory, result.memory_id)
        if row is not None:
            out = MemoryOut.model_validate(row)
    return {"accepted": result.accepted, "reason": result.reason, "memory_id": result.memory_id, "memory": out}


@router.put("/{memory_id}")
def update_memory(
    memory_id: str,
    body: MemoryUpdate,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> MemoryOut:
    repo = MemoryRepository(db)
    row = repo.get(identity.user_id, memory_id)
    if row is None:
        from core.errors import not_found

        raise not_found("memory")
    if body.content is not None:
        row.content = body.content
    if body.type is not None:
        row.type = body.type
    if body.importance is not None:
        row.importance = body.importance
    if body.confidence is not None:
        row.confidence = body.confidence
    db.add(row)
    db.flush()
    return MemoryOut.model_validate(row)


@router.delete("/{memory_id}")
def delete_memory(
    memory_id: str,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> dict:
    service = _svc(db)
    ok = service.delete(identity.user_id, memory_id)
    if not ok:
        from core.errors import not_found

        raise not_found("memory")
    return {"deleted": True, "id": memory_id}
