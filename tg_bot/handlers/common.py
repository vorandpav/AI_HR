# tg_bot/handlers/common.py
from aiogram import Router, types
from aiogram.filters import Command

router = Router()


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    text = (
        "Привет! Я AI-HR бот.\n\n"
        "HR:\n"
        "/post_vacancy - создать вакансию\n"
        "/get_applicants - посмотреть отклики\n"
        "/arrange_meeting - назначить собеседование\n"
        "/get_recording - скачать запись встречи\n\n"  # Добавляем новую команду
        "Кандидат:\n"
        "/apply - откликнуться на вакансию\n"
        "/get_status - узнать статус отклика\n"
    )
    await message.answer(text)


@router.message()
async def fallback(message: types.Message):
    await message.answer("Неизвестная команда. Напиши /start для инструкций.")
