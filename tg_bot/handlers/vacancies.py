# tg_bot/handlers/vacancies.py
from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from tg_bot.backend_client import BackendClient
from tg_bot.config import BACKEND_URL

router = Router()
bc = BackendClient(BACKEND_URL)


class PostVacancy(StatesGroup):
    waiting_title = State()
    waiting_description = State()


@router.message(Command("post_vacancy"))
async def cmd_post_vacancy(message: types.Message, state: FSMContext):
    await message.answer("Введите заголовок вакансии:")
    await state.set_state(PostVacancy.waiting_title)


@router.message(PostVacancy.waiting_title, F.text)
async def vacancy_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await message.answer("Теперь отправьте файл (PDF/DOCX).")
    await state.set_state(PostVacancy.waiting_description)


@router.message(PostVacancy.waiting_description, F.document)
async def vacancy_description_file(message: types.Message, state: FSMContext):
    data = await state.get_data()
    title = data.get("title")
    doc = message.document
    username = message.from_user.username or f"id{message.from_user.id}"
    user_id = str(message.from_user.id)

    file_obj = await message.bot.get_file(doc.file_id)
    file_bytes = await message.bot.download_file(file_obj.file_path)

    try:
        res = await bc.post_vacancy(
            title=title,
            telegram_username=username,
            telegram_user_id=user_id,
            file_bytes=file_bytes,
            filename=doc.file_name,
            mime=doc.mime_type or "application/octet-stream",
        )
        await message.answer(
            f"Вакансия сохранена!\n" f"ID вакансии: <code>{res['id']}</code>",
            parse_mode="HTML",
        )
    except Exception as e:
        await message.answer(f"Ошибка при отправке вакансии: {e}")
    await state.clear()
