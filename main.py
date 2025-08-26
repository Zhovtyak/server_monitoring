import asyncio
import subprocess
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.types import Message

from aiogram.filters import Command
from aiogram import F

API_TOKEN = os.getenv('TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

alert_cooldown = False


async def run_pidstat():
    global alert_cooldown

    while True:
        try:
            result = subprocess.run(["pidstat", "-u", "-p", "ALL", "1", "1"], capture_output=True, text=True)
            output = result.stdout.strip()

            for line in output.splitlines():
                if "python3" in line:
                    parts = line.split()
                    if len(parts) >= 8:
                        cpu_usage = float(parts[7].replace(",", "."))
                        cmd = parts[-1]

                        logging.info(f"Процесс: {cmd}, CPU: {cpu_usage}%")

                        if cpu_usage >= 99 and not alert_cooldown:
                            msg = (
                                f"⚠️ ВНИМАНИЕ!\n"
                                f"Процесс: {cmd}, CPU: {cpu_usage}%\n\n"
                                f"Вероятно, сервер завис — требуется проверка!"
                            )
                            await bot.send_message(int(CHAT_ID), msg)

                            # включаем кулдаун на 60 секунд
                            alert_cooldown = True
                            asyncio.create_task(reset_cooldown())
                    break
        except Exception as e:
            logging.error(f"Ошибка: {e}")

        await asyncio.sleep(1)


async def reset_cooldown():
    """Сбрасывает кулдаун через 60 секунд"""
    global alert_cooldown
    await asyncio.sleep(60)
    alert_cooldown = False


def get_pidstat_info():
    """Возвращает CPU info по python3, watchman-task, redis-server"""
    result = subprocess.run(["pidstat", "-u", "-p", "ALL", "1", "1"], capture_output=True, text=True)
    output = result.stdout.strip()

    processes = ["python3", "watchman-task", "redis-server"]
    report = []

    for proc in processes:
        for line in output.splitlines():
            if proc in line:
                parts = line.split()
                if len(parts) >= 8:
                    cpu_usage = parts[7]
                    report.append(f"{proc}: {cpu_usage}%")
                break
        else:
            report.append(f"{proc}: не найден")

    return "\n".join(report)


@dp.message(Command("info"))
async def cmd_info(message: Message):
    info = get_pidstat_info()
    await message.answer(f"📊 Текущее состояние процессов:\n{info}")


@dp.message()
async def echo(message: Message):
    await message.answer("Бот работает. Мониторинг идёт в фоне.")


async def main():
    asyncio.create_task(run_pidstat())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
