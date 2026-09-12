from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.agent_action import AgentAction
from app.schemas.agent_action import AgentActionRead, InvestigationResponse
from app.services.investigation import InvestigationNotAllowed, run_investigation

router = APIRouter(tags=["agent"])


@router.get("/agent-actions", response_model=list[AgentActionRead])
def list_agent_actions(
    server_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[AgentAction]:
    q = db.query(AgentAction)
    if server_id is not None:
        q = q.filter(AgentAction.server_id == server_id)
    return q.order_by(AgentAction.created_at.desc()).limit(limit).all()


@router.post("/servers/{server_id}/investigate", response_model=InvestigationResponse)
def investigate_server(server_id: int, db: Session = Depends(get_db)) -> InvestigationResponse:
    try:
        return run_investigation(db, server_id=server_id, alert_id=None)
    except InvestigationNotAllowed as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
