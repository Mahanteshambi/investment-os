import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from database.connection import get_connection, close_connection
from routers import holdings, portfolio, snapshots, sync
from scheduler.jobs import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Investment OS backend")
    get_connection()  # init DB + run migrations
    start_scheduler()
    yield
    stop_scheduler()
    close_connection()
    logger.info("Investment OS backend stopped")


app = FastAPI(
    title="Investment OS API",
    version="0.1.0",
    description="Personal investment portfolio backend",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(portfolio.router)
app.include_router(holdings.router)
app.include_router(snapshots.router)
app.include_router(sync.router)


# Stubbed agents endpoint
from fastapi import APIRouter
from models.schemas import AgentSignal

agents_router = APIRouter(prefix="/api/agents", tags=["agents"])


@agents_router.get("/signals", response_model=list[AgentSignal])
def get_agent_signals():
    now = datetime.now()
    return [
        AgentSignal(
            agent_name="MarketAnalyst",
            signal_type="market",
            signal_value="neutral",
            summary="Nifty 50 trading near 5-year median PE. FII flows cautious. No strong directional signal.",
            created_at=now,
        ),
        AgentSignal(
            agent_name="SectorRotation",
            signal_type="sector",
            signal_value="bullish",
            summary="Banking sector score 7/10 — highest this month. Overweight BANKBEES.",
            created_at=now,
        ),
        AgentSignal(
            agent_name="Rebalancer",
            signal_type="rebalance",
            signal_value="action_needed",
            summary="Gold allocation at 18% vs target 15%. Consider pausing GOLDBEES buys this week.",
            created_at=now,
        ),
    ]


app.include_router(agents_router)


@app.get("/health")
def health():
    from database.connection import get_db
    try:
        get_db().execute("SELECT 1").fetchone()
        db_status = "connected"
    except Exception:
        db_status = "error"
    return {"status": "ok", "db": db_status, "version": "0.1.0"}
