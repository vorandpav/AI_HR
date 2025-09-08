# backend/services/stt_tts_client.py
import os
import aiohttp
import logging

logger = logging.getLogger("uvicorn.error")

STT_TTS_WS_URL = os.getenv("STT_TTS_WS_URL", "ws://localhost:8080/call")


class STTClient:
    def __init__(self, url: str = None):
        self.url = url or STT_TTS_WS_URL
        self._session = None
        logger.info(f"STT/TTS client will connect to: {self.url}")

    async def _ensure_session(self):
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout)

    async def connect(self):
        await self._ensure_session()
        logger.info(f"Connecting to STT/TTS service: {self.url}")
        try:
            ws = await self._session.ws_connect(self.url)
            logger.info("Successfully connected to STT/TTS service")
            return ws
        except Exception as e:
            logger.error(f"Failed to connect to STT/TTS service: {e}")
            raise

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()


_stt_client = None


def get_stt_client():
    global _stt_client
    if _stt_client is None:
        _stt_client = STTClient()
    return _stt_client
