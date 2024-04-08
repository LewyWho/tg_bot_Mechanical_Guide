from aiogram.dispatcher.filters.state import StatesGroup, State


class EnterRequestText(StatesGroup):
    """Состояние для ввода текста нового запроса."""
    waiting_for_request_text = State()


class AnswerRequest(StatesGroup):
    waiting_for_request_id = State()


class PaginationState(StatesGroup):
    Page = State()
    TotalPages = State()
