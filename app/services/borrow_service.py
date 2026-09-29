"""
Borrow service (Phase 5).

A Borrow is a Lead/Manager-to-Lead/Manager transfer of *effective access* to
a setup (optionally naming the one hardware field actually needed) from the
group that owns it (the source) to the borrower's group, for a requested
window. It is an independent transaction domain from Reservation and Swap:
it never reads, creates or relocates a Reservation, and never exchanges
hardware values between setups.

State model (see ARCHITECTURE_ASSESSMENT.md section 10):
  * ORIGINAL state  -- ``Setup.group_id`` and the hardware baseline are NEVER
    modified by a Borrow.
  * EFFECTIVE state -- an approved Borrow creates one active
    ``SetupAccessGrant`` (borrower group). The effective holder of a setup is
    the active grant's group, else ``Setup.group_id``. Returning closes the
    grant, which restores the source group's access automatically -- there
    is no value to copy back, so nothing can drift.
  * HISTORY -- ``borrow_requests`` rows (all statuses, incl. who approved /
    returned and when), ``setup_access_grants`` rows (never deleted) and the
    audit log together give the complete Borrow history.

Lifecycle: PENDING -> COMPLETED (approved, currently borrowed) -> RETURNED;
or PENDING -> REJECTED / CANCELLED / EXPIRED (requested ``end_time`` passed
before anyone decided).

Who may do what:
  * request  -- LEAD / DEVELOPER_LEAD (Manager) / OWNER, and must belong to a
    group (that group becomes the borrowing group). The requester selects the
    *source lead* whose setup is needed.
  * approve/reject -- ANY ONE of the routed approvers is sufficient
    (``ApprovalRoutingService.resolve_borrow_approvers`` -- data-driven
    hierarchy, BORROW-scoped edges, e.g. E selecting Lead ``d`` routes to
    b,d,f,g). OWNER may always act. If the hierarchy yields no approver at
    all, the flat ``borrow:approve`` permission (checked by the caller)
    is authoritative so a request is never permanently unreachable.
    Nobody may decide their own request.
  * return ("get back") -- the requester, another lead of the borrowing
    group, any routed source-side approver, or OWNER.

Duplicate / conflicting states are prevented: at most one PENDING-or-active
Borrow per setup, no borrowing a setup your own group already holds, no
borrowing MAINTENANCE/RETIRED setups, valid time windows only.
"""
from datetime import datetime
from typing import List, Optional, Tuple

from app.core.constants import AnnouncementChannel, AuditAction, BorrowStatus, RoleName, SetupStatus, UserStatus
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError, ValidationAppError
from app.models.borrow_request import BorrowRequest
from app.models.setup_access_grant import SetupAccessGrant
from app.models.setup_hardware_baseline import BASELINE_FIELD_NAMES
from app.models.user import User
from app.repositories.interfaces.i_borrow_repository import IBorrowRepository
from app.repositories.interfaces.i_setup_repository import ISetupRepository
from app.repositories.interfaces.i_user_repository import IUserRepository
from app.schemas.borrow_request import (
    BorrowCreateRequest,
    BorrowDecisionRequest,
    BorrowFilter,
    BorrowReturnRequest,
)
from app.services.approval_routing_service import ApprovalRoutingService
from app.services.audit_service import AuditService
from app.services.hardware_state_service import HardwareStateService
from app.services.notification_service import NotificationService
from app.services.template_service import TemplateService

# Borrow privilege is restricted to Group Leads and their Managers (OWNER
# has full permissions). Enforced here as well as by the borrow:request
# permission so the rule holds even if a role's permission matrix changes.
BORROW_REQUESTER_ROLES = (RoleName.LEAD, RoleName.DEVELOPER_LEAD, RoleName.OWNER)
_LEAD_ROLES = (RoleName.LEAD, RoleName.DEVELOPER_LEAD)
_UNIVERSAL_ROLES = (RoleName.OWNER,)


def _group_ids(user: User) -> set:
    ids = set()
    if user.group_id:
        ids.add(user.group_id)
    ids.update(group.id for group in (user.groups or []))
    return ids


class BorrowService:
    """Business logic for Borrow request / approve / reject / cancel / return."""

    def __init__(
        self,
        borrow_repository: IBorrowRepository,
        setup_repository: ISetupRepository,
        user_repository: IUserRepository,
        audit_service: AuditService,
        approval_routing_service: Optional[ApprovalRoutingService] = None,
        template_service: Optional[TemplateService] = None,
        notification_service: Optional[NotificationService] = None,
        hardware_state_service: Optional[HardwareStateService] = None,
    ) -> None:
        self._borrow_repository = borrow_repository
        self._setup_repository = setup_repository
        self._user_repository = user_repository
        self._audit_service = audit_service
        self._approval_routing_service = approval_routing_service
        self._template_service = template_service
        self._notification_service = notification_service
        self._hardware_state_service = hardware_state_service

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_by_id(self, borrow_id: int) -> BorrowRequest:
        borrow = self._borrow_repository.get_by_id(borrow_id)
        if borrow is None:
            raise NotFoundError("Borrow request with id {0} was not found.".format(borrow_id))
        return borrow

    def list(self, filters: BorrowFilter, page: int, page_size: int) -> Tuple[List[BorrowRequest], int]:
        self.expire_stale_pending()
        return self._borrow_repository.list(filters, page, page_size)

    def expire_stale_pending(self, now: Optional[datetime] = None) -> int:
        """Mark every PENDING request whose requested window already ended as EXPIRED. Returns how many."""
        stale = self._borrow_repository.list_stale_pending(now or datetime.utcnow())
        for borrow in stale:
            borrow.status = BorrowStatus.EXPIRED
            self._borrow_repository.update(borrow)
            self._audit_service.record(
                user_id=None, action=AuditAction.UPDATE, entity_type="BorrowRequest", entity_id=borrow.id,
                old_value={"status": BorrowStatus.PENDING}, new_value={"status": BorrowStatus.EXPIRED},
            )
        return len(stale)

    def list_source_leads(self, acting_user: User) -> List[User]:
        """Leads/Managers of OTHER groups the requester may select as the source lead (UI helper)."""
        own_groups = _group_ids(acting_user)
        leads, _ = self._user_repository.list(
            _lead_filter(), page=1, page_size=1000
        )
        return [
            lead for lead in leads
            if lead.is_active and lead.role and lead.role.name in _LEAD_ROLES and lead.id != acting_user.id
            and (_group_ids(lead) - own_groups)
        ]

    def list_borrowable_setups(self, source_lead: User, acting_user: User) -> list:
        """Setups belonging to the selected lead's group(s), excluding the requester's own groups and any setup already tied up in a borrow (UI helper)."""
        own_groups = _group_ids(acting_user)
        candidates = []
        for group_id in sorted(_group_ids(source_lead) - own_groups):
            from app.schemas.setup import SetupFilter

            setups, _ = self._setup_repository.list(SetupFilter(group_id=group_id), page=1, page_size=500)
            candidates.extend(setups)
        return [
            s for s in candidates
            if s.group_id in (_group_ids(source_lead) - own_groups)
            and s.status not in (SetupStatus.MAINTENANCE, SetupStatus.RETIRED)
            and self._borrow_repository.get_open_for_setup(s.id) is None
        ]

    def borrowable_fields(self, setup) -> List[str]:
        """Hardware fields that can be named in a Borrow: the fixed hardware fields plus the setup's product custom columns."""
        fields = list(BASELINE_FIELD_NAMES)
        if self._template_service is not None:
            fields.extend(c.name for c in self._template_service.get_custom_columns(setup.product_id))
        return fields

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _routed_approvers(self, source_group_id: int) -> List[User]:
        if self._approval_routing_service is None:
            return []
        return self._approval_routing_service.resolve_borrow_approvers(source_group_id)

    def _assert_can_decide(self, borrow: BorrowRequest, acting_user: User) -> None:
        if acting_user.id == borrow.requester_id:
            raise AuthorizationError("You cannot approve or reject your own borrow request.")
        if acting_user.role and acting_user.role.name in _UNIVERSAL_ROLES:
            return
        approvers = [u for u in self._routed_approvers(borrow.source_group_id) if u.id != borrow.requester_id]
        if not approvers:
            return  # fallback: flat borrow:approve (checked by the caller) is authoritative
        if acting_user.id not in {u.id for u in approvers}:
            raise AuthorizationError(
                "You are not one of the routed approvers for this borrow request. "
                "Any one of the routed Leads/Managers may approve it."
            )

    def can_decide(self, borrow: BorrowRequest, acting_user: User) -> bool:
        """True if ``acting_user`` may approve/reject this pending borrow (routing + not the requester) -- used by the UI to show only usable actions."""
        if borrow.status != BorrowStatus.PENDING:
            return False
        try:
            self._assert_can_decide(borrow, acting_user)
        except AuthorizationError:
            return False
        return True

    def can_return(self, borrow: BorrowRequest, acting_user: User) -> bool:
        """True if ``acting_user`` may return this borrow (UI helper)."""
        if borrow.status != BorrowStatus.COMPLETED:
            return False
        try:
            self._assert_can_return(borrow, acting_user)
        except AuthorizationError:
            return False
        return True

    def _assert_can_return(self, borrow: BorrowRequest, acting_user: User) -> None:
        if acting_user.id == borrow.requester_id:
            return
        if acting_user.role and acting_user.role.name in _UNIVERSAL_ROLES:
            return
        if acting_user.role and acting_user.role.name in _LEAD_ROLES:
            if borrow.target_group_id in _group_ids(acting_user):
                return  # another lead of the borrowing group
            if acting_user.id in {u.id for u in self._routed_approvers(borrow.source_group_id)}:
                return  # source side "getting it back"
        raise AuthorizationError(
            "Only the requester, a Lead of the borrowing group, a routed approver of the source group, or an Owner may return this borrow."
        )

    def _validate_field(self, setup, field_name: Optional[str]) -> None:
        if field_name is None:
            return
        if field_name not in self.borrowable_fields(setup):
            raise ValidationAppError("'{0}' is not a hardware field of setup {1}.".format(field_name, setup.hostname))

    def _notify(self, recipients: List[str], subject: str, message: str, channels: List[str], setup, acting_user: User) -> None:
        """Direct email to the given leads/requester (always), plus the requester-chosen broader broadcast."""
        if self._notification_service is None:
            return
        unique = sorted({r for r in recipients if r})
        if unique:
            self._notification_service.email_direct(unique, subject, message)
        extra = [c for c in channels if c != AnnouncementChannel.MAIL_LEADS]  # direct email already reaches the leads
        if extra:
            self._notification_service.broadcast_reservation_event(extra, message, setup, acting_user)

    @staticmethod
    def _channels(borrow: BorrowRequest) -> List[str]:
        return [c for c in (borrow.announcement_channels or "").split(",") if c]

    @staticmethod
    def _what(borrow: BorrowRequest, setup) -> str:
        return "{0}{1}".format(setup.hostname, " ({0})".format(borrow.hardware_field_name) if borrow.hardware_field_name else "")

    # ------------------------------------------------------------------
    # Request
    # ------------------------------------------------------------------

    def create(self, payload: BorrowCreateRequest, acting_user: User) -> BorrowRequest:
        if not acting_user.role or acting_user.role.name not in BORROW_REQUESTER_ROLES:
            raise AuthorizationError("Only Group Leads and Managers may request a borrow.")
        if not acting_user.group_id:
            raise ValidationAppError("You must belong to a group to borrow on its behalf.")

        now = datetime.utcnow()
        if payload.end_time is not None and payload.end_time <= now:
            raise ValidationAppError("end_time must be in the future.")

        source_lead = self._user_repository.get_by_id(payload.source_lead_id)
        if source_lead is None:
            raise NotFoundError("Source lead with id {0} was not found.".format(payload.source_lead_id))
        if (
            source_lead.status != UserStatus.APPROVED or not source_lead.is_active
            or not source_lead.role or source_lead.role.name not in _LEAD_ROLES
        ):
            raise ValidationAppError("The selected source must be an active Lead or Manager.")

        setup = self._setup_repository.get_by_id(payload.setup_id)
        if setup is None:
            raise NotFoundError("Setup with id {0} was not found.".format(payload.setup_id))
        if setup.status in (SetupStatus.MAINTENANCE, SetupStatus.RETIRED):
            raise ConflictError("Setup {0} is currently {1} and cannot be borrowed.".format(setup.hostname, setup.status.lower()))
        if setup.group_id is None or setup.group_id not in _group_ids(source_lead):
            raise ValidationAppError("Setup {0} does not belong to the selected lead's group.".format(setup.hostname))

        source_group_id = setup.group_id
        borrower_group_id = acting_user.group_id
        if source_group_id == borrower_group_id:
            raise ConflictError("Your group already holds this setup; there is nothing to borrow.")

        if self._borrow_repository.get_active_grant_for_setup(setup.id) is not None:
            raise ConflictError("Setup {0} is already borrowed by another group.".format(setup.hostname))
        if self._borrow_repository.get_open_for_setup(setup.id) is not None:
            raise ConflictError("Setup {0} already has a pending or active borrow request.".format(setup.hostname))

        self._validate_field(setup, payload.hardware_field_name)

        routed = [u for u in self._routed_approvers(source_group_id) if u.id != acting_user.id]
        routed_emails = [u.email for u in routed if u.email]

        borrow = BorrowRequest(
            requester_id=acting_user.id,
            source_group_id=source_group_id,
            target_group_id=borrower_group_id,
            setup_id=setup.id,
            hardware_field_name=payload.hardware_field_name,
            reason=payload.reason,
            start_time=payload.start_time,
            end_time=payload.end_time,
            announcement_channels=",".join(payload.announcement_channels) if payload.announcement_channels else None,
            status=BorrowStatus.PENDING,
            routed_approver_emails=",".join(routed_emails) if routed_emails else None,
        )
        created = self._borrow_repository.create(borrow)
        self._audit_service.record(
            user_id=acting_user.id, action=AuditAction.CREATE, entity_type="BorrowRequest", entity_id=created.id,
            new_value={
                "setup_id": setup.id, "hardware_field_name": payload.hardware_field_name,
                "source_group_id": source_group_id, "target_group_id": borrower_group_id,
                "source_lead_id": source_lead.id, "routed_to": routed_emails,
            },
        )

        message = payload.announcement_message or "{0} requested to borrow {1} from group {2}. Approval needed.".format(
            acting_user.full_name, self._what(created, setup), source_group_id
        )
        self._notify(
            routed_emails, "Borrow approval needed: {0}".format(setup.hostname), message,
            payload.announcement_channels, setup, acting_user,
        )
        return created

    # ------------------------------------------------------------------
    # Approve / reject / cancel
    # ------------------------------------------------------------------

    def approve(self, borrow_id: int, payload: BorrowDecisionRequest, acting_user: User) -> BorrowRequest:
        self.expire_stale_pending()
        borrow = self.get_by_id(borrow_id)
        if borrow.status == BorrowStatus.EXPIRED:
            raise ConflictError("This borrow request's requested window has already ended and it has expired.")
        if borrow.status != BorrowStatus.PENDING:
            raise ConflictError("Only a PENDING borrow request can be approved.")

        setup = self._setup_repository.get_by_id(borrow.setup_id)
        if setup is None:
            raise NotFoundError("The setup in this borrow request no longer exists.")
        if setup.status in (SetupStatus.MAINTENANCE, SetupStatus.RETIRED):
            raise ConflictError("Setup {0} is currently {1} and can no longer be borrowed.".format(setup.hostname, setup.status.lower()))
        if self._borrow_repository.get_active_grant_for_setup(setup.id) is not None:
            raise ConflictError("Setup {0} is already borrowed by another group.".format(setup.hostname))
        if setup.group_id != borrow.source_group_id:
            raise ConflictError("Setup {0} no longer belongs to the requested source group; please raise a new request.".format(setup.hostname))

        self._assert_can_decide(borrow, acting_user)

        # ORIGINAL state is preserved: only a missing baseline may be created,
        # and Setup.group_id / hardware values are never touched.
        if self._hardware_state_service is not None:
            self._hardware_state_service.ensure_fixed_baseline(setup)

        self._borrow_repository.create_grant(SetupAccessGrant(
            setup_id=setup.id, borrow_request_id=borrow.id,
            source_group_id=borrow.source_group_id, granted_to_group_id=borrow.target_group_id, is_active=True,
        ))
        borrow.status = BorrowStatus.COMPLETED
        borrow.approved_by_id = acting_user.id
        updated = self._borrow_repository.update(borrow)
        self._audit_service.record(
            user_id=acting_user.id, action=AuditAction.APPROVE, entity_type="BorrowRequest", entity_id=updated.id,
            new_value={"granted_to_group_id": borrow.target_group_id, "note": payload.reason},
        )

        requester = self._user_repository.get_by_id(borrow.requester_id)
        if requester is not None:
            self._notify(
                [requester.email], "Borrow approved: {0}".format(setup.hostname),
                "Your borrow of {0} was approved by {1}. Please return it when you are done.".format(
                    self._what(borrow, setup), acting_user.full_name
                ),
                [], setup, acting_user,
            )
        return updated

    def reject(self, borrow_id: int, payload: BorrowDecisionRequest, acting_user: User) -> BorrowRequest:
        self.expire_stale_pending()
        borrow = self.get_by_id(borrow_id)
        if borrow.status == BorrowStatus.EXPIRED:
            raise ConflictError("This borrow request's requested window has already ended and it has expired.")
        if borrow.status != BorrowStatus.PENDING:
            raise ConflictError("Only a PENDING borrow request can be rejected.")
        self._assert_can_decide(borrow, acting_user)

        borrow.status = BorrowStatus.REJECTED
        borrow.approved_by_id = acting_user.id
        updated = self._borrow_repository.update(borrow)
        self._audit_service.record(
            user_id=acting_user.id, action=AuditAction.REJECT, entity_type="BorrowRequest", entity_id=updated.id,
            new_value={"note": payload.reason},
        )
        setup = self._setup_repository.get_by_id(borrow.setup_id)
        requester = self._user_repository.get_by_id(borrow.requester_id)
        if setup is not None and requester is not None:
            self._notify(
                [requester.email], "Borrow rejected: {0}".format(setup.hostname),
                "Your borrow request for {0} was rejected by {1}.{2}".format(
                    self._what(borrow, setup), acting_user.full_name, " Reason: {0}".format(payload.reason) if payload.reason else ""
                ),
                [], setup, acting_user,
            )
        return updated

    def cancel(self, borrow_id: int, acting_user: User) -> BorrowRequest:
        borrow = self.get_by_id(borrow_id)
        if borrow.requester_id != acting_user.id:
            raise AuthorizationError("You may only cancel your own borrow request.")
        if borrow.status != BorrowStatus.PENDING:
            raise ConflictError("Only a PENDING borrow request can be cancelled.")
        borrow.status = BorrowStatus.CANCELLED
        updated = self._borrow_repository.update(borrow)
        self._audit_service.record(
            user_id=acting_user.id, action=AuditAction.CANCEL, entity_type="BorrowRequest", entity_id=updated.id,
        )
        return updated

    # ------------------------------------------------------------------
    # Return / get back
    # ------------------------------------------------------------------

    def return_borrow(self, borrow_id: int, payload: BorrowReturnRequest, acting_user: User) -> BorrowRequest:
        borrow = self.get_by_id(borrow_id)
        if borrow.status == BorrowStatus.RETURNED:
            raise ConflictError("This borrow has already been returned.")
        if borrow.status != BorrowStatus.COMPLETED:
            raise ConflictError("Only an approved (currently borrowed) request can be returned.")
        self._assert_can_return(borrow, acting_user)

        grant = self._borrow_repository.get_grant_for_borrow(borrow.id)
        if grant is None or not grant.is_active:
            raise ConflictError("This borrow has no active access grant to close.")

        now = datetime.utcnow()
        grant.is_active = False
        grant.returned_at = now
        self._borrow_repository.update_grant(grant)  # effective access reverts to Setup.group_id (never changed)

        borrow.status = BorrowStatus.RETURNED
        borrow.returned_at = now
        borrow.returned_by_id = acting_user.id
        updated = self._borrow_repository.update(borrow)
        self._audit_service.record(
            user_id=acting_user.id, action=AuditAction.UPDATE, entity_type="BorrowRequest", entity_id=updated.id,
            old_value={"status": BorrowStatus.COMPLETED},
            new_value={"status": BorrowStatus.RETURNED, "restored_to_group_id": borrow.source_group_id, "note": payload.note},
        )
        self._audit_service.record(
            user_id=acting_user.id, action=AuditAction.UPDATE, entity_type="SetupAccessGrant", entity_id=grant.id,
            old_value={"is_active": True}, new_value={"is_active": False},
        )

        setup = self._setup_repository.get_by_id(borrow.setup_id)
        if setup is not None:
            requester = self._user_repository.get_by_id(borrow.requester_id)
            recipients: List[str] = []
            recipients.extend((borrow.routed_approver_emails or "").split(","))
            recipients.extend(u.email for u in self._routed_approvers(borrow.source_group_id))
            if requester is not None:
                recipients.append(requester.email)
            message = "{0} returned {1} to group {2}.{3}".format(
                acting_user.full_name, self._what(borrow, setup), borrow.source_group_id,
                " Note: {0}".format(payload.note) if payload.note else "",
            )
            self._notify(recipients, "Borrow returned: {0}".format(setup.hostname), message, self._channels(borrow), setup, acting_user)
        return updated


def _lead_filter():
    from app.schemas.user import UserFilter

    return UserFilter(status=UserStatus.APPROVED)
