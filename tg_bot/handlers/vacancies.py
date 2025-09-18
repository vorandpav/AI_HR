# tg_bot/handlers/vacancies.py
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from tg_bot.backend_client import BackendClient

router = Router()


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
    await message.answer("Теперь отправьте файл описания (PDF/DOCX).")
    await state.set_state(PostVacancy.waiting_description)


@router.message(PostVacancy.waiting_description, F.document)
async def vacancy_description_file(
        message: types.Message,
        state: FSMContext,
        backend_client: BackendClient
):
    data = await state.get_data()
    title = data.get("title")
    doc = message.document
    username = message.from_user.username
    user_id = str(message.from_user.id)

    file_obj = await message.bot.get_file(doc.file_id)
    file_bytes = await message.bot.download_file(file_obj.file_path)

    try:
        res = await backend_client.post_vacancy(
            title=title,
            username=username,
            user_id=user_id,
            file_bytes=file_bytes.read(),
            filename=doc.file_name,
        )
        await message.answer(
            f"Вакансия сохранена!\n"
            f"<b>{res['title']}</b>\n"
            f"ID вакансии: <code>{res['id']}</code>",
            parse_mode="HTML",
        )
    except Exception as e:
        await message.answer(f"Ошибка при отправке вакансии: {e}")

    await state.clear()
