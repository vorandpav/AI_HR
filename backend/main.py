import logging

import anyio
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import database, models
from .routers import meetings, resumes, users, vacancies, ws
from .services import analysis_service
from .utils import s3_async

logger = logging.getLogger("uvicorn.error")
app = FastAPI()


@app.on_event("startup")
async def startup_event():
    await anyio.to_thread.run_sync(models.Base.metadata.create_all, database.engine)
    try:
        await s3_async.ensure_bucket()
    except Exception as e:
        logger.warning("Could not ensure S3 bucket: %s", e)


app.include_router(vacancies.router, prefix="/vacancies", tags=["vacancies"])
app.include_router(resumes.router, prefix="/resumes", tags=["resumes"])
app.include_router(similarity.router, prefix="/similarity", tags=["similarity"])
app.include_router(users.router, prefix="/user", tags=["user"])
app.include_router(meetings.router, prefix="", tags=["meetings"])
app.include_router(ws.router, prefix="", tags=["call"])

app.mount("/static", StaticFiles(directory="backend/static"), name="static")
