# tg_bot/handlers/resumes.py
import tempfile

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile

from tg_bot.backend_client import BackendClient
from tg_bot.config import API_TOKEN, BACKEND_URL

router = Router()
bc = BackendClient(BACKEND_URL)


class ApplyResume(StatesGroup):
    waiting_vacancy = State()
    waiting_file = State()


class GetStatus(StatesGroup):
    waiting_resume_id = State()


@router.message(Command("apply"))
async def cmd_apply(message, state: FSMContext):
    await message.answer("Укажите ID вакансии, на которую откликаетесь:")
    await state.set_state(ApplyResume.waiting_vacancy)


@router.message(ApplyResume.waiting_vacancy, F.text)
async def apply_vacancy_id(message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("ID должен быть числом.")
        return
    await state.update_data(vacancy_id=int(message.text.strip()))
    await message.answer("Отправьте файл резюме (PDF/DOCX):")
    await state.set_state(ApplyResume.waiting_file)


@router.message(ApplyResume.waiting_file, F.document)
async def apply_file_doc(message, state: FSMContext):
    data = await state.get_data()
    vacancy_id = data.get("vacancy_id")
    doc = message.document
    username = message.from_user.username or f"id{message.from_user.id}"
    user_id = str(message.from_user.id)

    file_obj = await message.bot.get_file(doc.file_id)
    file_bytes = await message.bot.download_file(file_obj.file_path)

    try:
        res = await bc.post_resume(
            vacancy_id=vacancy_id,
            telegram_username=username,
            telegram_user_id=user_id,
            file_bytes=file_bytes,
            filename=doc.file_name,
            mime=doc.mime_type or "application/octet-stream",
        )
        await message.answer(
            f"Резюме отправлено!\n" f"ID резюме: <code>{res['id']}</code>",
            parse_mode="HTML",
        )
    except Exception as e:
        await message.answer(f"Ошибка при отправке резюме: {e}")
    await state.clear()


@router.message(Command("get_status"))
async def cmd_get_status_start(message, state: FSMContext):
    await message.answer("Укажите ID резюме:")
    await state.set_state(GetStatus.waiting_resume_id)


@router.message(GetStatus.waiting_resume_id, F.text)
async def process_resume_id(message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("ID должно быть числом.")
        return
    resume_id = int(message.text.strip())
    try:
        sim = await bc.get_similarity(
            resume_id,
            x_telegram_user=message.from_user.username or f"id{message.from_user.id}",
        )
        vac = await bc.get_vacancy(sim["vacancy_id"])
        await message.answer(
            f"Резюме ID: {sim['resume_id']}\n"
            f"Вакансия ID: {sim['vacancy_id']}\n"
            f"Вакансия: {vac['title']}\n"
            f"Соответствие: {sim['score']}%"
        )
    except Exception as e:
        await message.answer(f"Ошибка при запросе: {e}")
    await state.clear()
