"""Persistent reminders + honest notification delivery.

A backend process must be running for the in-process scheduler to fire.
There is no claim that reminders fire when the server is stopped or the
Android device is off; browser/Termux delivery is best-effort.
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session as OrmSession

from core.config import get_settings
from core.db.repositories import NotificationRepository, ReminderRepository
from core.errors import AppError, not_found
from core.scheduler import PROCESSING_LOCK


class ReminderService:
    def __init__(self, db: OrmSession, terminal_notifier_path: str | None = None) -> None:
        self.db = db
        self.repo = ReminderRepository(db)
        self.notifications = NotificationRepository(db)
        self.notifier_path = terminal_notifier_path or shutil.which("termux-notification")

    # ── helpers ────────────────────────────────────────────────
    @staticmethod
    def _as_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    def validate_timezone(name: str) -> str:
        try:
            ZoneInfo(name)
        except ZoneInfoNotFoundError as exc:
            raise AppError(
                "INVALID_TIMEZONE",
                "Unknown timezone.",
                what_failed="Reminder timezone",
                what_happened=f"{name!r} is not a valid IANA timezone.",
                what_next="Use a value like UTC, Asia/Kolkata, or America/New_York.",
            ) from exc
        return name

    @staticmethod
    def next_occurrence(current: datetime, recurrence: str, interval: int, tz_name: str) -> datetime | None:
        if recurrence == "none" or not recurrence:
            return None
        tz = ZoneInfo(tz_name)
        local = current.astimezone(tz)
        interval = max(1, int(interval or 1))
        if recurrence == "daily":
            nxt = local + timedelta(days=interval)
        elif recurrence == "weekly":
            nxt = local + timedelta(weeks=interval)
        elif recurrence == "monthly":
            # same clock time, same day-of-month where possible
            year = local.year
            month = local.month + interval
            while month > 12:
                month -= 12
                year += 1
            day = min(local.day, 28)
            nxt = local.replace(year=year, month=month, day=day)
            if nxt <= local:
                month += 1
                if month > 12:
                    month = 1
                    year += 1
                nxt = local.replace(year=year, month=month, day=min(local.day, 28))
        elif recurrence == "yearly":
            nxt = local.replace(year=local.year + interval)
        else:
            return None
        return nxt.astimezone(timezone.utc)

    # ── CRUD ───────────────────────────────────────────────────
    def create(self, user_id: str, data: dict) -> object:
        payload = dict(data or {})
        payload["timezone"] = self.validate_timezone(payload.get("timezone") or "UTC")
        payload["scheduled_at"] = self._as_utc(payload["scheduled_at"])
        if payload["scheduled_at"] <= datetime.now(timezone.utc) and payload.get("recurrence", "none") == "none":
            # Allow immediate-ish reminders; keep as scheduled.
            pass
        row = self.repo.create(user_id, payload)
        row.next_run_at = row.scheduled_at
        self.db.add(row)
        self.db.flush()
        return row

    def update(self, user_id: str, reminder_id: str, data: dict) -> object:
        payload = dict(data or {})
        if "timezone" in payload and payload["timezone"] is not None:
            payload["timezone"] = self.validate_timezone(payload["timezone"])
        if "scheduled_at" in payload and payload["scheduled_at"] is not None:
            payload["scheduled_at"] = self._as_utc(payload["scheduled_at"])
            payload["next_run_at"] = payload["scheduled_at"]
        row = self.repo.update(user_id, reminder_id, payload)
        return row

    def cancel(self, user_id: str, reminder_id: str) -> object:
        return self.repo.cancel(user_id, reminder_id)

    def delete(self, user_id: str, reminder_id: str) -> bool:
        return self.repo.delete(user_id, reminder_id)

    # ── firing ─────────────────────────────────────────────────
    def _notify_termux(self, notification) -> tuple[bool, str | None]:
        if not self.notifier_path:
            return False, None
        try:
            completed = subprocess.run(
                [
                    self.notifier_path,
                    "--title", notification.title,
                    "--content", notification.body or "",
                    "--id", notification.id,
                ],
                check=False,
                timeout=10,
                capture_output=True,
                text=True,
            )
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)
        if completed.returncode != 0:
            return False, (completed.stderr or "").strip() or f"exit code {completed.returncode}"
        return True, None

    def process_due(
        self,
        now: datetime | None = None,
        catch_up: bool = False,
        catch_up_window_hours: int = 24,
        max_batch: int | None = None,
    ) -> int:
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=catch_up_window_hours)
        fired = 0
        with PROCESSING_LOCK:
            due = self.repo.due(now)
            if max_batch is None:
                max_batch = len(due) if not catch_up else min(100, len(due))
            due = due[:max_batch]
            for reminder in due:
                try:
                    # Idempotency: never fire the same scheduled occurrence twice.
                    if reminder.last_fired_at is not None and reminder.last_fired_at >= reminder.scheduled_at:
                        # Advance defensively if a previous delivery already happened.
                        if reminder.recurrence != "none" and reminder.recurrence:
                            nxt = reminder.scheduled_at
                            while True:
                                candidate = self.next_occurrence(
                                    nxt, reminder.recurrence, reminder.recurrence_interval, reminder.timezone
                                )
                                if candidate is None or candidate > now:
                                    break
                                nxt = candidate
                            if nxt != reminder.scheduled_at:
                                reminder.scheduled_at = nxt
                                reminder.next_run_at = nxt
                                self.db.add(reminder)
                                self.db.flush()
                        self.db.commit()
                        continue

                    one_time = reminder.recurrence in (None, "", "none")
                    scheduled = reminder.scheduled_at if reminder.scheduled_at.tzinfo else reminder.scheduled_at.replace(tzinfo=timezone.utc)

                    # Catch-up policy: avoid replaying very old one-time reminders.
                    if one_time and catch_up and scheduled < cutoff:
                        reminder.status = "FAILED"
                        self.db.add(reminder)
                        self.db.flush()
                        self.db.commit()
                        continue

                    # Calculate the next recurring occurrence that is strictly future.
                    if not one_time:
                        scheduled_current = reminder.scheduled_at
                        next_future = None
                        iteration = scheduled_current
                        guard = 0
                        while guard < 10000:
                            candidate = self.next_occurrence(iteration, reminder.recurrence, reminder.recurrence_interval, reminder.timezone)
                            guard += 1
                            if candidate is None or candidate > now:
                                next_future = candidate
                                break
                            iteration = candidate
                        if next_future is None:
                            # No future recurrence; leave scheduled as-is.
                            next_future = reminder.next_run_at

                    native_path = self.notifier_path
                    channel = "termux" if native_path else "web"
                    notification = self.notifications.create(
                        {
                            "user_id": reminder.user_id,
                            "reminder_id": reminder.id,
                            "title": reminder.title,
                            "body": reminder.message or reminder.title,
                            "channel": channel,
                            "status": "QUEUED",
                        }
                    )
                    if native_path:
                        termux_ok, termux_error = self._notify_termux(notification)
                        if termux_ok:
                            notification.status = "SENT"
                            notification.sent_at = now
                            notification.error = None
                        else:
                            notification.status = "FAILED"
                            notification.error = termux_error or "native delivery failed"
                            notification.sent_at = None
                    else:
                        notification.status = "QUEUED"
                        notification.error = None
                        notification.sent_at = None
                    self.db.add(notification)

                    reminder.last_fired_at = reminder.scheduled_at
                    if one_time:
                        reminder.status = "FIRED"
                        reminder.next_run_at = None
                    else:
                        reminder.scheduled_at = next_future if next_future else reminder.scheduled_at
                        reminder.next_run_at = reminder.scheduled_at
                        reminder.status = "SCHEDULED"
                    self.db.add(reminder)
                    self.db.flush()
                    self.db.commit()
                    fired += 1
                except Exception as exc:  # noqa: BLE001
                    self.db.rollback()
                    fresh = self.repo.get(reminder.user_id, reminder.id)
                    if fresh is not None:
                        fresh.status = "FAILED"
                        try:
                            self.db.add(fresh)
                            self.db.flush()
                            self.db.commit()
                        except Exception:  # noqa: BLE001
                            self.db.rollback()
            return fired
