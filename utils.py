import os
import aiohttp
import logging
import asyncio

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from dotenv import load_dotenv

load_dotenv()

# ключь от API CoinMarketCap: https://coinmarketcap.com/
API_KEY = os.getenv('SECRET_COINMARKET_KEY')

# КНОПКИ
cryptocurrencies = ["BTC", "ETH", "USDT", "BNB", "SOL", "USDC", "XRP", "DOGE", "TON", "USDT"]

# для кнопок криптовалюты
def create_crypto_button():
    keyboard_builder = ReplyKeyboardBuilder()
    
    for crypto in cryptocurrencies:
        keyboard_builder.add(KeyboardButton(text=crypto)) 
         
    keyboard_builder.adjust(2)  
    
    return keyboard_builder.as_markup(resize_keyboard=True)


balance_info_buttons = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Текущий баланс")],
            [KeyboardButton(text="Текущая цена")],
            [KeyboardButton(text="Остановить торговлю")]
        ],
        resize_keyboard=True
    )

async def get_crypto_price(symbol: str, currency: str = 'USD', retries: int = 3, delay: int = 5):
    """Получает текущую цену криптовалюты по символу с обработкой ошибок и повторными попытками."""
    url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'

    headers = {
        'X-CMC_PRO_API_KEY': API_KEY,
    }

    params = {
        'symbol': symbol,
        'convert': currency,
    }

    async with aiohttp.ClientSession() as session:
        for attempt in range(retries):
            try:
                async with session.get(url, headers=headers, params=params) as response:
                    response.raise_for_status()  # Проверка на наличие ошибок HTTP

                    data = await response.json()
                    if symbol in data['data']:
                        price = data['data'][symbol]['quote'][currency]['price']
                        logging.info(f"Текущая цена {symbol}: {price} {currency}")
                        return price
                    else:
                        logging.error(f"Криптовалюта {symbol} не найдена в ответе API.")
                        return None

            except aiohttp.ClientError as req_err:
                logging.warning(f"Ошибка запроса для {symbol}: {req_err}")
                if attempt < retries - 1:  # Если это не последняя попытка, ждем перед повторной попыткой
                    await asyncio.sleep(delay)
                else:
                    logging.error(f"Не удалось получить цену для {symbol} после {retries} попыток.")
                    return None
            except KeyError:
                logging.error(f"Криптовалюта {symbol} не найдена в ответе API.")
                return None
            except Exception as e:
                logging.error(f"Неизвестная ошибка при получении цены для {symbol}: {e}")
                return None

    return None  # Возвращаем None, если ничего не удалось
