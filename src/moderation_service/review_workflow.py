from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from threading import RLock
from uuid import uuid4


class AccountState(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class ReviewLabel(StrEnum):
    SAFE = "safe"
    SENSITIVE = "sensitive"
    BLOCKED = "blocked"


class ImageState(StrEnum):
    PENDING_REVIEW = "pending_review"
    LIVE = "live"
    HELD = "held"
    REJECTED = "rejected"


@dataclass
class Tenant:
    id: str
    name: str
    state: AccountState = AccountState.ACTIVE


@dataclass
class Submission:
    id: str
    tenant_id: str
    filename: str
    infrai_image_id: str
    state: ImageState = ImageState.PENDING_REVIEW
    review_label: ReviewLabel | None = None
    reviewer_note: str | None = None


class WorkflowConflict(Exception):
    pass


class MissingRecord(Exception):
    pass


class ReviewWorkflow:
    def __init__(self) -> None:
        self._tenants: dict[str, Tenant] = {}
        self._submissions: dict[str, Submission] = {}
        self._lock = RLock()

    def onboard_tenant(self, name: str) -> Tenant:
        with self._lock:
            tenant = Tenant(id=str(uuid4()), name=name)
            self._tenants[tenant.id] = tenant
            return tenant

    def set_account_state(self, tenant_id: str, state: AccountState) -> Tenant:
        with self._lock:
            tenant = self._tenant(tenant_id)
            if tenant.state == AccountState.CLOSED and state != AccountState.CLOSED:
                raise WorkflowConflict("a closed account cannot be reopened")
            tenant.state = state
            return tenant

    def submit_image(
        self, tenant_id: str, filename: str, infrai_image_id: str
    ) -> Submission:
        with self._lock:
            tenant = self._tenant(tenant_id)
            if tenant.state != AccountState.ACTIVE:
                raise WorkflowConflict("only active accounts can submit images")
            submission = Submission(
                id=str(uuid4()),
                tenant_id=tenant_id,
                filename=filename,
                infrai_image_id=infrai_image_id,
            )
            self._submissions[submission.id] = submission
            return submission

    def review_image(
        self, submission_id: str, label: ReviewLabel, note: str | None
    ) -> Submission:
        with self._lock:
            submission = self._submission(submission_id)
            if submission.state != ImageState.PENDING_REVIEW:
                raise WorkflowConflict("only pending images can be reviewed")
            submission.review_label = label
            submission.reviewer_note = note
            submission.state = {
                ReviewLabel.SAFE: ImageState.LIVE,
                ReviewLabel.SENSITIVE: ImageState.HELD,
                ReviewLabel.BLOCKED: ImageState.REJECTED,
            }[label]
            return submission

    def get_submission(self, submission_id: str) -> Submission:
        with self._lock:
            return self._submission(submission_id)

    def _tenant(self, tenant_id: str) -> Tenant:
        try:
            return self._tenants[tenant_id]
        except KeyError as exc:
            raise MissingRecord("tenant not found") from exc

    def _submission(self, submission_id: str) -> Submission:
        try:
            return self._submissions[submission_id]
        except KeyError as exc:
            raise MissingRecord("submission not found") from exc

