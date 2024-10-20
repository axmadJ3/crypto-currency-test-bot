from aiogram.fsm.state import State, StatesGroup

class CryptoForm(StatesGroup):
    crypto_symbol = State()
    action = State()
    trading = State()
    