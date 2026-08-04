"""
Scheduler service: background jobs run in-process via APScheduler.

Runs the reservation-expiry sweep and announcement-expiry sweep on
configurable intervals. Each job opens its own short-lived DB session so it
does not hold a connection open between runs.
"""
from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.core.logging_config import get_logger
from app.db.session import SessionLocal
from app.repositories.sqlalchemy.announcement_repository import AnnouncementRepository
from app.repositories.sqlalchemy.audit_repository import AuditLogRepository
from app.repositories.sqlalchemy.reservation_repository import ReservationRepository
from app.repositories.sqlalchemy.role_repository import RoleRepository
from app.repositories.sqlalchemy.setup_repository import SetupRepository
from app.services.announcement_service import AnnouncementService
from app.services.audit_service import AuditService
from app.services.reservation_service import ReservationService
from app.services.role_lookup_service import RoleLookupService
from app.utils.datetime_utils import utc_now

logger = get_logger(__name__)

_scheduler = BackgroundScheduler(timezone="UTC")


def _run_reservation_sweep() -> None:
    """Job: complete ACTIVE reservations past their reserved_until."""
    db = SessionLocal()
    try:
        audit_service = AuditService(AuditLogRepository(db))
        role_lookup_service = RoleLookupService(RoleRepository(db))
        service = ReservationService(
            ReservationRepository(db), SetupRepository(db), role_lookup_service, audit_service
        )
        swept = service.sweep_expired_reservations(utc_now())
        db.commit()
        if swept:
            logger.info("Reservation expiry sweep completed.", extra={"swept_count": swept})
    except Exception:  # noqa: BLE001 - a failed sweep must not crash the scheduler thread
        db.rollback()
        logger.exception("Reservation expiry sweep failed.")
    finally:
        db.close()


def _run_announcement_sweep() -> None:
    """Job: deactivate announcements past their end_date."""
    db = SessionLocal()
    try:
        audit_service = AuditService(AuditLogRepository(db))
        service = AnnouncementService(AnnouncementRepository(db), audit_service)
        swept = service.sweep_expired(utc_now())
        db.commit()
        if swept:
            logger.info("Announcement expiry sweep completed.", extra={"swept_count": swept})
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("Announcement expiry sweep failed.")
    finally:
        db.close()


def start_scheduler() -> None:
    """Register and start all background jobs. Called once at app startup."""
    if not settings.ENABLE_SCHEDULER:
        return
    _scheduler.add_job(
        _run_reservation_sweep, "interval", minutes=settings.RESERVATION_SWEEP_INTERVAL_MINUTES,
        id="reservation_sweep", replace_existing=True,
    )
    _scheduler.add_job(
        _run_announcement_sweep, "interval", minutes=settings.ANNOUNCEMENT_SWEEP_INTERVAL_MINUTES,
        id="announcement_sweep", replace_existing=True,
    )
    _scheduler.start()
    logger.info("Background scheduler started.")


def shutdown_scheduler() -> None:
    """Stop all background jobs. Called at app shutdown."""
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
