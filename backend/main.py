from fastapi import FastAPI
from contextlib import asynccontextmanager

from backend.db.database import engine
from backend.db.models import Base
from backend import jobs

@asynccontextmanager
async def lifespan(app: FastAPI):
    # run on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield  # app running and accepting requests

    # run on shutdown
    await engine.dispose()  # clean up db connections

app = FastAPI(lifespan=lifespan)

@app.get("/api/health")
def health_check():
    return {"status": "CanopyID API is operational"}


app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])