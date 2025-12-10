"""Notification scheduling for the outage bot."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import logging
from typing import Iterable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from telegram import Bot

from .database import session_scope
from .models import NotificationLog, OutageEvent, User


LOGGER = logging.getLogger(__name__)


class NotificationService:
    """Schedules and sends notifications to users."""

    def __init__(self, session_factory, *, offset_minutes: int = 60) -> None:
        self._session_factory = session_factory
        self._offset = offset_minutes
        self._scheduler = AsyncIOScheduler()
        self._application_bot: Bot | None = None

    def bind_bot(self, bot: Bot) -> None:
        self._application_bot = bot

    def start(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    def schedule_events(self, events: Iterable[OutageEvent]) -> None:
        for event in events:
            self._schedule_single_event(event)

    def _schedule_single_event(self, event: OutageEvent) -> None:
        run_time = event.start_time - timedelta(minutes=self._offset)
        tzinfo = run_time.tzinfo or timezone.utc
        if run_time <= datetime.now(tz=tzinfo):
            LOGGER.debug("Skipping scheduling for past event %s", event.id)
            return
        job_id = f"notify-{event.id}"
        self._scheduler.add_job(
            self._dispatch_notification,
            trigger=DateTrigger(run_date=run_time),
            args=[event.id],
            id=job_id,
            replace_existing=True,
        )
        LOGGER.debug("Scheduled notification %s at %s", job_id, run_time)

    async def reschedule_from_database(self) -> None:
        """Reload persisted events and schedule notifications."""

        def load_events():
            with session_scope(self._session_factory) as session:
                now = datetime.now(tz=timezone.utc)
                return (
                    session.query(OutageEvent)
                    .filter(OutageEvent.start_time > now)
                    .all()
                )

        events = await asyncio.to_thread(load_events)
        for event in events:
            self._schedule_single_event(event)

    async def _dispatch_notification(self, event_id: int) -> None:
        if not self._application_bot:
            LOGGER.error("Cannot send notification without a bound bot")
            return

        def load_event_and_users():
            with session_scope(self._session_factory) as session:
                event = session.get(OutageEvent, event_id)
                if event is None:
                    return None, []
                users = (
                    session.query(User)
                    .filter(
                        User.region_code == event.region_code,
                        User.locality_id == event.locality_id,
                        User.queue == event.queue,
                    )
                    .all()
                )
                return event, users

        event, users = await asyncio.to_thread(load_event_and_users)
        if not event or not users:
            LOGGER.info("No users to notify for event %s", event_id)
            return

        tasks = [self._send_to_user(event, user) for user in users]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_to_user(self, event: OutageEvent, user: User) -> None:
        assert self._application_bot
        try:
            already_sent = await asyncio.to_thread(self._notification_exists, event.id, user.id)
            if already_sent:
                LOGGER.debug("Notification already sent for event %s and user %s", event.id, user.telegram_id)
                return
            await self._application_bot.send_message(
                chat_id=user.telegram_id,
                text=self._build_notification_message(event, user),
            )
            await asyncio.to_thread(self._store_notification_log, event.id, user.id)
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("Failed to send notification to %s: %s", user.telegram_id, exc)

    @staticmethod
    def _build_notification_message(event: OutageEvent, user: User) -> str:
        start_local = event.start_time.astimezone()
        end_local = event.end_time.astimezone()
        return (
            "⚠️ Незабаром планується відключення електроенергії\n"
            f"Регіон: {event.region_title}\n"
            f"Населений пункт: {event.locality_title}\n"
            f"Черга: {event.queue}\n"
            f"Початок: {start_local:%d.%m.%Y %H:%M}\n"
            f"Завершення: {end_local:%d.%m.%Y %H:%M}\n"
        )

    def _store_notification_log(self, event_id: int, user_id: int) -> None:
        with session_scope(self._session_factory) as session:
            exists = (
                session.query(NotificationLog)
                .filter(
                    NotificationLog.event_id == event_id,
                    NotificationLog.user_id == user_id,
                )
                .first()
            )
            if exists:
                return
            session.add(NotificationLog(event_id=event_id, user_id=user_id))

    def _notification_exists(self, event_id: int, user_id: int) -> bool:
        with session_scope(self._session_factory) as session:
            exists = (
                session.query(NotificationLog)
                .filter(
                    NotificationLog.event_id == event_id,
                    NotificationLog.user_id == user_id,
                )
                .first()
            )
            return exists is not None
