from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.enums import ParseMode
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command, CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import asyncio
from keep_alive import keep_alive
from enum import Enum
from aiogram.fsm.storage.memory import MemoryStorage
from datetime import datetime  # Уже может быть — ничего страшного

# Счётчик заказов на каждый день
daily_order_counter = {}

# Связь между номером заказа и user_id
order_number_to_user = {}

API_TOKEN = "7582557120:AAHsoe7RYRjCbPV9EwNh5Ak6C9HmTZGRbRs"
ADMIN_ID = 1648127193
COURIERS_CHAT_ID = -1002297990202
last_help_message_id = None  # Добавьте это в начало с другими переменными

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📂 Каталог"), KeyboardButton(text="🛍 Корзина")],
        [KeyboardButton(text="📦 Мои заказы"), KeyboardButton(text="📢 Новости")],
        [KeyboardButton(text="⭐️ Оставить отзыв"), KeyboardButton(text="❓ Помощь")]
    ],
    resize_keyboard=True
)

class OrderForm(StatesGroup):
    waiting_for_location = State()
    confirm_address = State()
    waiting_for_phone = State()

class OrderStatus(Enum):
    ACCEPTED = "Ваш заказ принят"
    PREPARING = "Ваш заказ собирается"
    ON_THE_WAY = "Ваш заказ едет к вам"
    DELIVERED = "Ваш заказ доставлен"

user_carts = {}
user_orders = {}

products = {
    "category_fruits": {"Яблоко": 3, "Банан": 4, "Апельсин": 5},
    "category_vegetables": {"Картошка": 2, "Морковь": 1, "Огурец": 3},
    "category_drinks": {"Кола": 6, "Сок": 5, "Вода": 2},
    "category_snacks": {"Чипсы": 4, "Шоколад": 5, "Орехи": 6},
    "category_milks": {"Молоко": 18, "Сметана": 14, "Кефир": 12}
}

@dp.message(CommandStart())
async def send_welcome(message: Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="Фрукты", callback_data="category_fruits")
    kb.button(text="Овощи", callback_data="category_vegetables")
    kb.button(text="Напитки", callback_data="category_drinks")
    kb.button(text="Снеки", callback_data="category_snacks")
    kb.button(text="Молочка", callback_data="category_milks")

    # Приветствие
    await message.answer("Добро пожаловать!                                                               Ждём ваших заказов 💜", reply_markup=main_menu)

    # Отправка стикера (тот, что ты прислал)
    await bot.send_sticker(message.chat.id, "CAACAgQAAxkBAAIJT2gmdq7qFlY80egtqdn3Q0QPoA5iAAISDQAC1MiAUAXbnVAhxur0NgQ")

    # Кнопки категорий
    await message.answer("Выберите категорию:", reply_markup=kb.as_markup())


@dp.message(Command("status"))
async def change_order_status(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        parts = message.text.split()
        if len(parts) != 3:
            raise ValueError("Формат команды: /status <номер_заказа> <статус>")

        _, order_number_str, status_str = parts
        order_number = int(order_number_str)
        status = OrderStatus[status_str.upper()]

        user_id = None
        order_to_update = None

        for uid, orders in user_orders.items():
            for order in orders:
                if order["order_number"] == order_number:
                    user_id = uid
                    order_to_update = order
                    break
            if user_id:
                break

        if user_id and order_to_update:
            order_to_update["status"] = status
            await bot.send_message(user_id, f"<b>{status.value}</b>")
            await message.answer(f"Статус заказа №{order_number} обновлён: {status.value}")
        else:
            await message.answer("Заказ с таким номером не найден.")

    except Exception:
        await message.answer(
            "Ошибка. Пример: /status 2 preparing\n"
            "Доступные статусы: accepted, preparing, on_the_way, delivered"
)

@dp.message(F.sticker)
async def get_sticker_id(message: Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer(f"file_id стикера:\n<code>{message.sticker.file_id}</code>")

@dp.callback_query(lambda c: c.data.startswith("category_"))
async def show_category(callback: types.CallbackQuery):
    category = callback.data
    items = products.get(category, {})
    kb = InlineKeyboardBuilder()
    for item, price in items.items():
        kb.button(text=f"{item} - {price} сом", callback_data=f"add_{item}")
    kb.button(text="Корзина", callback_data="cart")
    kb.button(text="Назад", callback_data="back")
    await callback.message.edit_text(f"<b>{category.split('_')[1].capitalize()}</b>:", reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("add_"))
async def add_to_cart(callback: types.CallbackQuery):
    item = callback.data.replace("add_", "")
    user_id = callback.from_user.id
    for category in products.values():
        if item in category:
            price = category[item]
            cart = user_carts.setdefault(user_id, {})
            if item in cart:
                cart[item]["quantity"] += 1
            else:
                cart[item] = {"price": price, "quantity": 1}
            await callback.answer(f"{item} добавлено!")
            return

@dp.callback_query(lambda c: c.data.startswith("increase_"))
async def increase_quantity(callback: types.CallbackQuery):
    item = callback.data.replace("increase_", "")
    user_id = callback.from_user.id
    cart = user_carts.get(user_id, {})
    if item in cart:
        cart[item]["quantity"] += 1
    await show_cart(callback)
    await callback.answer(f"Добавлен ещё один {item}")

@dp.callback_query(lambda c: c.data.startswith("decrease_"))
async def decrease_quantity(callback: types.CallbackQuery):
    item = callback.data.replace("decrease_", "")
    user_id = callback.from_user.id
    cart = user_carts.get(user_id, {})
    if item in cart:
        if cart[item]["quantity"] > 1:
            cart[item]["quantity"] -= 1
        else:
            del cart[item]
    await show_cart(callback)
    await callback.answer(f"{item} обновлён")

@dp.callback_query(lambda c: c.data.startswith("remove_"))
async def remove_from_cart(callback: types.CallbackQuery):
    item_to_remove = callback.data.replace("remove_", "")
    user_id = callback.from_user.id
    cart = user_carts.get(user_id, {})

    if item_to_remove in cart:
        del cart[item_to_remove]
        await show_cart(callback)
        await callback.answer(f"{item_to_remove} удалено из корзины.")

@dp.callback_query(lambda c: c.data == "cart")
async def show_cart(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    cart = user_carts.get(user_id, {})

    if not cart:
        await callback.message.edit_text("Корзина пуста.", reply_markup=main_menu)
        return

    text = "🛒 <b>Ваша корзина:</b>\n\n"
    total = 0
    kb = InlineKeyboardBuilder()

    for item, data in cart.items():
        price = data["price"]
        qty = data["quantity"]
        text += f"▪️ {item} — {qty} x {price} = {qty * price} сом\n"
        total += qty * price

        kb.row(
            types.InlineKeyboardButton(text="➖", callback_data=f"decrease_{item}"),
            types.InlineKeyboardButton(text=f"{qty}", callback_data="noop"),
            types.InlineKeyboardButton(text="➕", callback_data=f"increase_{item}"),
            types.InlineKeyboardButton(text="❌", callback_data=f"remove_{item}")
        )

    text += f"\n<b>Итого: {total} сом</b>"

    kb.row(
        types.InlineKeyboardButton(text="🔙 Назад", callback_data="back"),
        types.InlineKeyboardButton(text="✅ Оформить", callback_data="checkout")
    )

    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "checkout")
async def ask_location(callback: types.CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    kb.button(text="Отправить геолокацию", callback_data="send_location")
    kb.button(text="Ввести адрес вручную", callback_data="write_address")
    await callback.message.answer("Как вы хотите указать адрес?", reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(lambda c: c.data == "send_location")
async def ask_geo(callback: types.CallbackQuery, state: FSMContext):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Отправить геолокацию", request_location=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await callback.message.answer("Пожалуйста, отправьте вашу геолокацию:", reply_markup=kb)
    await state.set_state(OrderForm.waiting_for_location)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "write_address")
async def ask_manual_address(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Пожалуйста, введите адрес вручную (улица, дом, этаж, квартира, можно и ориентир):")
    await state.set_state(OrderForm.confirm_address)
    await callback.answer()

@router.message(OrderForm.waiting_for_location)
async def confirm_location(message: Message, state: FSMContext):
    if message.location:
        latitude = message.location.latitude
        longitude = message.location.longitude
        address = f"https://yandex.ru/maps/?ll={longitude}%2C{latitude}&z=18&l=map&pt={longitude},{latitude},pm2rdl"
        await state.update_data(address=address)
        kb = InlineKeyboardBuilder()
        kb.button(text="Да", callback_data="confirm_address_yes")
        kb.button(text="Нет", callback_data="confirm_address_no")
        await message.answer(f"Это ваш адрес?\n{address}", reply_markup=kb.as_markup())
        await state.set_state(OrderForm.confirm_address)
    else:
        await message.answer("Пожалуйста, нажмите кнопку 'Отправить геолокацию'.")

@router.message(OrderForm.confirm_address)
async def handle_address(message: Message, state: FSMContext):
    if message.location:
        latitude = message.location.latitude
        longitude = message.location.longitude
        address = f"https://yandex.ru/maps/?ll={longitude}%2C{latitude}&z=18&l=map&pt={longitude},{latitude},pm2rdl"
    else:
        address = message.text
    await state.update_data(address=address)
    kb = InlineKeyboardBuilder()
    kb.button(text="Да", callback_data="confirm_address_yes")
    kb.button(text="Нет", callback_data="confirm_address_no")
    await message.answer(f"Это ваш адрес?\n{address}", reply_markup=kb.as_markup())

@dp.callback_query(lambda c: c.data == "confirm_address_yes")
async def ask_phone(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите ваш номер телефона:")
    await state.set_state(OrderForm.waiting_for_phone)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "confirm_address_no")
async def retry_location(callback: types.CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    kb.button(text="Отправить геолокацию", callback_data="send_location")
    kb.button(text="Ввести адрес вручную", callback_data="write_address")
    await callback.message.answer("Укажите адрес ещё раз:", reply_markup=kb.as_markup())
    await callback.answer()

@router.message(OrderForm.waiting_for_phone)
async def get_phone(message: Message, state: FSMContext):
    data = await state.get_data()
    address = data["address"]
    phone = message.text
    user_id = message.from_user.id

    today = datetime.now().strftime("%Y-%m-%d")
    if today not in daily_order_counter:
        daily_order_counter[today] = 0
    daily_order_counter[today] += 1
    order_number = daily_order_counter[today]

    order_number_to_user[message.from_user.id] = order_number
    
    cart = user_carts.get(user_id, {})
    order_text = "\n".join(
        f"- {item} x {data['quantity']} = {data['price'] * data['quantity']} сом"
        for item, data in cart.items()
    )
    total = sum(data['price'] * data['quantity'] for data in cart.values()) 
    text = (
        f"<b>Номер заказа: #{order_number}</b>\n\n"
        f"{order_text}\n\n"
        f"<b>Итого: {total} сом</b>\n"
        f"<b>Адрес:</b> {address}\n"
        f"<b>Телефон:</b> {phone}\n\n"
        f"Спасибо за заказ! 💜 "
    )

    user_carts[user_id] = []
    await message.answer(text, reply_markup=main_menu)

    user_name = f"@{message.from_user.username}" if message.from_user.username else f"ID {user_id}"
    notify_text = f"Новый заказ от {user_name}:\n{text}"
    await bot.send_message(ADMIN_ID, notify_text)
    await bot.send_message(COURIERS_CHAT_ID, notify_text)

    user_orders.setdefault(user_id, []).append({
        "status": OrderStatus.ACCEPTED,
        "text": text,
        "order_number": order_number
    })

    await state.clear()

@dp.message(Command("active_orders"))
async def cmd_active_orders(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    if not user_orders:
        await message.answer("Нет активных заказов.", reply_markup=main_menu)
        return

    response = "<b>Активные заказы:</b>\n\n"
    found = False

    for user_id, orders in user_orders.items():
        for order in orders:
            if order["status"] in [OrderStatus.ACCEPTED, OrderStatus.PREPARING, OrderStatus.ON_THE_WAY]:
                found = True
                chat = await bot.get_chat(user_id)
                user_name = f"@{chat.username}" if chat.username else f"ID {user_id}"
                response += (
                    f"№{order['order_number']} — {user_name} — <b>{order['status'].value}</b>\n\n"
                    f"{order['text']}\n\n---\n\n"
    )

    await message.answer(response, reply_markup=main_menu) 

@dp.callback_query(lambda c: c.data == "back")
async def go_back(callback: types.CallbackQuery):
    kb = InlineKeyboardBuilder()
    kb.button(text="Фрукты", callback_data="category_fruits")
    kb.button(text="Овощи", callback_data="category_vegetables")
    kb.button(text="Напитки", callback_data="category_drinks")
    kb.button(text="Снеки", callback_data="category_snacks")
    kb.button(text="Молочка", callback_data="category_milks")

    await callback.message.edit_text("Выберите категорию:", reply_markup=kb.as_markup())
    await callback.answer()

@dp.message(Command("cart"))
async def cmd_cart(message: Message):
    user_id = message.from_user.id
    cart = user_carts.get(user_id, {})
    
    if not cart:
        await message.answer("🛒 Корзина пуста", reply_markup=main_menu)
        return

    text = "🛒 <b>Ваша корзина:</b>\n\n"
    total = 0
    kb = InlineKeyboardBuilder()
    
    for item, data in cart.items():
        price = data["price"]
        qty = data["quantity"]
        subtotal = price * qty
        text += f"▪️ {item} — {qty} x {price} = {subtotal} сом\n"
        total += subtotal

        kb.row(
            types.InlineKeyboardButton(text="➖", callback_data=f"decrease_{item}"),
            types.InlineKeyboardButton(text=f"{qty}", callback_data="noop"),
            types.InlineKeyboardButton(text="➕", callback_data=f"increase_{item}"),
            types.InlineKeyboardButton(text="❌", callback_data=f"remove_{item}")
        )
    
    text += f"\n<b>Итого: {total} сом</b>"
    
    kb.row(
        types.InlineKeyboardButton(text="🔙 Назад", callback_data="back"),
        types.InlineKeyboardButton(text="✅ Оформить", callback_data="checkout")
    )

    await message.answer(text, reply_markup=kb.as_markup()) 

@dp.message(Command("orders"))
async def cmd_orders(message: Message):
    user_id = message.from_user.id
    args = message.text.split()
    status_filter = args[1].lower() if len(args) > 1 else None
    if user_id in user_orders and user_orders[user_id]:
        response = "<b>Ваши заказы:</b>\n\n"
        for order in user_orders[user_id]:
            response += (
                f"📦 <b>Заказ #{order['order_number']}</b>\n"
                f"{order['text']}\n"
                f"<b>Статус:</b> {order['status'].value}\n\n"
                f"---\n\n"
    )
        await message.answer(response)
    else:
        await message.answer("У вас пока нет заказов.")
        
async def cmd_contacts(message: Message):
    await message.answer("Контакты магазина: @DilovarAhi", reply_markup=main_menu)

@dp.message(Command("help"))
async def cmd_help(message: Message):
    help_text = """
<b>Доступные команды:</b>
/start - Начать покупки
/search - Поиск товаров (например: /search яблоко)
/cart - Показать корзину
/orders - Показать мои заказы
"""
    await message.answer(help_text, reply_markup=main_menu)

@dp.message(Command("search"))
async def search_products(message: Message):
    search_query = message.text.replace("/search", "").strip().lower()
    if not search_query:
        await message.answer("Пожалуйста, укажите что вы ищете. Например: /search яблоко")
        return
        
    results = []
    for category, items in products.items():
        for item, price in items.items():
            if search_query in item.lower():
                results.append(f"▪️ {item} — {price} сом ({category.replace('category_', '').capitalize()})")
    
    if results:
        await message.answer("🔍 Результаты поиска:\n\n" + "\n".join(results))
    else:
        await message.answer("По вашему запросу ничего не найдено 😔")

@dp.message(F.text == "📂 Каталог")
async def menu_catalog(message: Message):
    await message.delete()
    kb = InlineKeyboardBuilder()
    kb.button(text="Фрукты", callback_data="category_fruits")
    kb.button(text="Овощи", callback_data="category_vegetables")
    kb.button(text="Напитки", callback_data="category_drinks")
    kb.button(text="Снеки", callback_data="category_snacks")
    kb.button(text="Молочка", callback_data="category_milks")
    await message.answer("Выберите категорию:", reply_markup=kb.as_markup())

@dp.message(F.text == "🛍 Корзина")
async def menu_cart(message: Message):
    await message.delete()
    await cmd_cart(message)

@dp.message(F.text == "📦 Мои заказы")
async def menu_orders(message: Message):
    await message.delete()
    await cmd_orders(message)

@dp.message(F.text == "📢 Новости")
async def menu_news(message: Message):
    await message.delete()
    await message.answer("Нет новостей пока.")

class ReviewState(StatesGroup):
    waiting_for_rating = State()
    waiting_for_text = State()

@dp.message(F.text == "⭐️ Оставить отзыв")
async def menu_reviews(message: Message, state: FSMContext):
    await message.delete()
    kb = InlineKeyboardBuilder()
    # Сначала 1-3 звезды
    for i in range(1, 4):
        kb.button(text="⭐" * i, callback_data=f"rate_{i}")
    # Затем 4-5 звезд
    for i in range(4, 6):
        kb.button(text="⭐" * i, callback_data=f"rate_{i}")
    kb.adjust(3, 2)
    await message.answer("Пожалуйста, оцените наш сервис:", reply_markup=kb.as_markup())
    await state.set_state(ReviewState.waiting_for_rating)

@dp.callback_query(lambda c: c.data.startswith("rate_"))
async def handle_rating(callback: types.CallbackQuery, state: FSMContext):
    rating = int(callback.data.split("_")[1])
    await state.update_data(rating=rating)
    await callback.message.edit_text(f"Спасибо за оценку! ({rating}⭐)\nТеперь напишите ваш отзыв:")
    await state.set_state(ReviewState.waiting_for_text)
    await callback.answer()

@dp.message(ReviewState.waiting_for_text)
async def handle_review_text(message: Message, state: FSMContext):
    data = await state.get_data()
    rating = data.get("rating")
    review_text = message.text
    user_name = f"@{message.from_user.username}" if message.from_user.username else f"ID {message.from_user.id}"
    
    review_message = (
        f"📝 Новый отзыв от {user_name}:\n"
        f"Оценка: {'⭐' * rating}\n"
        f"Отзыв: {review_text}"
    )
    
    await bot.send_message(ADMIN_ID, review_message)
    await message.answer("Спасибо за ваш отзыв! 💜", reply_markup=main_menu)
    await state.clear()

@dp.message(F.text == "❓ Помощь")
async def menu_help(message: Message):
    await message.delete ()
    kb = InlineKeyboardBuilder()
    kb.button(
        text="💬 Написать в Telegram", 
        url="https://t.me/DilovarAhi"
    )
    
    await message.answer(
        "<b>📞 Контакты поддержки</b>\n\n"
        "Служба поддержки ДУЧАРХА 💜:\n"
        "• Телеграм: @DilovarAhi\n"
        "• Телефон: +992 98 765 43 21\n\n"
        "Быстрая помощь поддержки👇",
        reply_markup=kb.as_markup(),
        parse_mode=ParseMode.HTML
    )
    
# Словарь для хранения ID пользователей, которые взаимодействовали с ботом
active_users = set()

@dp.message()
async def track_users(message: Message):
    """Track all users who interact with the bot"""
    if message.from_user and message.from_user.id:
        active_users.add(message.from_user.id)
        print(f"Added user {message.from_user.id} to active users")

@dp.message(Command("promote"))
async def send_promotion(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
        
    promo_text = message.text.replace("/promote", "").strip()
    if not promo_text:
        await message.answer("Использование: /promote <текст акции>")
        return
        
    success_count = 0
    for user_id in active_users:
        try:
            await bot.send_message(
                user_id,
                f"🎉 <b>Специальное предложение!</b>\n\n{promo_text}",
                reply_markup=main_menu
            )
            success_count += 1
        except Exception:
            continue
            
    await message.answer(f"Уведомление отправлено {success_count} пользователям!")

# === Запуск бота ===
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
