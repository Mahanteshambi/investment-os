import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from database.connection import get_connection, close_connection
from routers import holdings, portfolio, snapshots, sync, intelligence, sector_rotation, world_view, transactions
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
app.include_router(world_view.router)
app.include_router(intelligence.router)
app.include_router(sector_rotation.router)
app.include_router(transactions.router)


@app.get("/health")
def health():
    from database.connection import get_db
    try:
        get_db().execute("SELECT 1").fetchone()
        db_status = "connected"
    except Exception:
        db_status = "error"
    return {"status": "ok", "db": db_status, "version": "0.1.0"}
