"""Health check endpoints with dependency checking."""

import os
import shutil
import time

from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

router = APIRouter()
_start_time = time.time()


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness() -> dict[str, object]:
    checks: dict[str, str] = {}

    try:
        db_url = os.environ.get("DATABASE_URL")
        if db_url:
            engine = create_async_engine(db_url)
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            await engine.dispose()
            checks["database"] = "ok"
        else:
            checks["database"] = "not_configured"
    except Exception as e:
        checks["database"] = f"error: {e}"

    if shutil.which("cbc") or os.environ.get("CBC_PATH"):
        checks["solver"] = "available"
    else:
        checks["solver"] = "missing"

    all_ok = all(v in ("ok", "available") for v in checks.values())
    return {
        "status": "ready" if all_ok else "degraded",
        "checks": checks,
        "uptime_seconds": time.time() - _start_time,
    }
