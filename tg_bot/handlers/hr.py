# tg_bot/handlers/hr.py
import tempfile

import aiohttp
from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import FSInputFile

from tg_bot.backend_client import BackendClient
from tg_bot.config import BACKEND_URL

router = Router()
bc = BackendClient(BACKEND_URL)


class GetApplicants(StatesGroup):
    waiting_vacancy_id = State()


class ArrangeMeeting(StatesGroup):
    waiting_resume_id = State()


class GetRecording(StatesGroup):
    waiting_resume_id = State()


@router.message(Command("get_applicants"))
async def cmd_get_applicants_start(message, state: FSMContext):
    await message.answer("Укажите ID вакансии:")
    await state.set_state(GetApplicants.waiting_vacancy_id)


@router.message(GetApplicants.waiting_vacancy_id, F.text)
async def process_vacancy_id(message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("ID должно быть числом.")
        return

    vacancy_id = int(message.text.strip())
    await state.clear()

    try:
        vacancy = await bc.get_vacancy(vacancy_id)
    except Exception as e:
        await message.answer(f"Ошибка при получении вакансии: {e}")
        return
    await message.answer(
        f"Вакансия: {vacancy.get('title')}\n" f"ID: {vacancy.get('id')}"
    )

    username = message.from_user.username or f"id{message.from_user.id}"
    try:
        resumes = await bc.get_resumes_for_vacancy(vacancy_id, x_telegram_user=username)
        if not resumes:
            await message.answer("Откликов нет.")
            return

        for r in resumes:
            rid = r["id"]
            candidate = r.get("telegram_username")
            try:
                sim = await bc.get_similarity(rid, x_telegram_user=username)
                sim_text = (
                    f"Результат: {sim.get('score')}\n{sim.get('result_text', '')}"
                )
            except Exception:
                sim_text = "Результат ещё не готов."
            await message.answer(
                f"ID резюме: {rid}\n"
                f"Кандидат: @{candidate}\n"
                f"{candidate}\n{sim_text}"
            )

            try:
                data, ctype, cd = await bc.download_resume_bytes(
                    rid, x_telegram_user=username
                )
                filename = r.get("original_filename") or f"resume_{rid}"
                with tempfile.NamedTemporaryFile(delete=False, suffix="") as tmp:
                    tmp.write(data)
                    tmp_path = tmp.name
                await message.answer_document(FSInputFile(tmp_path, filename=filename))
            except Exception as e:
                await message.answer(f"Не удалось скачать резюме {rid}: {e}")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")


@router.message(Command("arrange_meeting"))
async def cmd_arrange_meeting_start(message, state: FSMContext):
    await message.answer("Укажите ID резюме, для которого назначаете встречу:")
    await state.set_state(ArrangeMeeting.waiting_resume_id)


@router.message(ArrangeMeeting.waiting_resume_id, F.text)
async def arrange_scheduled(message, state: FSMContext):
    txt = message.text.strip()
    if not txt.isdigit():
        await message.answer("ID должен быть числом.")
        return
    resume_id = int(txt)
    username = message.from_user.username or f"id{message.from_user.id}"

    try:
        rinfo = await bc.get_resume(resume_id, x_telegram_user=username)
    except Exception as e:
        await message.answer(f"Ошибка при получении информации резюме: {e}")
        return

    try:
        vac = await bc.get_vacancy(rinfo.get("vacancy_id"))
    except Exception as e:
        await message.answer(f"Ошибка при получении вакансии резюме: {e}")
        return

    await message.answer(
        f"Вакансия: {vac.get('title')}\n"
        f"ID вакансии: {vac.get('id')}\n"
        f"Автор резюме: @{rinfo.get('telegram_username')}\n"
        f"ID резюме: {resume_id}\n"
    )
    try:
        meeting = await bc.arrange_meeting(resume_id, organizer_username=username)
        base = BACKEND_URL.rstrip("/")
        link = f"{base}/static/meeting.html?token={meeting['token']}"
        await message.answer(
            f"Встреча создана.\n" f"<code>{link}</code>\n", parse_mode="HTML"
        )
        rinfo = await bc.get_resume(resume_id, x_telegram_user=username)
        candidate_username = rinfo.get("telegram_username")
        candidate_user_id = rinfo.get("telegram_user_id")
        sent = False

        if candidate_user_id:
            try:
                target = int(candidate_user_id)
                await message.bot.send_message(
                    target,
                    f"Вам назначили интервью:\n"
                    f"<code>{link}</code>\n"
                    f"Вакансия: {vac.get('title')} (ID: {vac.get('id')})",
                    parse_mode="HTML",
                )
                sent = True
            except Exception as e:
                await message.answer(
                    f"Не удалось отправить сообщение по ID кандидата: {e}"
                )
        if not sent and candidate_username:
            try:
                target = f"@{candidate_username}"
                await message.bot.send_message(
                    target,
                    f"Вам назначили интервью:"
                    f"<code>{link}</code>\n"
                    f"Вакансия: {vac.get('title')} (ID: {vac.get('id')})",
                    parse_mode="HTML",
                )
                sent = True
            except Exception as e:
                await message.answer(
                    f"Не удалось отправить сообщение по юзернейму кандидата: {e}"
                )
        if not sent:
            await message.answer(
                "Не удалось отправить сообщение кандидату: нет его телеграм-юзернейма или ID."
            )
    except Exception as e:
        await message.answer(f"Ошибка при создании встречи: {e}")
    await state.clear()


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
