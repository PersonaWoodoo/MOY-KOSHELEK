from aiogram.fsm.state import State, StatesGroup


class CheckStates(StatesGroup):
    asset = State()
    amount = State()
    description = State()
    target = State()


class DepositStates(StatesGroup):
    asset = State()
    amount = State()


class WithdrawStates(StatesGroup):
    asset = State()
    amount = State()
    address = State()
