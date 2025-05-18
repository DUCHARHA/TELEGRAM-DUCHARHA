await state.clear()

@dp.message(Command("status"))
async def change_order_status(message: Message):
if message.from_user.id != ADMIN_ID:
return
try:
parts = message.text.split()
if len(parts) != 3:
raise ValueError("Формат команды: /status <user_id> <status>")
_, user_id_str, status_str = parts
user_id = int(user_id_str)
status = OrderStatus[status_str.upper()]
if user_id in user_orders:
user_orders[user_id]["status"] = status
await bot.send_message(user_id, f"<b>{status.value}</b>")
await message.answer(f"Статус заказа пользователя {user_id} обновлён: {status.value}")
else:
await message.answer("Заказ не найден.")
except Exception as e:
await message.answer("Ошибка. Пример: /status 123456789 preparing\nДоступные статусы: accepted, preparing, on_the_way, delivered")

@dp.callback_query(lambda c: c.data == "back")
async def go_back(callback: types.CallbackQuery):
await send_welcome(callback.message)
await callback.answer()

@dp.message(Command("cart"))
async def cmd_cart(message: Message):
user_id = message.from_user.id
cart = user_carts.get(user_id, [])
if cart:
total = sum(price for _, price in cart)
text = "Ваша корзина:\n" + "\n".join(f"- {item} — {price} сом" for item, price in cart)
text += f"\n\n<b>Итого: {total} сом</b>"
else:
text = "Корзина пуста."
kb = InlineKeyboardBuilder()
if cart:
kb.button(text="Оформить заказ", callback_data="checkout")
kb.button(text="Назад", callback_data="back")
await message.answer(text, reply_markup=kb.as_markup())

@dp.message(Command("orders"))
async def cmd_orders(message: Message):
user_id = message.from_user.id
args = message.text.split()
status_filter = args[1].lower() if len(args) > 1 else None
if user_id in user_orders:
order = user_orders[user_id]
if status_filter and order["status"].name.lower() != status_filter:
await message.answer("У вас нет заказов с таким статусом.")
else:
await message.answer(f"{order['text']}\n\n<b>Статус:</b> {order['status'].value}")
else:
await message.answer("У вас пока нет активных заказов.")

@dp.message(Command("contacts"))
async def cmd_contacts(message: Message):
await message.answer("Контакты магазина: @DilovarAhi")

@dp.message(Command("help"))
async def cmd_help(message: Message):
await message.answer("Напишите /start чтобы начать. Выберите категорию и оформите заказ.")

@dp.message(F.text == "📂 Каталог")
async def menu_catalog(message: Message):
await send_welcome(message)

@dp.message(F.text == "🛍 Корзина")
async def menu_cart(message: Message):
await cmd_cart(message)

@dp.message(F.text == "📦 Заказы")
async def menu_orders(message: Message):
await cmd_orders(message)

@dp.message(F.text == "📢 Новости")
async def menu_news(message: Message):
await message.answer("Нет новостей пока.")

@dp.message(F.text == "⚙️ Настройки")
async def menu_settings(message: Message):
await message.answer("Настройки пока недоступны.")

@dp.message(F.text == "❓ Помощь")
async def menu_help(message: Message):
await cmd_help(message)

async def main():
await dp.start_polling(bot)

if name == "main":
keep_alive()
asyncio.run(main()