# tg_bot/handlers/problems.py
from aiogram import Router, types

router = Router()


@router.message()
async def fallback(message: types.Message):
    await message.answer("Неизвестная команда. Напиши /start для инструкций.")
