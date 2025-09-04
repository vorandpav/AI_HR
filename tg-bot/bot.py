# bot.py
import logging
import os
import aiohttp
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import FSInputFile
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("TELEGRAM_TOKEN")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

if not API_TOKEN:
    raise RuntimeError("Set TELEGRAM_TOKEN in .env")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=None))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# --- States ---
class PostVacancy(StatesGroup):
    waiting_title = State()
    waiting_description = State()


class ApplyResume(StatesGroup):
    waiting_vacancy = State()
    waiting_file = State()


class GetApplicants(StatesGroup):
    waiting_vacancy_id = State()


class GetStatus(StatesGroup):
    waiting_resume_id = State()


# --- Commands ---
@dp.message(Command('start'))
async def cmd_start(message: types.Message):
    text = ("Привет! Я AI-HR бот.\n\n"
            "Если вы HR (размещаете вакансии): /post_vacancy\n"
            "Если вы кандидат (отправляете резюме): /apply\n"
            "HR: получить отклики по вакансии: /get_applicants\n"
            "Кандидат: получить статус по отклику: /get_status")
    await message.answer(text)


# --- HR: публикуем вакансию ---
@dp.message(Command('post_vacancy'))
async def cmd_post_vacancy(message: types.Message, state: FSMContext):
    await message.answer("Введите заголовок вакансии:")
    await state.set_state(PostVacancy.waiting_title)


@dp.message(PostVacancy.waiting_title, F.text)
async def vacancy_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await message.answer("Теперь отправьте описание вакансии (текстом) или отправьте файл (PDF/DOCX):")
    await state.set_state(PostVacancy.waiting_description)


# 1) если HR отправил описание текстом
@dp.message(PostVacancy.waiting_description, F.text)
async def vacancy_description_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    title = data.get("title")
    description = message.text.strip()
    username = message.from_user.username or f"id{message.from_user.id}"

    form = aiohttp.FormData()
    form.add_field("title", title)
    form.add_field("description", description)
    form.add_field("telegram_username", username)

    headers = {"X-Telegram-User": message.from_user.username or f"id{message.from_user.id}"}
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.post(f"{BACKEND_URL}/vacancies/", data=form,
                                    timeout=aiohttp.ClientTimeout(total=15)) as resp:
                resp.raise_for_status()
                vacancy = await resp.json()
        except Exception as e:
            await message.answer(f"Ошибка при отправке вакансии на backend: {e}")
            await state.clear()
            return

    await message.answer(f"Вакансия сохранена. ID: {vacancy['id']}")
    await state.clear()


# 2) если HR отправил описание файлом
@dp.message(PostVacancy.waiting_description, F.document)
async def vacancy_description_file(message: types.Message, state: FSMContext):
    data = await state.get_data()
    title = data.get("title")
    doc = message.document
    username = message.from_user.username or f"id{message.from_user.id}"

    # Получаем ссылку на файл в Telegram и качаем через aiohttp
    file_info = await bot.get_file(doc.file_id)
    file_url = f"https://api.telegram.org/file/bot{API_TOKEN}/{file_info.file_path}"

    headers = {"X-Telegram-User": message.from_user.username or f"id{message.from_user.id}"}
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(file_url) as fresp:
                fresp.raise_for_status()
                file_bytes = await fresp.read()

            form = aiohttp.FormData()
            form.add_field("title", title)
            form.add_field("description", f"Описание в файле: {doc.file_name}")
            form.add_field("file", file_bytes, filename=doc.file_name,
                           content_type=doc.mime_type or "application/octet-stream")
            form.add_field("telegram_username", username)

            async with session.post(f"{BACKEND_URL}/vacancies/", data=form,
                                    timeout=aiohttp.ClientTimeout(total=30)) as resp:
                resp.raise_for_status()
                vacancy = await resp.json()
        except Exception as e:
            await message.answer(f"Ошибка при отправке файла в backend: {e}")
            await state.clear()
            return

    await message.answer(f"Вакансия с файлом сохранена. ID: {vacancy['id']}")
    await state.clear()


# --- Кандидат: отправляет резюме ---
@dp.message(Command('apply'))
async def cmd_apply(message: types.Message, state: FSMContext):
    await message.answer("Пожалуйста, укажите ID вакансии, на которую вы откликаетесь:")
    await state.set_state(ApplyResume.waiting_vacancy)


@dp.message(ApplyResume.waiting_vacancy, F.text)
async def apply_vacancy_id(message: types.Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("ID должен быть числом. Попробуйте ещё раз.")
        return

    await state.update_data(vacancy_id=int(text))
    await message.answer("Теперь отправьте ваше резюме в виде файла (PDF или DOCX). ")
    await state.set_state(ApplyResume.waiting_file)


@dp.message(ApplyResume.waiting_file, F.document)
async def apply_file_doc(message: types.Message, state: FSMContext):
    data = await state.get_data()
    vacancy_id = data.get('vacancy_id')
    doc = message.document
    username = message.from_user.username or f"id{message.from_user.id}"

    file_info = await bot.get_file(doc.file_id)
    file_url = f"https://api.telegram.org/file/bot{API_TOKEN}/{file_info.file_path}"

    headers = {"X-Telegram-User": message.from_user.username or f"id{message.from_user.id}"}
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(file_url) as fresp:
                fresp.raise_for_status()
                file_bytes = await fresp.read()

            form_data = aiohttp.FormData()
            form_data.add_field('vacancy_id', str(vacancy_id))
            form_data.add_field('file', file_bytes, filename=doc.file_name,
                                content_type=doc.mime_type or 'application/octet-stream')
            form_data.add_field('telegram_username', username)

            async with session.post(f"{BACKEND_URL}/resumes/", data=form_data,
                                    timeout=aiohttp.ClientTimeout(total=30)) as resp:
                resp.raise_for_status()
                resume = await resp.json()

        except Exception as e:
            await message.answer(f"Ошибка при отправке резюме: {e}")
            await state.clear()
            return

    await message.answer(f"Резюме отправлено! ID отклика: {resume['id']}\n"
                         f"Узнать статус: /get_status {resume['id']}")
    await state.clear()


# --- HR: получить резюме и результаты для вакансии ---
@dp.message(Command("get_applicants"))
async def cmd_get_applicants_start(message: types.Message, state: FSMContext):
    await message.answer("Укажи ID вакансии:")
    await state.set_state(GetApplicants.waiting_vacancy_id)


@dp.message(GetApplicants.waiting_vacancy_id, F.text)
async def process_vacancy_id(message: types.Message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("ID должно быть числом. Попробуй ещё раз.")
        return
    vacancy_id = int(message.text.strip())
    await state.clear()

    headers = {"X-Telegram-User": message.from_user.username or f"id{message.from_user.id}"}
    async with aiohttp.ClientSession(headers=headers) as session:
        # 1) тянем список резюме
        try:
            async with session.get(f"{BACKEND_URL}/resumes/vacancy/{vacancy_id}",
                                   timeout=aiohttp.ClientTimeout(total=10)) as resp:
                resp.raise_for_status()
                resumes = await resp.json()
        except Exception as e:
            await message.answer(f"Ошибка запроса к backend: {e}")
            return

        if not resumes:
            await message.answer("Откликов по этой вакансии нет.")
            return

        # 2) по каждому резюме — тянем similarity + файл
        for r in resumes:
            rid = r['id']
            username = r.get('telegram_username') or f"id{r.get('telegram_user_id')}"
            try:
                async with session.get(f"{BACKEND_URL}/similarity/resume/{rid}",
                                       timeout=aiohttp.ClientTimeout(total=5)) as sresp:
                    if sresp.status == 200:
                        sim = await sresp.json()
                        score = sim.get('score')
                        result_text = sim.get('result_text') or ""
                        sim_text = f"Score: {score}\nResult: {result_text}"
                    else:
                        sim_text = "Результат ещё не готов."
            except Exception:
                sim_text = "Ошибка при запросе результата."

            await message.answer(f"Отклик ID: {rid}\nКандидат: {username}\n{sim_text}")

            # файл резюме
            try:
                async with session.get(f"{BACKEND_URL}/resumes/{rid}/download",
                                       timeout=aiohttp.ClientTimeout(total=10)) as dl:
                    if dl.status == 200:
                        content = await dl.read()
                        filename = r.get('original_filename') or f"resume_{rid}.pdf"
                        tmp_path = f"{rid}_{username}_{filename}"
                        with open(tmp_path, "wb") as f:
                            f.write(content)
                        await message.answer_document(FSInputFile(tmp_path))
                    else:
                        await message.answer("Не удалось скачать файл резюме.")
            except Exception as e:
                await message.answer(f"Ошибка при скачивании резюме: {e}")


# --- Соискатель/HR: статус отклика ---
@dp.message(Command("get_status"))
async def cmd_get_status_start(message: types.Message, state: FSMContext):
    await message.answer("Укажи ID резюме:")
    await state.set_state(GetStatus.waiting_resume_id)


@dp.message(GetStatus.waiting_resume_id, F.text)
async def process_resume_id(message: types.Message, state: FSMContext):
    if not message.text.strip().isdigit():
        await message.answer("ID должно быть числом. Попробуй ещё раз.")
        return
    resume_id = int(message.text.strip())
    await state.clear()

    headers = {"X-Telegram-User": message.from_user.username or f"id{message.from_user.id}"}
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(f"{BACKEND_URL}/similarity/resume/{resume_id}", timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # проверяем, что нужные ключи есть
                    resume_id = data.get("resume_id")
                    vacancy_id = data.get("vacancy_id")
                    score = data.get("score")

                    await message.answer(
                        f"📊 Результат сравнения:\n"
                        f"Резюме ID: {resume_id}\n"
                        f"Вакансия ID: {vacancy_id}\n"
                        f"Соответствие: {score}%"
                    )
                elif resp.status == 404:
                    await message.answer("Для этого резюме результат ещё не готов.")
                else:
                    text = await resp.text()
                    await message.answer(f"Ошибка backend ({resp.status}): {text}")
        except Exception as e:
            await message.answer(f"Ошибка при запросе: {e}")


# --- Fallback handlers / unknown commands ---
@dp.message()
async def fallback(message: types.Message):
    await message.answer("Неизвестная команда. Напиши /start для инструкций.")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
