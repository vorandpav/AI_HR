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
    Ключ словаря - токен встречи, значение - множество активных сокетов.
    """

    def __init__(self):
        self.active_connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, websocket: WebSocket, meeting_token: str):
        """Регистрирует новое соединение."""
        await websocket.accept()
        self.active_connections[meeting_token].add(websocket)
        logger.info(
            f"Новое WebSocket-соединение для встречи {meeting_token}. Всего участников: {len(self.active_connections[meeting_token])}")

    def disconnect(self, websocket: WebSocket, meeting_token: str):
        """Удаляет соединение."""
        self.active_connections[meeting_token].remove(websocket)
        logger.info(f"WebSocket-соединение для встречи {meeting_token} закрыто.")
        # Если в комнате никого не осталось, удаляем ее из словаря
        if not self.active_connections[meeting_token]:
            del self.active_connections[meeting_token]

    async def broadcast_to_others(self, message: bytes, meeting_token: str, sender: WebSocket):
        """Отправляет сообщение всем участникам встречи, кроме отправителя."""
        # Копируем множество, чтобы избежать проблем при изменении во время итерации
        for connection in list(self.active_connections.get(meeting_token, set())):
            if connection is not sender:
                try:
                    await connection.send_bytes(message)
                except (WebSocketDisconnect, RuntimeError):
                    # Если сокет уже закрыт, просто игнорируем
                    pass


# Создаем единственный экземпляр менеджера, который будет жить, пока живо приложение
manager = ConnectionManager()


@router.websocket("/ws/{token}")
async def websocket_endpoint(
        websocket: WebSocket,
        token: str,
        # Эти зависимости проверяют, что пользователь имеет право на доступ к встрече
        user: str = Depends(get_current_user),
        meeting: models.Meeting = Depends(get_meeting_for_authorized_user),
        db: Session = Depends(database.get_db),
):
    """
    Основной эндпоинт для WebSocket-коммуникации во время звонка.
    """
    # Шаг 1: Подключаем и регистрируем пользователя в менеджере
    await manager.connect(websocket, meeting.token)

    # Определяем "роль" пользователя в этом звонке для сохранения аудио
    role = "organizer" if user == meeting.organizer_username else "candidate"

    try:
        # Шаг 2: Бесконечный цикл приема, пересылки и сохранения аудио
        while True:
            # Принимаем аудио-чанк от клиента
            data = await websocket.receive_bytes()

            # Пересылаем его другому участнику
            await manager.broadcast_to_others(data, meeting.token, websocket)

            # В фоне (не блокируя основной поток) сохраняем чанк в MinIO и БД
            asyncio.create_task(
                save_chunk_in_background(db, data, meeting.id, role)
            )

    except WebSocketDisconnect:
        logger.info(f"Клиент {user} отключился от встречи {meeting.token}.")
    except Exception as e:
        logger.error(f"Произошла ошибка в WebSocket для встречи {meeting.token}: {e}", exc_info=True)
    finally:
        # Шаг 3: Гарантированно отключаем пользователя от менеджера при выходе
        manager.disconnect(websocket, meeting.token)


async def save_chunk_in_background(db: Session, data: bytes, meeting_id: int, role: str):
    """
    Асинхронная обертка для сохранения аудио-чанка.
    Нужна, чтобы безопасно работать с сессией БД в фоновой задаче.
    """
    try:
        # Используем синхронную функцию, но вызываем ее в асинхронном контексте
        file_service.save_audio_chunk(
            db=db,
            data=data,
            session_id=str(meeting_id),  # Используем ID встречи как ID сессии
            role=role,
        )
    except Exception as e:
        logger.error(f"Ошибка при сохранении аудио-чанка в фоне: {e}")
