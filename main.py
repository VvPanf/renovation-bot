import os
import asyncio
from aiogram import Bot, Dispatcher, executor, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
import xlrd
from aiogram.types import BotCommand

API_TOKEN = os.environ.get("BOT_TOKEN")

# Настройки бота
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

# Коллекции рассчётных значений из файла
calc_params = []

# Допустимые пункты меню
rooms = ["Комната", "Квартира", "Новострой"]
room_types = ["Жилая комната", "Кухня", "Ванная комната", "Туалет", "Совмещенный санузел"]
room_count = ["Студия", "1", "2", "3", "4", "5"]
renovation_types = ["Косметический ремонт", "Капитальный ремонт", "Евроремонт"]
new_renovation_types = ["С полной отделкой от застройщика",
                        "С черновой отделкой от застройщика",
                        "Без отделки от застройщика",
                        "Новостройка свободной планировки"]

# Сообщения с пояснениями по типам ремонта
hello_message = """
Добро пожаловать! 
Наш телеграмм-бот поможет вам рассчитать стоимость ремонта и материалов.
Выберите, где вы собираетесь проводить ремонт.
"""
renovation_message = """
<u>Косметический ремонт</u> - это отделка, предполагающая выполнение демонтажных и чистовых работ помещения (без выравнивания стен).
<u>Капитальный ремонт</u> - подразумевает выполнение базовой черновой отделки (визуальное выравнивание стен) и косметического ремонта.
<u>Евроремонт</u> - комплексная отделка (демонтажные работы проводятся до основания, выравнивание стен под 90°, полная замена электрики, разводка коммуникаций и т.д.)
"""
new_renovation_message = """
<u>Ремонт с полной отделкой от застройщика</u> - демонтаж чистовой отделки от застройщика, исправление дефектов, выполнение новой отделки согласно пожеланиям клиента.
<u>Ремонт с черновой отделкой от застройщика</u> - выявление и исправление дефектов черновой отделки от застройщика, выполнение чистовых работ помещения.
<u>Ремонт без отделки от застройщика</u> - комплексный ремонт подразумевает выполнение полного чернового ремонта с выравниванием стен и пола, разводкой коммуникаций, и выполнение чистовых работ в помещении.
<u>Ремонт новостройки свободной планировки</u> - подразумевает комплексный ремонт от черновой до чистовой отделки с возведением стен.
"""
final_menu = ["Оставить заявку", "Получить консультацию", "Подписаться на наш канал"]

# Состояния конечного автомата
class RenovationState(StatesGroup):
    waiting_room = State()
    waiting_type = State()
    waiting_meterage = State()
    waiting_renovation = State()


async def main():
    await bot.set_my_commands([BotCommand(command="/start", description="Создать новый расчёт")])
    await dp.skip_updates()
    await dp.start_polling()

# Приветственное сообщение
@dp.message_handler(commands=["start"], state="*")
@dp.message_handler(Text(equals="Создать новый расчёт"), state="*")
async def start(message: types.Message, state: FSMContext):
    await message.answer(hello_message, reply_markup=make_keyboard(rooms))
    await state.set_state(RenovationState.waiting_room.state)

# Ввод типа помещения
@dp.message_handler(lambda message: message.text in rooms, state=RenovationState.waiting_room.state)
async def room(message: types.Message, state: FSMContext):
    await state.update_data(chosen_room=message.text)
    user_data = await state.get_data()
    if user_data.get("chosen_room") == "Комната":
        await message.answer("Ремонт какой комнаты вас интересует?", reply_markup=make_keyboard(room_types))
        await state.set_state(RenovationState.waiting_type.state)
        return
    if user_data.get("chosen_room") == "Квартира" or user_data.get("chosen_room") == "Новострой":
        await message.answer("Сколько комнат в квартире?", reply_markup=make_keyboard(room_count))
        await state.set_state(RenovationState.waiting_type.state)

# Выбор типа комнаты или количества комнат в квартире
@dp.message_handler(lambda message: message.text in room_types or message.text in room_count, state=RenovationState.waiting_type.state)
async def type(message: types.Message, state: FSMContext):
    await state.update_data(chosen_type=message.text)
    user_data = await state.get_data()
    msg = "Укажите метраж вашей "
    if user_data.get("chosen_room") == "Комната":
        msg += "комнаты"
    else:
        msg += "квартиры"
    await message.answer(msg, reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(RenovationState.waiting_meterage.state)

# Ввод метража квартиры или комнаты
@dp.message_handler(state=RenovationState.waiting_meterage.state)
async def meterage(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Введено неверное значение метража квартиры")
        return
    await state.update_data(chosen_meterage=int(message.text))
    user_data = await state.get_data()
    if user_data.get("chosen_room") == "Комната" or user_data.get("chosen_room") == "Квартира":
        await message.answer(renovation_message, parse_mode=types.ParseMode.HTML)
        await message.answer("Какой тип ремонта вас интересует?", reply_markup=make_keyboard(renovation_types))
        await state.set_state(RenovationState.waiting_renovation.state)
        return
    if user_data.get("chosen_room") == "Новострой":
        await message.answer(new_renovation_message, parse_mode=types.ParseMode.HTML)
        await message.answer("Какой из ремонтов у вас произведен?", reply_markup=make_keyboard(new_renovation_types))
        await state.set_state(RenovationState.waiting_renovation.state)

# Выбор типа ремонта и показ результата
@dp.message_handler(lambda message: message.text in renovation_types or message.text in new_renovation_types, state=RenovationState.waiting_renovation.state)
async def renovation(message: types.Message, state: FSMContext):
    await state.update_data(chosen_renovation=message.text)
    user_data = await state.get_data()
    ren, mat = make_calculations(user_data)
    await message.answer("""
Стоимость ремонта: <b>{0}</b> рублей
Стоимость черновых материалов: <b>{1}</b> рублей
    """.format(ren, mat), parse_mode=types.ParseMode.HTML, reply_markup=types.ReplyKeyboardRemove())
    buttons = [
        types.InlineKeyboardButton(text="Получить консультацию", callback_data="consult"),
        types.InlineKeyboardButton(text="Посетить канал", url="https://github.com/VvPanf"),
    ]
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(*buttons)
    await message.answer("Свяжитесь с нами для уточнения информации по ремонту", reply_markup=keyboard)


@dp.callback_query_handler(Text(equals="consult"), state="*")
async def consult(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("Чтобы получить консультацию, вы можете позвонить по телефону:")
    await bot.send_contact(chat_id=call.message.chat.id, phone_number="+7(123)456-78-910", first_name="Организация")
    await call.answer()


def make_keyboard(items: list):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for item in items:
        keyboard.add(item)
    return keyboard


def make_calculations(user_data: dict):
    ren = 0
    mat = 0
    meterage = user_data["chosen_meterage"]
    for item in calc_params:
        if item["room"] == user_data["chosen_room"] and item["type"] == user_data["chosen_type"] and item["renovation"] == user_data["chosen_renovation"]:
            if item["calc"] == "Ремонт":
                ren = item["value"] * meterage
            if item["calc"] == "Материалы":
                mat = item["value"] * meterage
    return ren, mat

def read_xlsx(filename: str):
    book = xlrd.open_workbook(filename)
    for s in range(book.nsheets):
        sheet = book.sheet_by_index(s)
        for i in range(2, sheet.ncols):
            for j in range(1, sheet.nrows, 2):
                calc_params.append({
                    "room": sheet.name,
                    "type": str(sheet.cell(0, i).value).replace(".0", ""),
                    "renovation": str(sheet.cell(j, 0).value).replace(".0", ""),
                    "calc": "Ремонт",
                    "value": sheet.cell(j, i).value
                })
        for i in range(2, sheet.ncols):
            for j in range(2, sheet.nrows, 2):
                calc_params.append({
                    "room": sheet.name,
                    "type": str(sheet.cell(0, i).value).replace(".0", ""),
                    "renovation": str(sheet.cell(j, 0).value).replace(".0", ""),
                    "calc": "Материалы",
                    "value": sheet.cell(j, i).value
                })


if __name__ == '__main__':
    read_xlsx("calculations.xls")
    asyncio.run(main())