from aiogram.fsm.state import State, StatesGroup


class CheckStates(StatesGroup):
    asset = State()
    amount = State()
    description = State()
    max_activations = State()
    target = State()


class DepositStates(StatesGroup):
    crypto_asset = State()
    crypto_amount = State()
    rub_amount = State()
    rub_txid = State()


class WithdrawStates(StatesGroup):
    asset = State()
    amount = State()
    address = State()


class AdminStates(StatesGroup):
    give_user = State()
    give_asset = State()
    give_amount = State()
    set_balance_user = State()
    set_balance_amount = State()
    broadcast = State()
