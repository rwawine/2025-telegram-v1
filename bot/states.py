"""Finite-state machine definitions for user registration flow."""

from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    accept_agreement = State()
    declined_agreement = State()
    enter_name = State()
    enter_phone = State()
    enter_loyalty_card = State()
    upload_photo = State()


class SupportStates(StatesGroup):
    entering_message = State()
    adding_to_ticket = State()

