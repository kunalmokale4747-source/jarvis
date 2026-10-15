"""Curated long-term memory.

Storage policy (docs/architecture.md §7): a memory must pass a value test
before it is stored — JARVIS does not dump conversations into memory.
Retrieval combines relevance, importance, recency and confidence.
"""

from __future__ import annotations

import enum
import math
import re
import struct
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from core.db.models import Memory, utcnow

MEMORY_TTL_DAYS = 365


class MemoryCategory(str, enum.Enum):
    PROFILE = "PROFILE"
    GOAL = "GOAL"
    PROJECT = "PROJECT"
    TASK = "TASK"
    PREFERENCE = "PREFERENCE"
    CONTACT = "CONTACT"
    OPPORTUNITY = "OPPORTUNITY"
    DECISION = "DECISION"
    LESSON = "LESSON"
    CONVERSATION = "CONVERSATION"
    FACT = "FACT"


_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "so", "of", "to", "in",
    "on", "at", "for", "with", "by", "from", "as", "is", "are", "was", "were",
    "be", "been", "it", "its", "this", "that", "these", "those", "i", "you",
    "he", "she", "we", "they", "me", "my", "your", "our", "their", "am", "do",
    "does", "did", "have", "has", "had", "will", "would", "can", "could",
    "should", "about", "into", "up", "down", "out", "not", "no", "yes", "ok",
    "okay", "thanks", "thank", "please", "hi", "hello", "hey", "great", "good",
    "very", "much", "many", "more", "most", "some", "any", "all",
}

_TOKEN_RE = re.compile(r"[a-z0-9@._+-]+")


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t]


def content_tokens(text: str) -> list[str]:
    return [t for t in tokenize(text) if t not in _STOPWORDS]


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


def pack_embedding(vector: list[float]) -> bytes:
    return struct.pack(f"<{len(vector)}f", *vector)


def unpack_embedding(blob: bytes | None) -> list[float] | None:
    if not blob:
        return None
    count = len(blob) // 4
    return list(struct.unpack(f"<{count}f", blob))


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if not na or not nb:
        return 0.0
    return max(0.0, dot / (na * nb))


@dataclass
class MemoryWriteResult:
    accepted: bool
    reason: str
    memory_id: str | None = None


@dataclass
class MemorySearchHit:
    memory: Memory
    score: float


class MemoryService:
    def __init__(
        self,
        db: OrmSession,
        embedder: Callable[[str], list[float]] | None = None,
    ) -> None:
        self.db = db
        self.embedder = embedder

    # ── write path ────────────────────────────────────────────────
    @staticmethod
    def evaluate_value(
        content: str, *, importance: float, confidence: float
    ) -> tuple[bool, str]:
        """Value test — only information useful for future assistance passes."""
        text = (content or "").strip()
        if not text:
            return False, "empty content"
        if len(text) < 15:
            return False, "too short to be useful for future assistance"
        if len(content_tokens(text)) < 3:
            return False, "low signal (greetings/thanks/filler, no durable information)"
        if importance < 0.1:
            return False, "declared importance below the storage threshold (0.1)"
        if confidence < 0 or confidence > 1:
            return False, "confidence must be between 0 and 1"
        return True, "ok"

    def propose(
        self,
        *,
        user_id: str,
        content: str,
        type: str | MemoryCategory = MemoryCategory.FACT,
        importance: float = 0.5,
        confidence: float = 0.8,
        source: str = "user",
        structured_ref: dict | None = None,
    ) -> MemoryWriteResult:
        category = MemoryCategory(type)
        importance = min(1.0, max(0.0, float(importance)))
        confidence = min(1.0, max(0.0, float(confidence)))

        ok, reason = self.evaluate_value(content, importance=importance, confidence=confidence)
        if not ok:
            return MemoryWriteResult(accepted=False, reason=reason)

        text = content.strip()
        merged = self._find_duplicate(user_id, text)
        if merged is not None:
            merged.importance = max(merged.importance, importance)
            merged.confidence = max(merged.confidence, confidence)
            merged.updated_at = utcnow()
            self.db.add(merged)
            self.db.flush()
            return MemoryWriteResult(
                accepted=True, reason="merged with an existing near-duplicate memory",
                memory_id=merged.id,
            )

        embedding = None
        if self.embedder is not None:
            try:
                embedding = pack_embedding(self.embedder(text))
            except Exception:  # noqa: BLE001 - embeddings are best-effort
                embedding = None

        row = Memory(
            user_id=user_id,
            type=category.value,
            content=text,
            structured_ref=structured_ref,
            importance=importance,
            confidence=confidence,
            source=source,
            embedding=embedding,
            expires_at=None,
        )
        self.db.add(row)
        self.db.flush()
        return MemoryWriteResult(accepted=True, reason="stored", memory_id=row.id)

    def _find_duplicate(self, user_id: str, content: str) -> Memory | None:
        norm = normalize(content)
        tokens = set(tokenize(content))
        for row in self.db.scalars(self._live_query(user_id).limit(2000)):
            if normalize(row.content) == norm:
                return row
            if jaccard(tokens, set(tokenize(row.content))) >= 0.85:
                return row
        return None

    # ── retrieval ─────────────────────────────────────────────────
    def _live_query(self, user_id: str, types: list[str] | None = None):
        now = utcnow()
        stmt = select(Memory).where(
            Memory.user_id == user_id,
            Memory.superseded_by.is_(None),
        )
        if types:
            stmt = stmt.where(Memory.type.in_(types))
        rows = list(self.db.scalars(stmt))
        live = []
        for row in rows:
            expires = row.expires_at
            if expires is not None:
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=timezone.utc)
                if expires <= now:
                    continue
            live.append(row)
        # re-query filtered ids for stable ordering
        if not live:
            return select(Memory).where(Memory.id.is_(None))
        return select(Memory).where(
            Memory.user_id == user_id,
            Memory.id.in_([r.id for r in live]),
        )

    def search(
        self,
        *,
        user_id: str,
        query: str = "",
        types: list[str] | None = None,
        limit: int = 8,
    ) -> list[MemorySearchHit]:
        rows = list(self.db.scalars(self._live_query(user_id, types)))
        query_tokens = set(content_tokens(query)) if query.strip() else set()
        query_emb: list[float] | None = None
        if query.strip() and self.embedder is not None:
            try:
                query_emb = self.embedder(query)
            except Exception:  # noqa: BLE001 - keyword path still works
                query_emb = None

        now = utcnow()
        hits: list[MemorySearchHit] = []
        for row in rows:
            tokens = set(content_tokens(row.content))
            keyword = 0.0
            if query_tokens:
                coverage = len(query_tokens & tokens) / len(query_tokens)
                keyword = 0.7 * coverage + 0.3 * jaccard(query_tokens, tokens)
            relevance = keyword
            mem_emb = unpack_embedding(row.embedding)
            if query_emb is not None and mem_emb is not None:
                relevance = max(relevance, cosine(query_emb, mem_emb))

            created = row.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            age_days = max(0.0, (now - created).total_seconds() / 86400.0)
            recency = math.exp(-age_days / 30.0)

            score = 0.5 * relevance + 0.25 * row.importance + 0.15 * recency + 0.10 * row.confidence
            hits.append(MemorySearchHit(memory=row, score=round(score, 6)))

        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:limit]

    # ── management ────────────────────────────────────────────────
    def delete(self, user_id: str, memory_id: str) -> bool:
        row = self.db.get(Memory, memory_id)
        if row is None or row.user_id != user_id:
            return False
        self.db.delete(row)
        self.db.flush()
        return True

    @staticmethod
    def categories() -> list[str]:
        return [c.value for c in MemoryCategory]
