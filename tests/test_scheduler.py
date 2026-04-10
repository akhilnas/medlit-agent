"""Tests for src/services/scheduler.py."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.scheduler import PipelineScheduler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_query(cron: str = "0 6 * * 1", is_active: bool = True):
    q = MagicMock()
    q.id = uuid.uuid4()
    q.name = "SGLT2 HF"
    q.pubmed_query = "SGLT2 AND heart failure"
    q.is_active = is_active
    q.schedule_cron = cron
    return q


# ---------------------------------------------------------------------------
# PipelineScheduler
# ---------------------------------------------------------------------------

def test_scheduler_not_started_on_init():
    with patch("src.services.scheduler.AsyncIOScheduler") as MockScheduler:
        PipelineScheduler(db_factory=AsyncMock())
        MockScheduler.return_value.start.assert_not_called()


def test_scheduler_disabled_does_not_start():
    with patch("src.services.scheduler.AsyncIOScheduler") as MockScheduler:
        sched = PipelineScheduler(db_factory=AsyncMock(), enabled=False)
        sched.start()
        MockScheduler.return_value.start.assert_not_called()


def test_scheduler_enabled_starts_apscheduler():
    with patch("src.services.scheduler.AsyncIOScheduler") as MockScheduler:
        mock_aps = MagicMock()
        MockScheduler.return_value = mock_aps

        sched = PipelineScheduler(db_factory=AsyncMock(), enabled=True)
        sched.start()

        mock_aps.start.assert_called_once()


def test_scheduler_shutdown_calls_apscheduler():
    with patch("src.services.scheduler.AsyncIOScheduler") as MockScheduler:
        mock_aps = MagicMock()
        MockScheduler.return_value = mock_aps

        sched = PipelineScheduler(db_factory=AsyncMock(), enabled=True)
        sched.start()
        sched.shutdown()

        mock_aps.shutdown.assert_called_once()


def test_scheduler_shutdown_is_noop_when_disabled():
    with patch("src.services.scheduler.AsyncIOScheduler") as MockScheduler:
        mock_aps = MagicMock()
        MockScheduler.return_value = mock_aps

        sched = PipelineScheduler(db_factory=AsyncMock(), enabled=False)
        sched.shutdown()  # must not raise
        mock_aps.shutdown.assert_not_called()


def test_schedule_query_adds_cron_job():
    with patch("src.services.scheduler.AsyncIOScheduler") as MockScheduler:
        mock_aps = MagicMock()
        MockScheduler.return_value = mock_aps
        query = make_query(cron="0 6 * * 1")

        sched = PipelineScheduler(db_factory=AsyncMock(), enabled=True)
        sched.start()
        sched.schedule_query(query)

        mock_aps.add_job.assert_called_once()
        call_kwargs = mock_aps.add_job.call_args[1]
        assert call_kwargs.get("trigger") == "cron" or "cron" in str(mock_aps.add_job.call_args)


def test_schedule_query_skips_inactive():
    with patch("src.services.scheduler.AsyncIOScheduler") as MockScheduler:
        mock_aps = MagicMock()
        MockScheduler.return_value = mock_aps
        query = make_query(is_active=False)

        sched = PipelineScheduler(db_factory=AsyncMock(), enabled=True)
        sched.start()
        sched.schedule_query(query)

        mock_aps.add_job.assert_not_called()


def test_schedule_query_skips_when_no_cron():
    with patch("src.services.scheduler.AsyncIOScheduler") as MockScheduler:
        mock_aps = MagicMock()
        MockScheduler.return_value = mock_aps
        query = make_query(cron=None)
        query.schedule_cron = None

        sched = PipelineScheduler(db_factory=AsyncMock(), enabled=True)
        sched.start()
        sched.schedule_query(query)

        mock_aps.add_job.assert_not_called()


def test_unschedule_query_removes_job():
    with patch("src.services.scheduler.AsyncIOScheduler") as MockScheduler:
        mock_aps = MagicMock()
        MockScheduler.return_value = mock_aps
        query = make_query()

        sched = PipelineScheduler(db_factory=AsyncMock(), enabled=True)
        sched.start()
        sched.schedule_query(query)
        sched.unschedule_query(query.id)

        mock_aps.remove_job.assert_called_once()
