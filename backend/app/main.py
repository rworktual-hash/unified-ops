from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agent_actions import router as agent_router
from app.api.chat import router as chat_router
from app.api.approvals import router as approvals_router
from app.api.alerts import router as alerts_router
from app.api.servers import router as servers_router
from app.config import settings
from app.db.session import Base, engine
from app.models import agent_action as _agent_action_model  # noqa: F401
from app.models import approval_request as _approval_request_model  # noqa: F401
from app.models import alert as _alert_model  # noqa: F401
from app.models import gpu_metric as _gpu_metric_model  # noqa: F401
from app.models import server as _server_model  # noqa: F401
from app.models import server_metric as _server_metric_model  # noqa: F401


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Unified Ops API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(servers_router)
app.include_router(alerts_router)
app.include_router(agent_router)
app.include_router(approvals_router)
app.include_router(chat_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
