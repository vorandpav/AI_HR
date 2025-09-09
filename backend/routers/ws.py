import asyncio
import logging
import uuid

import aiohttp
import anyio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends

from .dependencies import get_current_user
from ..services.meeting_service import finish_meeting_sync, get_meeting_by_token
from backend.services.audio_store import save_audio_chunk_sync
from backend.services.stt_tts_client import STTClient, get_stt_client

logger = logging.getLogger("uvicorn.error")
router = APIRouter()


async def client_to_stt(
        client_ws: WebSocket, stt_ws: aiohttp.ClientWebSocketResponse, session_id: str
):
    """Принимает аудио от клиента, сохраняет и пересылает в STT/TTS сервис."""
    try:
        while True:
            data = await client_ws.receive_bytes()
            if data:
                # Сохраняем аудио клиента
                try:
                    await anyio.to_thread.run_sync(
                        save_audio_chunk_sync,
                        data,
                        session_id,
                        "participant",
                        "audio/webm",
                    )
                    logger.debug(f"Saved client audio chunk for session {session_id}")
                except Exception as e:
                    logger.exception(
                        "Failed saving client audio chunk for session %s", session_id
                    )

                # Пересылаем байты в STT/TTS сервис
                if not stt_ws.closed:
                    await stt_ws.send_bytes(data)
    except WebSocketDisconnect:
        logger.info("Client disconnected (client_to_stt)")
    except Exception as e:
        logger.exception("Error in client_to_stt: %s", e)
    finally:
        try:
            if not stt_ws.closed:
                await stt_ws.send_str("end_session")
        except Exception as e:
            logger.warning(f"Could not send end_session to STT/TTS: {e}")


async def stt_to_client(
        stt_ws: aiohttp.ClientWebSocketResponse, client_ws: WebSocket, session_id: str
):
    """Принимает аудио/текст от STT/TTS сервиса, сохраняет и пересылает клиенту."""
    try:
        while True:
            msg = await stt_ws.receive()
            if msg.type == aiohttp.WSMsgType.BINARY:
                # Сохраняем аудио STT/TTS
                try:
                    await anyio.to_thread.run_sync(
                        save_audio_chunk_sync,
                        msg.data,
                        session_id,
                        "stt_tts",
                        "audio/webm",
                    )
                    logger.debug(f"Saved STT/TTS audio chunk for session {session_id}")
                except Exception as e:
                    logger.exception(
                        "Failed saving STT audio chunk for session %s", session_id
                    )
                await client_ws.send_bytes(msg.data)
            elif msg.type == aiohttp.WSMsgType.TEXT:
                await client_ws.send_text(msg.data)
            elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                break
    except Exception as e:
        logger.exception("Error in stt_to_client: %s", e)
    finally:
        try:
            if client_ws.client_state.name == "CONNECTED":
                await client_ws.close()
        except Exception as e:
            logger.warning(f"Could not close client websocket: {e}")


@router.websocket("/ws/{token}")
async def meeting_websocket(
        websocket: WebSocket,
        token: str,
        user: str = Depends(get_current_user),
):
    await websocket.accept()
    session_id = uuid.uuid4().hex

    # Проверка токена и состояния встречи
    meeting = await anyio.to_thread.run_sync(get_meeting_by_token, token)
    if not meeting:
        logger.warning(f"Invalid token attempted: {token}")
        await websocket.close(code=4001, reason="Invalid token")
        return

    if meeting.is_finished:
        logger.warning(f"Attempt to use finished meeting token: {token}")
        await websocket.close(code=4002, reason="Meeting already finished")
        return

    logger.info(
        "New call session %s for meeting %d (token=%s)", session_id, meeting.id, token
    )

    stt_ws = None
    temp_stt_client = None
    tasks = []

    try:
        stt_client = get_stt_client()
        stt_url_with_token = f"{stt_client.url}/{token}"
        temp_stt_client = STTClient(stt_url_with_token)
        stt_ws = await temp_stt_client.connect()
        logger.info(
            "Successfully connected to STT/TTS service for session %s", session_id
        )

        task_client_to_stt = asyncio.create_task(
            client_to_stt(websocket, stt_ws, session_id)
        )
        task_stt_to_client = asyncio.create_task(
            stt_to_client(stt_ws, websocket, session_id)
        )

        tasks = [task_client_to_stt, task_stt_to_client]

        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        logger.info(
            f"Call session {session_id} tasks completed. Done: {len(done)}, Pending: {len(pending)}"
        )
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    except Exception as e:
        logger.exception(
            "Failed to establish or maintain connection for session %s: %s",
            session_id,
            e,
        )
        if websocket.client_state.name == "CONNECTED":
            await websocket.close(code=1011, reason="Internal server error")
    finally:
        logger.info("Cleaning up resources for session %s", session_id)
        if stt_ws and not stt_ws.closed:
            try:
                await stt_ws.close()
            except Exception as e:
                logger.warning(f"Error closing STT/TTS connection: {e}")
        if temp_stt_client:
            try:
                await temp_stt_client.close()
            except Exception as e:
                logger.warning(f"Error closing STT/TTS client session: {e}")
        if websocket.client_state.name == "CONNECTED":
            try:
                await websocket.close()
            except Exception as e:
                logger.warning(f"Error closing client WebSocket connection: {e}")
        try:
            await anyio.to_thread.run_sync(finish_meeting_sync, token, session_id)
            logger.info("Meeting for token %s marked as finished in DB.", token)
        except Exception as e:
            logger.exception(
                "Failed to finish meeting for token %s in DB: %s", token, e
            )
        # Запуск пост-обработки (объединение аудио)
        try:
            from backend.services import post_processing
            asyncio.create_task(
                post_processing.process_and_merge_audio(meeting.id, session_id)
            )
            logger.info(
                f"Post-processing task scheduled for meeting {meeting.id}, session {session_id}"
            )
        except Exception as e:
            logger.exception(
                f"Failed to schedule post-processing for meeting {meeting.id}: {e}"
            )
