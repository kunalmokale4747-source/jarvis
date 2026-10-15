from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as OrmSession

from apps.api.deps import get_db, get_identity
from apps.api.schemas import ChatMessageOut, ChatSendRequest, ChatSendResponse, ChatSessionOut
from core.auth import Identity
from core.chat.service import ChatService
from core.db.repositories import ChatRepository

router = APIRouter(tags=["chat"])


@router.get("/sessions")
def list_sessions(
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> list[ChatSessionOut]:
    svc = ChatService(db)
    rows = svc.list_sessions(identity.user_id)
    return [ChatSessionOut.model_validate(r) for r in rows]


@router.post("/sessions")
def create_session(
    title: str | None = None,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> ChatSessionOut:
    svc = ChatService(db)
    row = svc.create_session(identity.user_id, title=title)
    return ChatSessionOut.model_validate(row)


@router.get("/sessions/{session_id}")
def get_session(
    session_id: str,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> ChatSessionOut:
    svc = ChatService(db)
    row = svc.get_session(identity.user_id, session_id)
    return ChatSessionOut.model_validate(row)


@router.get("/sessions/{session_id}/messages")
def list_messages(
    session_id: str,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> list[ChatMessageOut]:
    svc = ChatService(db)
    rows = svc.messages(identity.user_id, session_id)
    return [ChatMessageOut.model_validate(r) for r in rows]


@router.post("/sessions/{session_id}/messages")
def send_to_session(
    session_id: str,
    body: ChatSendRequest,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> ChatSendResponse:
    svc = ChatService(db)
    # ignore body.session_id, trust path
    result = svc.send(identity.user_id, body.message, session_id=session_id, title=body.title)
    return ChatSendResponse(
        session_id=result["session_id"],
        user_message=ChatMessageOut.model_validate(result["user_message"]),
        assistant_message=ChatMessageOut.model_validate(result["assistant_message"]),
        offline=result["offline"],
    )


@router.post("/send")
def send_chat(
    body: ChatSendRequest,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> ChatSendResponse:
    svc = ChatService(db)
    result = svc.send(identity.user_id, body.message, session_id=body.session_id, title=body.title)
    return ChatSendResponse(
        session_id=result["session_id"],
        user_message=ChatMessageOut.model_validate(result["user_message"]),
        assistant_message=ChatMessageOut.model_validate(result["assistant_message"]),
        offline=result["offline"],
    )


@router.post("")
def send_chat_root(
    body: ChatSendRequest,
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> ChatSendResponse:
    return send_chat(body, identity, db)


@router.get("/history")
def chat_history(
    session_id: str | None = Query(default=None),
    identity: Identity = Depends(get_identity),
    db: OrmSession = Depends(get_db),
) -> list[ChatMessageOut]:
    svc = ChatService(db)
    if not session_id:
        sessions = svc.list_sessions(identity.user_id)
        if not sessions:
            return []
        session_id = sessions[0].id
    rows = svc.messages(identity.user_id, session_id)
    return [ChatMessageOut.model_validate(r) for r in rows]
