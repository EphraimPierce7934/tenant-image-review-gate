import pytest

from moderation_service.review_workflow import (
    AccountState,
    ImageState,
    ReviewLabel,
    ReviewWorkflow,
    WorkflowConflict,
)


def test_admin_decision_controls_publish_state() -> None:
    workflow = ReviewWorkflow()
    tenant = workflow.onboard_tenant("Atlas Creators")

    safe = workflow.submit_image(tenant.id, "profile.jpg", "img_safe")
    blocked = workflow.submit_image(tenant.id, "banner.jpg", "img_blocked")

    assert workflow.review_image(safe.id, ReviewLabel.SAFE, None).state == ImageState.LIVE
    assert (
        workflow.review_image(blocked.id, ReviewLabel.BLOCKED, "Policy match").state
        == ImageState.REJECTED
    )


def test_suspended_tenant_cannot_submit() -> None:
    workflow = ReviewWorkflow()
    tenant = workflow.onboard_tenant("Paused Studio")
    workflow.set_account_state(tenant.id, AccountState.SUSPENDED)

    with pytest.raises(WorkflowConflict, match="only active accounts"):
        workflow.submit_image(tenant.id, "new-cover.jpg", "img_paused")

