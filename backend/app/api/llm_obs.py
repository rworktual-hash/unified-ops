from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, get_current_user
from app.db.session import get_db
from app.models.llm_obs import LlmObsProject
from app.schemas.llm_obs import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyPublic,
    IngestBody,
    IngestResult,
    ProjectCreate,
    ProjectPublic,
    SummaryPublic,
    TraceDetail,
    TraceListItem,
)
from app.services.llm_obs import (
    LlmObsConflict,
    LlmObsRejected,
    create_api_key,
    create_project,
    get_owned_project,
    get_trace,
    ingest,
    list_api_keys,
    list_projects,
    list_traces,
    match_api_key,
    revoke_api_key,
    summarize,
)

dashboard_router = APIRouter(prefix="/llm-obs", tags=["llm-obs"])
ingest_router = APIRouter(prefix="/llm-obs", tags=["llm-obs-ingest"])
_bearer = HTTPBearer(auto_error=False)


def _key_public(row) -> ApiKeyPublic:
    return ApiKeyPublic(
        id=row.id,
        project_id=row.project_id,
        name=row.name,
        key_prefix=row.key_prefix,
        created_at=row.created_at,
        last_used_at=row.last_used_at,
        revoked=row.revoked_at is not None,
    )


def _project_or_404(db: Session, user: CurrentUser, project_id: int) -> LlmObsProject:
    row = get_owned_project(db, user, project_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return row


@dashboard_router.get("/projects", response_model=list[ProjectPublic])
def projects(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> list[LlmObsProject]:
    return list_projects(db, user)


@dashboard_router.post("/projects", response_model=ProjectPublic, status_code=status.HTTP_201_CREATED)
def add_project(
    payload: ProjectCreate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LlmObsProject:
    try:
        return create_project(db, user, payload.name, payload.display_name)
    except LlmObsRejected as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message) from exc
    except LlmObsConflict:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Project name already exists") from None


@dashboard_router.get("/projects/{project_id}/keys", response_model=list[ApiKeyPublic])
def project_keys(
    project_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ApiKeyPublic]:
    _project_or_404(db, user, project_id)
    return [_key_public(row) for row in list_api_keys(db, project_id)]


@dashboard_router.post(
    "/projects/{project_id}/keys",
    response_model=ApiKeyCreated,
    status_code=status.HTTP_201_CREATED,
)
def add_key(
    project_id: int,
    payload: ApiKeyCreate,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiKeyCreated:
    project = _project_or_404(db, user, project_id)
    row, raw = create_api_key(db, project, payload.name)
    created = _key_public(row)
    return ApiKeyCreated(**created.model_dump(), api_key=raw)


@dashboard_router.post("/projects/{project_id}/keys/{key_id}/revoke", response_model=ApiKeyPublic)
def revoke_key(
    project_id: int,
    key_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiKeyPublic:
    _project_or_404(db, user, project_id)
    row = revoke_api_key(db, project_id, key_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    return _key_public(row)


@dashboard_router.get("/summary", response_model=SummaryPublic)
def summary(
    project_id: int | None = None,
    model: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    started_from: datetime | None = Query(default=None, alias="from"),
    started_to: datetime | None = Query(default=None, alias="to"),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SummaryPublic:
    if project_id is not None:
        _project_or_404(db, user, project_id)
    return summarize(
        db,
        user,
        project_id=project_id,
        model=model or None,
        status=status_filter,
        started_from=started_from,
        started_to=started_to,
    )


@dashboard_router.get("/traces", response_model=list[TraceListItem])
def traces(
    project_id: int | None = None,
    model: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    started_from: datetime | None = Query(default=None, alias="from"),
    started_to: datetime | None = Query(default=None, alias="to"),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TraceListItem]:
    if project_id is not None:
        _project_or_404(db, user, project_id)
    return list_traces(
        db,
        user,
        project_id=project_id,
        model=model or None,
        status=status_filter,
        started_from=started_from,
        started_to=started_to,
    )


@dashboard_router.get("/traces/{trace_id}", response_model=TraceDetail)
def trace_detail(
    trace_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TraceDetail:
    row = get_trace(db, user, trace_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trace not found")
    return row


def _ingest_key(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    x_api_key: str | None = Header(default=None, alias="X-Api-Key"),
    db: Session = Depends(get_db),
):
    raw = (x_api_key or "").strip()
    if not raw and creds is not None and creds.scheme.lower() == "bearer":
        raw = creds.credentials.strip()
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key required")
    row = match_api_key(db, raw)
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return row


@ingest_router.post("/ingest", response_model=IngestResult, status_code=status.HTTP_201_CREATED)
def ingest_trace(
    payload: IngestBody,
    key=Depends(_ingest_key),
    db: Session = Depends(get_db),
) -> IngestResult:
    try:
        return ingest(db, key, payload)
    except LlmObsRejected as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.message) from exc
    except LlmObsConflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Trace id already exists for this project",
        ) from None
