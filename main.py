import asyncio
import subprocess
import logging
import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command
from collections import deque

API_TOKEN = os.getenv("TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID", 0))

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

alert_cooldown = False

cpu_history = {
    "python3": deque(maxlen=10),
    "watchman-task": deque(maxlen=10),
    "redis-server": deque(maxlen=10),
}


async def run_pidstat():
    global alert_cooldown

    while True:
        try:
            result = subprocess.run(["pidstat", "-u", "-p", "ALL", "1", "1"],
                                    capture_output=True, text=True)
            output = result.stdout.strip()

            max_cpu = 0.0
            for line in output.splitlines():
                parts = line.split()
                if len(parts) < 8:
                    continue
                cmd = parts[-1]
                if cmd != "python3":
                    continue
                try:
                    cpu = float(parts[7].replace(",", "."))
                except ValueError:
                    continue
                if cpu > max_cpu:
                    max_cpu = cpu

            cpu_history["python3"].append(max_cpu)

            logging.info(f"Максимальный python3 CPU: {max_cpu}%")

            if max_cpu >= 99 and not alert_cooldown:
                msg = f"⚠️ ВНИМАНИЕ! Процесс python3 использует {max_cpu}% CPU. Возможен зависший процесс!"
                await bot.send_message(CHAT_ID, msg)
                alert_cooldown = True
                asyncio.create_task(reset_cooldown())

        except Exception as e:
            logging.error(f"Ошибка: {e}")

        await asyncio.sleep(1)


async def reset_cooldown():
    global alert_cooldown
    await asyncio.sleep(60)
    alert_cooldown = False


def get_avg_cpu(proc_name):
    data = cpu_history.get(proc_name, [])
    if data:
        return round(sum(data) / len(data), 2)
    return None


@dp.message(Command("info"))
async def cmd_info(message: Message):
    try:
        result = subprocess.run(["pidstat", "-u", "-p", "ALL", "1", "1"],
                                capture_output=True, text=True)
        output = result.stdout.strip()
        monitored = ["watchman-task", "redis-server"]
        for proc in monitored:
            max_cpu = 0.0
            for line in output.splitlines():
                parts = line.split()
                if len(parts) < 8:
                    continue
                cmd = parts[-1]
                if cmd != proc:
                    continue
                try:
                    cpu = float(parts[7].replace(",", "."))
                except ValueError:
                    continue
                if cpu > max_cpu:
                    max_cpu = cpu
            cpu_history[proc].append(max_cpu)

        msg_lines = []
        for proc in ["python3", "watchman-task", "redis-server"]:
            avg = get_avg_cpu(proc)
            if avg is not None:
                msg_lines.append(f"{proc}: средний CPU за 10с = {avg}%")
            else:
                msg_lines.append(f"{proc}: данных нет")

        await message.answer("📊 Средняя нагрузка за последние 10 секунд:\n" + "\n".join(msg_lines))

    except Exception as e:
        await message.answer(f"Ошибка при выполнении pidstat: {e}")


@dp.message()
async def echo(message: Message):
    await message.answer("Бот работает. Мониторинг идёт в фоне.")


async def main():
    asyncio.create_task(run_pidstat())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
