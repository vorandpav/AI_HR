import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from tg_bot.config import API_TOKEN, BACKEND_URL
from tg_bot.handlers.common import router as common_router
from tg_bot.handlers.hr import router as hr_router
from tg_bot.handlers.resumes import router as res_router
from tg_bot.handlers.vacancies import router as vac_router
from tg_bot.handlers.problems import router as problems_router
from tg_bot.backend_client import BackendClient

logging.basicConfig(level=logging.INFO)


async def main():
    bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=None))
    storage = MemoryStorage()

    backend_client = BackendClient(base_url=BACKEND_URL)

    dp = Dispatcher(storage=storage, backend_client=backend_client)

    dp.include_router(common_router)
    dp.include_router(vac_router)
    dp.include_router(res_router)
    dp.include_router(hr_router)
    dp.include_router(problems_router)

    try:
        await dp.start_polling(bot)
    finally:
        await backend_client.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
