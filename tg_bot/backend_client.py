# tg_bot/backend_client.py
import httpx
from typing import List, Optional, Dict, Tuple
import os


class BackendClient:
    """
    Асинхронный клиент для взаимодействия с API нашего бэкенда.
    """

    def __init__(self, base_url: str):
        self._client = httpx.AsyncClient(base_url=base_url, timeout=30.0)

    async def close(self):
        """Закрывает сессию клиента."""
        await self._client.close()

    def _get_auth_header(self, telegram_username: str) -> Dict[str, str]:
        """Генерирует заголовок аутентификации для пользователя."""
        return {"X-Telegram-User": telegram_username}

    # --- Вакансии ---
    async def post_vacancy(self, title: str, username: str, user_id: str, file_bytes: bytes, filename: str) -> Dict:
        """Публикует новую вакансию."""
        headers = self._get_auth_header(username)
        files = {"file": (filename, file_bytes)}
        data = {"title": title, "user_id": user_id}

        response = await self._client.post("/vacancies/", headers=headers, data=data, files=files)
        response.raise_for_status()
        return response.json()

    async def get_my_vacancies(self, username: str) -> List[Dict]:
        """Получает список вакансий пользователя."""
        headers = self._get_auth_header(username)
        response = await self._client.get("/vacancies/", headers=headers)
        response.raise_for_status()
        return response.json()

    # --- Резюме и Анализ ---
    async def post_resume(self, vacancy_id: int, username: str, user_id: str, file_bytes: bytes, filename: str) -> Dict:
        """Отправляет отклик на вакансию."""
        headers = self._get_auth_header(username)
        files = {"file": (filename, file_bytes)}
        data = {"vacancy_id": str(vacancy_id), "user_id": user_id}

        response = await self._client.post("/resumes/", headers=headers, data=data, files=files)
        response.raise_for_status()
        return response.json()

    async def get_resumes_for_vacancy(self, vacancy_id: int, username: str) -> List[Dict]:
        """Получает список откликов на вакансию."""
        headers = self._get_auth_header(username)
        params = {"vacancy_id": vacancy_id}

        response = await self._client.get("/resumes/", headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    async def get_resume(self, resume_id: int, username: str) -> Optional[Dict]:
        """Получает полную информацию о резюме"""
        headers = self._get_auth_header(username)
        response = await self._client.get(f"/resumes/{resume_id}", headers=headers)
        response.raise_for_status()
        return response.json()

    # --- Встречи и Записи ---
    async def create_meeting(self, resume_id: int, username: str) -> Dict:
        """Создает встречу для резюме."""
        headers = self._get_auth_header(username)
        params = {"resume_id": resume_id}

        response = await self._client.post("/meetings/", headers=headers, params=params)
        response.raise_for_status()
        return response.json()
