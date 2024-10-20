import logging
import asyncio
from aiogram import F, Router
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove

from states import CryptoForm
from utils import get_crypto_price, create_crypto_button, cryptocurrencies, balance_info_buttons

router = Router()

initial_balance = 100  # Начальный капитал
grid_parts = 10  # На сколько частей делим капитал
balance_per_grid = initial_balance / grid_parts  # Сумма на каждую покупку
purchase_grid = {}  # Отслеживание покупок по сетке
percent = 1  # Процент для сеточной стратегии
trading_active = False


# ======================== Вспомогательные функции ============================


async def fetch_crypto_price(symbol: str, message: Message) -> float:
    """Получает текущую цену криптовалюты по символу"""
    try:
        crypto = await get_crypto_price(symbol)  
        
        # Проверяем, что ответ не None
        if crypto is None:
            logging.error(f"Получен пустой ответ для символа: {symbol}")
            await message.answer(f"Ошибка при получении цены для {symbol}.\nВведите 'Нет' что бы остановить торговлю")
            raise ValueError(f"Не удалось получить данные для криптовалюты {symbol}.")

        return crypto

    except KeyError:
        logging.error(f"Не удалось получить цену для символа: {symbol}")
        await message.answer(f"Криптовалюта {symbol} не найдена.")
        raise ValueError(f"Криптовалюта {symbol} не найдена.")

    except Exception as e:
        logging.error(f"Ошибка при получении цены для {symbol}: {str(e)}")
        await message.answer(f"Ошибка при получении цены для {symbol}.\nВведите 'Нет' что бы остановить торговлю")
        raise ValueError(f"Произошла ошибка при получении цены для {symbol}.")


async def update_grid_prices(symbol: str, message: Message):
    """Обновляет начальные цены для сеточной стратегии"""
    global purchase_grid
    current_price = await fetch_crypto_price(symbol, message)
    logging.info(f"Устанавливаем сеточные цены для {symbol}, текущая цена: {current_price} USDT")

    for i in range(grid_parts):
        purchase_grid[i] = {
            'buy_price': current_price * (1 - (percent / 100) * (i + 1)),
            'sell_price': None,
            'quantity': 0
        }


# ======================== Обработчики команд ================================


@router.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext):
    """Обработка команды /start"""
    await message.answer(
        f"Добро пожаловать в CryptoBot, {message.from_user.username}! "
        f"\nЭтот бот предназначен для отслеживания курса криптовалют! "
        f"\nВыберите криптовалюту👇", 
        reply_markup=create_crypto_button()
    )
    
    await state.set_state(CryptoForm.crypto_symbol)


@router.message(F.text.in_(cryptocurrencies), StateFilter(CryptoForm.crypto_symbol))
async def crypto_price_info(message: Message, state: FSMContext):
    symbol = message.text
    try:
        await state.update_data(symbol=symbol)

        price = await fetch_crypto_price(symbol, message)  # Обязательно используем await
        await message.answer(f"Текущая цена {symbol}: {price} ($) USD. Разрешить боту торговать? (Да/Нет)", 
                             reply_markup=ReplyKeyboardRemove())
        await state.set_state(CryptoForm.action)  # Переключаемся на следующее состояние
    except Exception as e:
        await message.answer(f"Ошибка. Попробуйте снова ввести символ.")
        logging.error(f'Ошибка: {str(e)}.')


@router.message(StateFilter(CryptoForm.action))
async def process_action(message: Message, state: FSMContext):
    global trading_active
    data = await state.get_data()
    symbol = data.get('symbol')
    
    if message.text.lower() == 'да':
        # Если пользователь разрешает торговлю
        trading_active = True  # Устанавливаем флаг активной торговли
        price = await fetch_crypto_price(symbol, message)
        await message.answer(
            f"Торговля разрешена для {symbol}. Текущая цена: {price:.2f} USDT.\nВнизу вы можете видеть процесс торговли.",
            reply_markup=balance_info_buttons
        )
        await start_trading(symbol, message)
          
    elif message.text.lower() == 'нет':
        # Если пользователь отменяет торговлю
        trading_active = False  # Останавливаем торговлю
        await state.clear()
        await message.answer(
            "Торговля отменена. Выберите другую криптовалюту:",
            reply_markup=create_crypto_button()
        )
        await state.set_state(CryptoForm.crypto_symbol)
        
    else:
        await message.answer("Пожалуйста, ответьте 'Да' или 'Нет'.")
        

@router.message(F.text == "Текущий баланс", StateFilter(None))
async def show_balance(message: Message):
    """Отображение текущего баланса"""
    await message.answer(f"Текущий капитал: {initial_balance:.2f} USD")


@router.message(F.text == "Текущая цена", StateFilter(None))
async def show_price(message: Message, state: FSMContext):
    """Отображение текущей цены выбранной криптовалюты"""
    data = await state.get_data()
    symbol = data.get('symbol')
    
    if symbol:
        price = await fetch_crypto_price(symbol, message)
        await message.answer(f"Текущая цена {symbol}: {price:.2f} USD")
    else:
        await message.answer("Сначала выберите криптовалюту.")


@router.message(F.text == "Остановить торговлю", StateFilter(None))
async def stop_trading(message: Message, state: FSMContext):
    global initial_balance, purchase_grid
    initial_balance = 100  # Возвращаем начальный капитал
    purchase_grid.clear()  # Очищаем сетки покупок/продаж
    await message.answer("Торговля остановлена и капитал сброшен.", reply_markup=create_crypto_button())
    await state.set_state(CryptoForm.crypto_symbol)  # Устанавливаем состояние для выбора новой криптовалюты
    await state.clear()


# ======================== Торговая логика ================================


async def start_trading(symbol: str, message: Message):
    """Основная торговая логика по сеточной стратегии"""
    global initial_balance, trading_active

    await update_grid_prices(symbol, message)

    while initial_balance > 0 and trading_active:  # Добавляем условие для проверки флага
        try:
            current_price = await fetch_crypto_price(symbol, message)
            logging.info(f"Обновленная цена {symbol}: {current_price:.2f} USDT")
            await message.answer(f"Обновленная цена {symbol}: {current_price:.2f} USDT")

            for i in range(grid_parts):
                grid = purchase_grid[i]

                # Покупка
                if grid['quantity'] == 0 and current_price <= grid['buy_price']:
                    grid['quantity'] = balance_per_grid / current_price
                    initial_balance -= balance_per_grid
                    grid['sell_price'] = current_price * (1 + percent / 100)
                    logging.info(f"Купили {grid['quantity']:.6f} {symbol} по цене {current_price:.2f} USDT")
                    await message.answer(f"Купили {grid['quantity']:.6f} {symbol} по цене {current_price:.2f} USDT")

                # Продажа
                elif grid['quantity'] > 0 and current_price >= grid['sell_price']:
                    earnings = grid['quantity'] * current_price
                    initial_balance += earnings
                    logging.info(f"Продали {grid['quantity']:.6f} {symbol} по цене {current_price:.2f} USDT")
                    await message.answer(f"Продали {grid['quantity']:.6f} {symbol} по цене {current_price:.2f} USDT")

                    # Сбрасываем сетку после продажи
                    grid['quantity'] = 0
                    grid['buy_price'] = current_price * (1 - percent / 100)
                    grid['sell_price'] = None

            await asyncio.sleep(15)

        except Exception as e:
            logging.error(f"Ошибка в торговле: {str(e)}")
            await asyncio.sleep(15)  # Подождите немного перед следующей попыткой
