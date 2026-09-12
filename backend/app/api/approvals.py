from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.approval_request import ApprovalRequest
from app.models.server import Server
from app.schemas.approval import ApprovalCreate, ApprovalDecision, ApprovalRead, ApprovalReadWithServer
from app.services.approval_flow import approve_request, create_approval_request, reject_request

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("", response_model=list[ApprovalReadWithServer])
def list_approvals(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[ApprovalReadWithServer]:
    q = db.query(ApprovalRequest, Server).join(Server, ApprovalRequest.server_id == Server.id)
    if status_filter:
        q = q.filter(ApprovalRequest.status == status_filter)
    rows = q.order_by(ApprovalRequest.created_at.desc()).limit(limit).all()
    out: list[ApprovalReadWithServer] = []
    for req, server in rows:
        out.append(
            ApprovalReadWithServer(
                id=req.id,
                server_id=req.server_id,
                alert_id=req.alert_id,
                action_key=req.action_key,
                action_params=req.action_params,
                status=req.status,
                request_notes=req.request_notes,
                requested_by=req.requested_by,
                decided_by=req.decided_by,
                execution_result=req.execution_result,
                created_at=req.created_at,
                decided_at=req.decided_at,
                executed_at=req.executed_at,
                server_name=server.server_name,
                ip_address=server.ip_address,
            )
        )
    return out


@router.post("", response_model=ApprovalRead, status_code=status.HTTP_201_CREATED)
def create_approval(payload: ApprovalCreate, db: Session = Depends(get_db)) -> ApprovalRequest:
    try:
        return create_approval_request(
            db,
            server_id=payload.server_id,
            action_key=payload.action_key,
            action_params=payload.action_params,
            alert_id=payload.alert_id,
            request_notes=payload.request_notes,
            requested_by=payload.requested_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{approval_id}/approve", response_model=ApprovalRead)
def approve(approval_id: int, body: ApprovalDecision, db: Session = Depends(get_db)) -> ApprovalRequest:
    try:
        return approve_request(db, approval_id, decided_by=body.decided_by)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{approval_id}/reject", response_model=ApprovalRead)
def reject(approval_id: int, body: ApprovalDecision, db: Session = Depends(get_db)) -> ApprovalRequest:
    try:
        return reject_request(db, approval_id, decided_by=body.decided_by)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
