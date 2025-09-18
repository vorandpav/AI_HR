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
async def apply_vacancy_id(message: types.Message,
                           state: FSMContext,
                           backend_client: BackendClient):
    if not message.text.strip().isdigit():
        await message.answer("ID должен быть числом.")
        await state.clear()
        return

    vacancy_id = int(message.text.strip())
    username = message.from_user.username

    try:
        vacancy = await backend_client.get_vacancy(vacancy_id, username)
        if vacancy['telegram_username'] == username:
            await message.answer("Вы подаёте резюме на свою же вакансию.\n"
                                 f"Вакансия: <b>{vacancy['title']}</b>\n"
                                 f"ID вакансии: <code>{vacancy['id']}</code>\n"
                                 "Если это ошибка, введите /start\n"
                                 "Иначе отправьте резюме в формате PDF или DOCX.",
                                 parse_mode="HTML")
        else:
            await message.answer(f"Вакансия: <b>{vacancy['title']}</b>\n"
                                 f"ID вакансии: <code>{vacancy['id']}</code>\n"
                                 "Отправьте резюме в формате PDF или DOCX.",
                                 parse_mode="HTML")
    except Exception as e:
        await message.answer(f"Ошибка: Вакансия с ID {vacancy_id} не найдена или недоступна.\n{e}")
        await state.clear()
        return

    await state.update_data(vacancy_id=vacancy_id)
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
            f"Резюме отправлено!\n"
            f"Кандидат: @{res['telegram_username']}\n"
            f"ID резюме: <code>{res['id']}</code>\n"
            f"Ожидайте уведомления об анализе соответствия.",
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
async def process_resume_id(
        message: types.Message,
        state: FSMContext,
        backend_client: BackendClient
):
    if not message.text.strip().isdigit():
        await message.answer("ID должно быть числом.")
        await state.clear()
        return

    resume_id = int(message.text.strip())
    username = message.from_user.username

    try:
        resume = await backend_client.get_resume(resume_id, username)
    except Exception as e:
        await message.answer(f"Ошибка: Резюме с ID {resume_id} не найдено или недоступно.\n{e}")
        await state.clear()
        return
    print(resume)
    if resume['similarity'] is None:
        await message.answer(
            f"Резюме ID <code>{resume['id']}</code> ещё не проанализировано.\n"
            "Ожидайте уведомления, когда анализ будет завершён.",
            parse_mode="HTML"
        )
    else:
        score = resume['similarity']['score'] * 100
        comment = resume['similarity']['comment']
        await message.answer(
            f"Статус резюме ID <code>{resume['id']}</code>:\n"
            f"Кандидат: @{resume['telegram_username']}\n"
            f"Вакансия: <b>{vacancy['title']}</b>\n"
            f"ID вакансии: <code>{vacancy['id']}</code>\n"
            f"Ссылка на резюме: {resume['file_url']}\n"
            f"Оценка соответствия вакансии: {score:.2f}%\n"
            f"Комментарий: {comment}",
            parse_mode="HTML"
        )

    await state.clear()
