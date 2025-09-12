import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routers import meetings, resumes, users, vacancies, ws

logger = logging.getLogger("uvicorn.error")
app = FastAPI()

app.include_router(vacancies.router, prefix="/vacancies", tags=["vacancies"])
app.include_router(resumes.router, prefix="/resumes", tags=["resumes"])
app.include_router(users.router, prefix="/user", tags=["user"])
app.include_router(meetings.router, prefix="", tags=["meetings"])
app.include_router(ws.router, prefix="", tags=["call"])

app.mount("/static", StaticFiles(directory="backend/static"), name="static")
