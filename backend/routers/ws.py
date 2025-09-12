import asyncio
import logging
from collections import defaultdict

from fastapi import APIRouter, WebSocket, Depends, WebSocketDisconnect
from sqlalchemy.orm import Session

from .. import database, models
from ..dependencies import get_meeting_for_authorized_user, get_current_user
from ..services import file_service

logger = logging.getLogger("uvicorn.error")
router = APIRouter()


class ConnectionManager:
    """
    Управляет активными WebSocket-соединениями для каждой встречи.
    """

    def __init__(self):
        self.active_connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, meeting_token: str):
        await websocket.accept()
        self.active_connections[meeting_token].add(websocket)
        logger.info(
            f"New WebSocket connection for meeting {meeting_token}. Total participants: {len(self.active_connections[meeting_token])}")

    def disconnect(self, websocket: WebSocket, meeting_token: str):
        if websocket in self.active_connections[meeting_token]:
            self.active_connections[meeting_token].remove(websocket)
        logger.info(f"WebSocket connection for meeting {meeting_token} closed.")
        if not self.active_connections[meeting_token]:
            del self.active_connections[meeting_token]

    async def broadcast_to_others(self, message: bytes, meeting_token: str, sender: WebSocket):
        for connection in list(self.active_connections.get(meeting_token, set())):
            if connection is not sender:
                try:
                    await connection.send_bytes(message)
                except (WebSocketDisconnect, RuntimeError):
                    pass


manager = ConnectionManager()


@router.websocket("/ws/{token}")
async def websocket_endpoint(
        websocket: WebSocket,
        token: str,
        user: str = Depends(get_current_user),
        meeting: models.Meeting = Depends(get_meeting_for_authorized_user),
):
    """
    Основной эндпоинт для WebSocket-коммуникации во время звонка.
    """
    await manager.connect(websocket, meeting.token)
    role = "organizer" if user == meeting.organizer_username else "candidate"

    try:
        while True:
            data = await websocket.receive_bytes()
            await manager.broadcast_to_others(data, meeting.token, websocket)
            asyncio.create_task(
                save_chunk_in_background(data, meeting.id, role)
            )

    except WebSocketDisconnect:
        logger.info(f"Client {user} disconnected from meeting {meeting.token}.")
    except Exception as e:
        logger.error(f"An error occurred in WebSocket for meeting {meeting.token}: {e}", exc_info=True)
    finally:
        manager.disconnect(websocket, meeting.token)


async def save_chunk_in_background(data: bytes, meeting_id: int, role: str):
    """
    Асинхронная фоновая задача, которая создает собственную сессию БД.
    """
    db: Session = next(database.get_db())
    try:
        file_service.save_audio_chunk(
            db=db,
            data=data,
            session_id=str(meeting_id),
            role=role,
        )
    except Exception as e:
        logger.error(f"Error saving audio chunk in background: {e}")
    finally:
        db.close()
