import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .database import engine, Base
from .routers import vacancies, resumes, meetings, ws
from .services.minio_client import get_minio_client, BUCKET_NAME

Base.metadata.create_all(bind=engine)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvicorn.error")

app = FastAPI(
    title="AI-HR API",
    description="API для системы AI-рекрутинга с поддержкой видео-интервью.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- События жизненного цикла ---
@app.on_event("startup")
async def startup_event():
    """Проверяет и создает бакет в MinIO при старте приложения."""
    try:
        minio_client = get_minio_client()
        found = minio_client.client.bucket_exists(BUCKET_NAME)
        if not found:
            minio_client.client.make_bucket(BUCKET_NAME)
            logger.info(f"Bucket '{BUCKET_NAME}' created in MinIO.")
        else:
            logger.info(f"Bucket '{BUCKET_NAME}' already exists in MinIO.")
    except Exception as e:
        logger.error(f"Failed to connect to MinIO or create bucket: {e}")


app.include_router(vacancies.router, prefix="/vacancies", tags=["Vacancies"])
app.include_router(resumes.router, prefix="/resumes", tags=["Resumes"])
app.include_router(meetings.router, prefix="/meetings", tags=["Meetings"])
app.include_router(ws.router, tags=["WebSocket Calls"])

app.mount("/static", StaticFiles(directory="backend/static"), name="static")


@app.get("/", tags=["Root"])
async def read_root():
    """Корневой эндпоинт для проверки работоспособности API."""
    return {"message": "Welcome to AI-HR API"}
