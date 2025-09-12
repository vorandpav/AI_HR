# tg_bot/handlers/hr.py
from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from tg_bot.backend_client import BackendClient
from tg_bot.config import BACKEND_URL

router = Router()


class GetApplicants(StatesGroup):
    waiting_vacancy_id = State()


class ArrangeMeeting(StatesGroup):
    waiting_resume_id = State()


@router.message(Command("get_applicants"))
async def cmd_get_applicants_start(message, state: FSMContext):
    await message.answer("Укажите ID вакансии:")
    await state.set_state(GetApplicants.waiting_vacancy_id)


@router.message(GetApplicants.waiting_vacancy_id, F.text)
async def process_vacancy_id(
        message: types.Message,
        state: FSMContext,
        backend_client: BackendClient  # <-- Получаем клиент
):
    if not message.text.strip().isdigit():
        await message.answer("ID должно быть числом.")
        return

    vacancy_id = int(message.text.strip())
    username = message.from_user.username or f"id{message.from_user.id}"
    await state.clear()

    try:
        resumes = await backend_client.get_resumes_for_vacancy(vacancy_id, username)
        if not resumes:
            await message.answer("Откликов на эту вакансию пока нет.")
            return

        await message.answer(f"Найдено откликов: {len(resumes)}")

        for r in resumes:
            resume_full = await backend_client.get_resume(r['id'], username)

            sim_text = "Анализ еще не завершен."
            if resume_full and resume_full.get("similarity"):
                sim = resume_full["similarity"]
                sim_text = f"<b>Соответствие: {sim['score']:.1%}</b>\n<i>{sim['comment']}</i>"

            await message.answer(
                f"<b>Кандидат: @{r['telegram_username']}</b> (Резюме ID: {r['id']})\n\n{sim_text}",
                parse_mode="HTML"
            )

    except Exception as e:
        await message.answer(f"Произошла ошибка: {e}")


@router.message(Command("arrange_meeting"))
async def cmd_arrange_meeting_start(message, state: FSMContext):
    await message.answer("Укажите ID резюме, для которого назначаете встречу:")
    await state.set_state(ArrangeMeeting.waiting_resume_id)


@router.message(ArrangeMeeting.waiting_resume_id, F.text)
async def arrange_scheduled(
        message: types.Message,
        state: FSMContext,
        backend_client: BackendClient  # <-- Получаем клиент
):
    if not message.text.strip().isdigit():
        await message.answer("ID должен быть числом.")
        return

    resume_id = int(message.text.strip())
    username = message.from_user.username or f"id{message.from_user.id}"
    await state.clear()

    try:
        meeting = await backend_client.create_meeting(resume_id, username)

        resume = await backend_client.get_resume(resume_id, username)

        base = BACKEND_URL.rstrip("/")
        link = f"{base}/static/meeting.html?token={meeting['token']}"

        await message.answer(
            f"Встреча для кандидата @{resume['telegram_username']} создана.\n"
            f"Ссылка для звонка:\n<code>{link}</code>",
            parse_mode="HTML"
        )

        try:
            await message.bot.send_message(
                chat_id=resume['telegram_user_id'],
                text=(
                    f"Здравствуйте! Вам назначено собеседование по вашей кандидатуре.\n"
                    f"ID резюме: {resume_id}\n"
                    f"Пожалуйста, присоединяйтесь к встрече по ссылке:\n{link}"
                )
            )
            await message.answer(f"Кандидат @{resume['telegram_username']} уведомлен о встрече.")
        except Exception as e:
            await message.answer(f"Не удалось уведомить кандидата: {e}")



    except Exception as e:
        await message.answer(f"Ошибка при создании встречи: {e}")


@router.message(Command("get_recording"))
async def cmd_get_recording_start(message, state: FSMContext):
    """Начинает процесс запроса записи по ID резюме."""
    await message.answer("Укажите ID резюме, по которому была встреча:")
    await state.set_state(GetRecording.waiting_resume_id)


@router.message(GetRecording.waiting_resume_id, F.text)
async def process_recording_resume_id(message: types.Message, state: FSMContext):
    """Обрабатывает ID резюме и пытается скачать и отправить запись."""
    txt = message.text.strip()

    if not txt.isdigit():
        await message.answer("ID должен быть числом.")
        await state.clear()
        return

    resume_id = int(txt)
    username = message.from_user.username or f"id{message.from_user.id}"

    try:
        recording_data, content_type, content_disposition = (
            await bc.download_recording_by_resume_id(resume_id, username)
        )

        if not recording_data:
            await message.answer(
                "Ошибка: бэкенд вернул пустой файл. Запись может быть повреждена."
            )
            await state.clear()
            return

        filename = "recording.ogg"
        if content_disposition and "filename=" in content_disposition:
            try:
                filename_part = content_disposition.split("filename=")[1]
                filename = filename_part.strip("\"'")
            except (IndexError, ValueError):
                pass

        audio_file = types.BufferedInputFile(recording_data, filename=filename)

        await message.answer_document(
            audio_file, caption=f"Запись встречи по резюме ID {resume_id}"
        )
        await message.answer("Запись успешно отправлена!")

    except aiohttp.ClientResponseError as e:
        if e.status == 404:
            await message.answer("Запись для указанного резюме не найдена.")
        elif e.status == 403:
            await message.answer(
                "Ошибка доступа. У вас нет прав для скачивания этой записи."
            )
        else:
            await message.answer(
                f"Ошибка сервера при получении записи: {e.status} - {e.message}"
            )
    except Exception as e:
        await message.answer(
            f"Произошла непредвиденная ошибка при получении записи: {e}"
        )
    finally:
        await state.clear()
