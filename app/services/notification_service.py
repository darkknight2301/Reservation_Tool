"""
Notification service.

Fans a single reservation event out across the requested channels:
``WALL`` posts a dashboard Announcement; ``MAIL_LEADS`` / ``MAIL_GROUP`` /
``MAIL_ALL`` send email via ``EmailService``, scoped to the setup's Group
(or every active user for ``MAIL_ALL``).
"""
from datetime import datetime, timedelta
from typing import List, Optional

from app.core.constants import AnnouncementChannel, AnnouncementPriority, RoleName, UserStatus
from app.models.setup import Setup
from app.models.user import User
from app.repositories.interfaces.i_user_repository import IUserRepository
from app.schemas.announcement import AnnouncementCreateRequest
from app.schemas.user import UserFilter
from app.services.announcement_service import AnnouncementService
from app.services.email_service import EmailService

_LEAD_ROLE_NAMES = (RoleName.LEAD, RoleName.DEVELOPER_LEAD, RoleName.OWNER)


class NotificationService:
    """Broadcasts reservation events across the selected announcement channels."""

    def __init__(
        self,
        announcement_service: AnnouncementService,
        email_service: EmailService,
        user_repository: IUserRepository,
    ) -> None:
        self._announcement_service = announcement_service
        self._email_service = email_service
        self._user_repository = user_repository

    def broadcast_reservation_event(
        self,
        channels: List[str],
        message: Optional[str],
        setup: Setup,
        acting_user: User,
    ) -> None:
        """Dispatch the given message across every requested channel."""
        if not channels:
            return

        text = message or "{0} reserved {1} ({2}).".format(acting_user.full_name, setup.hostname, setup.ip_address)
        subject = "Reservation update: {0}".format(setup.hostname)

        if AnnouncementChannel.WALL in channels:
            self._announcement_service.create(
                AnnouncementCreateRequest(
                    title=subject,
                    message=text,
                    priority=AnnouncementPriority.NORMAL,
                    start_date=datetime.utcnow(),
                    end_date=datetime.utcnow() + timedelta(days=7),
                ),
                acting_user,
            )

        if AnnouncementChannel.MAIL_LEADS in channels:
            self._email_service.send_email(self._group_lead_emails(setup.group_id), subject, text)

        if AnnouncementChannel.MAIL_GROUP in channels:
            self._email_service.send_email(self._group_member_emails(setup.group_id), subject, text)

        if AnnouncementChannel.MAIL_ALL in channels:
            self._email_service.send_email(self._all_active_user_emails(), subject, text)

    def _group_lead_emails(self, group_id: Optional[int]) -> List[str]:
        if group_id is None:
            return []
        users, _ = self._user_repository.list(UserFilter(group_id=group_id, status=UserStatus.APPROVED), page=1, page_size=1000)
        return [u.email for u in users if u.role.name in _LEAD_ROLE_NAMES]

    def _group_member_emails(self, group_id: Optional[int]) -> List[str]:
        if group_id is None:
            return []
        users, _ = self._user_repository.list(UserFilter(group_id=group_id, status=UserStatus.APPROVED), page=1, page_size=1000)
        return [u.email for u in users]

    def _all_active_user_emails(self) -> List[str]:
        users, _ = self._user_repository.list(UserFilter(status=UserStatus.APPROVED), page=1, page_size=100000)
        return [u.email for u in users if u.is_active]
