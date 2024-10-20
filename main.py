import asyncio
import os
import logging
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from handler import router

load_dotenv()

TOKEN = os.getenv('TOKEN')
    

async def main():
    dp = Dispatcher()
    dp.include_router(router)

    bot = Bot(token=TOKEN, default=DefaultBotProperties())

    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
    