# tg_bot/backend_client.py
from typing import Optional, Tuple

import aiohttp


class BackendClient:
    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")

    async def post_vacancy(
        self,
        title: str,
        telegram_username: str,
        telegram_user_id: str,
        file_bytes: bytes,
        filename: str,
        mime: Optional[str] = None,
        timeout=15,
    ):
        form = aiohttp.FormData()
        form.add_field("title", title)
        form.add_field("telegram_username", telegram_username)
        form.add_field("telegram_user_id", telegram_user_id)
        if file_bytes is not None:
            form.add_field(
                "file",
                file_bytes,
                filename=filename or "file",
                content_type=mime or "application/octet-stream",
            )
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base}/vacancies/",
                data=form,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                resp.raise_for_status()
                return await resp.json()

    async def get_vacancy(self, vacancy_id: int):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base}/vacancies/{vacancy_id}") as resp:
                resp.raise_for_status()
                return await resp.json()

    async def post_resume(
        self,
        vacancy_id: int,
        telegram_username: str,
        telegram_user_id: str,
        file_bytes: bytes,
        filename: str,
        mime: str,
        timeout=30,
    ):
        form = aiohttp.FormData()
        form.add_field("vacancy_id", str(vacancy_id))
        form.add_field("telegram_username", telegram_username)
        form.add_field("telegram_user_id", telegram_user_id)
        form.add_field(
            "file",
            file_bytes,
            filename=filename,
            content_type=mime or "application/octet-stream",
        )
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base}/resumes/",
                data=form,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                resp.raise_for_status()
                return await resp.json()

    async def get_resumes_for_vacancy(self, vacancy_id: int, x_telegram_user: str):
        headers = {"X-Telegram-User": x_telegram_user}
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(f"{self.base}/resumes/vacancy/{vacancy_id}") as resp:
                resp.raise_for_status()
                return await resp.json()

    async def download_resume_bytes(self, resume_id: int, x_telegram_user: str):
        headers = {"X-Telegram-User": x_telegram_user}
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(f"{self.base}/resumes/{resume_id}/download") as resp:
                resp.raise_for_status()
                return (
                    await resp.read(),
                    resp.headers.get("Content-Type"),
                    resp.headers.get("Content-Disposition"),
                )

    async def get_resume(self, resume_id: int, x_telegram_user: str):
        headers = {"X-Telegram-User": x_telegram_user} if x_telegram_user else {}
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(f"{self.base}/resumes/{resume_id}") as resp:
                resp.raise_for_status()
                return await resp.json()

    async def get_similarity(self, resume_id: int, x_telegram_user: str):
        headers = {"X-Telegram-User": x_telegram_user} if x_telegram_user else {}
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(
                f"{self.base}/similarity/resume/{resume_id}"
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                raise aiohttp.ClientResponseError(
                    resp.request_info,
                    resp.history,
                    status=resp.status,
                    message=await resp.text(),
                )

    async def arrange_meeting(self, resume_id: int, organizer_username: str):
        headers = {"X-Telegram-User": organizer_username}
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(
                f"{self.base}/arrange_meeting",
                json={"resume_id": resume_id},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                resp.raise_for_status()
                return await resp.json()

    async def download_recording_by_resume_id(
        self, resume_id: int, x_telegram_user: str
    ) -> Tuple[bytes, str, str]:
        """
        Скачивает финальную запись встречи по ID резюме.
        Возвращает (данные, content-type, content-disposition).
        """
        headers = {"X-Telegram-User": x_telegram_user}
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(
                f"{self.base}/resumes/{resume_id}/recording"
            ) as resp:
                # resp.raise_for_status() вызовет исключение для статусов 4xx и 5xx
                # которое мы сможем обработать в handlers
                resp.raise_for_status()  # <-- Убедимся, что ошибки 4xx/5xx обрабатываются

                # --- ГЛАВНОЕ ИЗМЕНЕНИЕ ---
                # Мы должны прочитать тело ответа, чтобы получить байты файла.
                data = await resp.read()
                content_type = resp.headers.get(
                    "Content-Type", "application/octet-stream"
                )
                content_disposition = resp.headers.get("Content-Disposition", "")
                return data, content_type, content_disposition
