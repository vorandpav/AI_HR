# tg_bot/handlers/resumes.py
from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from tg_bot.backend_client import BackendClient

router = Router()


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
async def apply_file_doc(
        message: types.Message,
        state: FSMContext,
        backend_client: BackendClient
):
    data = await state.get_data()
    vacancy_id = data.get("vacancy_id")
    doc = message.document
    username = message.from_user.username
    user_id = str(message.from_user.id)

    file_obj = await message.bot.get_file(doc.file_id)
    file_bytes = await message.bot.download_file(file_obj.file_path)

    try:
        res = await backend_client.post_resume(
            vacancy_id=vacancy_id,
            username=username,
            user_id=user_id,
            file_bytes=file_bytes.read(),
            filename=doc.file_name,
        )
        await message.answer(
            f"Резюме отправлено!\nID резюме: <code>{res['id']}</code>",
            parse_mode="HTML",
        )
    except Exception as e:
        await message.answer(f"Ошибка при отправке резюме: {e}")
    finally:
        await state.clear()


@router.message(Command("get_status"))
async def cmd_get_status_start(message, state: FSMContext):
    await message.answer("Укажите ID резюме:")
    await state.set_state(GetStatus.waiting_resume_id)


@router.message(GetStatus.waiting_resume_id, F.text)
async def process_resume_id(
        message: types.Message,
        state: FSMContext,
        backend_client: BackendClient  # <-- Получаем клиент
):
    if not message.text.strip().isdigit():
        await message.answer("ID должно быть числом.")
        return

    resume_id = int(message.text.strip())
    username = message.from_user.username or f"id{message.from_user.id}"

    try:
        resume_data = await backend_client.get_resume(resume_id, username)
        if not resume_data:
            await message.answer("Резюме не найдено или у вас нет доступа.")
            return

        similarity = resume_data.get("similarity")
        if similarity:
            sim_text = f"Соответствие: {similarity['score']:.1%}\nКомментарий: {similarity['comment']}"
        else:
            sim_text = "Статус: Анализ еще не завершен. Попробуйте позже."

        await message.answer(
            f"<b>Статус по резюме ID: {resume_data['id']}</b>\n\n"
            f"Вакансия ID: {resume_data['vacancy_id']}\n"
            f"{sim_text}",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(f"Ошибка при запросе статуса: {e}")
    finally:
        await state.clear()
