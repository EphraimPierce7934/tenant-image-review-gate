from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Annotated, AsyncIterator

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from .infrai_images import InfraiError, InfraiImages
from .review_workflow import (
    AccountState,
    MissingRecord,
    ReviewLabel,
    ReviewWorkflow,
    WorkflowConflict,
)


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class AccountUpdate(BaseModel):
    state: AccountState


class ReviewDecision(BaseModel):
    label: ReviewLabel
    note: str | None = Field(default=None, max_length=500)


class TenantView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    state: AccountState


class SubmissionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    tenant_id: str
    filename: str
    infrai_image_id: str
    state: str
    review_label: ReviewLabel | None
    reviewer_note: str | None


workflow = ReviewWorkflow()


def build_infrai_client() -> InfraiImages:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise RuntimeError("INFRAI_API_KEY is required")
    return InfraiImages(api_key)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    application.state.images = build_infrai_client()
    yield
    await application.state.images.close()


service = FastAPI(title="Tenant image review gate", lifespan=lifespan)


def infrai_client() -> InfraiImages:
    return service.state.images


@service.exception_handler(MissingRecord)
async def missing_record_handler(_request, exc: MissingRecord):
    return _error_response(404, str(exc))


@service.exception_handler(WorkflowConflict)
async def conflict_handler(_request, exc: WorkflowConflict):
    return _error_response(409, str(exc))


def _error_response(status_code: int, detail: str):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=status_code, content={"detail": detail})


@service.post("/tenants", response_model=TenantView, status_code=201)
async def onboard_tenant(request: TenantCreate) -> object:
    return workflow.onboard_tenant(request.name)


@service.patch("/tenants/{tenant_id}", response_model=TenantView)
async def update_account(tenant_id: str, request: AccountUpdate) -> object:
    return workflow.set_account_state(tenant_id, request.state)


@service.post("/submissions", response_model=SubmissionView, status_code=201)
async def submit_image(
    tenant_id: Annotated[str, Form()],
    image: Annotated[UploadFile, File()],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    images: Annotated[InfraiImages, Depends(infrai_client)],
) -> object:
    content = await image.read()
    if not content:
        raise HTTPException(status_code=422, detail="image must not be empty")
    try:
        uploaded = await images.upload(
            content=content,
            filename=image.filename or "upload",
            idempotency_key=idempotency_key,
        )
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=client_status, detail=str(exc)) from exc

    image_id = uploaded.get("id")
    if not isinstance(image_id, str) or not image_id:
        raise HTTPException(status_code=502, detail="upload response did not include an image id")
    return workflow.submit_image(tenant_id, image.filename or "upload", image_id)


@service.post("/admin/submissions/{submission_id}/review", response_model=SubmissionView)
async def review_submission(submission_id: str, decision: ReviewDecision) -> object:
    return workflow.review_image(submission_id, decision.label, decision.note)


@service.get("/submissions/{submission_id}", response_model=SubmissionView)
async def submission_status(submission_id: str) -> object:
    return workflow.get_submission(submission_id)
