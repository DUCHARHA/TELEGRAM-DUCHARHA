
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.types import Message
from aiogram.filters import Command, CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.storage.memory import MemoryStorage
import asyncio
import logging

# Токен для анонимного бота (нужно создать отдельного бота через @BotFather)
ANONYMOUS_BOT_TOKEN = "YOUR_ANONYMOUS_BOT_TOKEN"  # Замените на токен анонимного бота
ADMIN_ID = 1648127193  # ID администратора

# Инициализация анонимного бота
anonymous_bot = Bot(token=ANONYMOUS_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
anonymous_dp = Dispatcher(storage=MemoryStorage())

# Хранилище активных чатов: {chat_id: {"order_number": "order_id", "customer_id": user_id, "courier_id": user_id}}
active_chats = {}
# Связь пользователей с чатами: {user_id: chat_id}
user_to_chat = {}

@anonymous_dp.message(CommandStart())
async def anonymous_start(message: Message):
    user_id = message.from_user.id
    
    # Проверяем, есть ли активный чат для этого пользователя
    if user_id in user_to_chat:
        chat_id = user_to_chat[user_id]
        chat_info = active_chats.get(chat_id, {})
        order_number = chat_info.get("order_number", "N/A")
        
        kb = InlineKeyboardBuilder()
        kb.button(text="📝 Написать сообщение", callback_data="write_message")
        kb.button(text="❌ Завершить чат", callback_data="end_chat")
        
        await message.answer(
            f"🔒 <b>Анонимный чат</b>\n"
            f"📦 Заказ: #{order_number}\n\n"
            f"Вы можете общаться анонимно. Ваши личные данные не передаются собеседнику.",
            reply_markup=kb.as_markup()
        )
    else:
        await message.answer(
            "🔒 <b>Анонимный чат</b>\n\n"
            "Этот бот предназначен для анонимного общения между курьерами и клиентами.\n"
            "Доступ предоставляется автоматически при активном заказе."
        )

@anonymous_dp.callback_query(F.data == "write_message")
async def prompt_write_message(callback: types.CallbackQuery):
    await callback.message.answer(
        "✍️ Напишите ваше сообщение:",
        reply_markup=InlineKeyboardBuilder().button(text="❌ Отмена", callback_data="cancel_message").as_markup()
    )
    await callback.answer()

@anonymous_dp.callback_query(F.data == "cancel_message")
async def cancel_message(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer("Отменено")

@anonymous_dp.callback_query(F.data == "end_chat")
async def end_chat(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id in user_to_chat:
        chat_id = user_to_chat[user_id]
        chat_info = active_chats.get(chat_id, {})
        
        customer_id = chat_info.get("customer_id")
        courier_id = chat_info.get("courier_id")
        order_number = chat_info.get("order_number", "N/A")
        
        # Уведомляем обе стороны о завершении чата
        end_message = f"💬 <b>Чат завершен</b>\n📦 Заказ: #{order_number}\n\nСпасибо за использование анонимного чата!"
        
        try:
            if customer_id and customer_id != user_id:
                await anonymous_bot.send_message(customer_id, end_message)
            if courier_id and courier_id != user_id:
                await anonymous_bot.send_message(courier_id, end_message)
        except Exception as e:
            logging.error(f"Error notifying about chat end: {e}")
        
        # Удаляем чат из активных
        if customer_id in user_to_chat:
            del user_to_chat[customer_id]
        if courier_id in user_to_chat:
            del user_to_chat[courier_id]
        if chat_id in active_chats:
            del active_chats[chat_id]
        
        # Уведомляем администратора
        try:
            await anonymous_bot.send_message(
                ADMIN_ID,
                f"💬 <b>Анонимный чат завершен</b>\n"
                f"📦 Заказ: #{order_number}\n"
                f"Инициатор: {'Клиент' if user_id == customer_id else 'Курьер'}"
            )
        except Exception as e:
            logging.error(f"Error notifying admin: {e}")
    
    await callback.message.edit_text("✅ Чат завершен. Спасибо за использование анонимного чата!")
    await callback.answer()

@anonymous_dp.message(F.text)
async def handle_anonymous_message(message: Message):
    user_id = message.from_user.id
    
    if user_id not in user_to_chat:
        await message.answer("У вас нет активного чата. Начните с /start")
        return
    
    chat_id = user_to_chat[user_id]
    chat_info = active_chats.get(chat_id, {})
    
    customer_id = chat_info.get("customer_id")
    courier_id = chat_info.get("courier_id")
    order_number = chat_info.get("order_number", "N/A")
    
    # Определяем получателя
    if user_id == customer_id:
        recipient_id = courier_id
        sender_role = "👤 Клиент"
    elif user_id == courier_id:
        recipient_id = customer_id
        sender_role = "🚗 Курьер"
    else:
        await message.answer("Ошибка: вы не участник этого чата")
        return
    
    if not recipient_id:
        await message.answer("Собеседник недоступен")
        return
    
    # Отправляем сообщение получателю
    try:
        kb = InlineKeyboardBuilder()
        kb.button(text="↩️ Ответить", callback_data="write_message")
        kb.button(text="❌ Завершить чат", callback_data="end_chat")
        
        await anonymous_bot.send_message(
            recipient_id,
            f"💬 <b>Сообщение от {sender_role}</b>\n"
            f"📦 Заказ: #{order_number}\n\n"
            f"{message.text}",
            reply_markup=kb.as_markup()
        )
        
        await message.answer("✅ Сообщение отправлено")
        
        # Уведомляем администратора о сообщении
        await anonymous_bot.send_message(
            ADMIN_ID,
            f"💬 <b>Сообщение в анонимном чате</b>\n"
            f"📦 Заказ: #{order_number}\n"
            f"От: {sender_role}\n"
            f"Текст: {message.text}"
        )
        
    except Exception as e:
        logging.error(f"Error sending anonymous message: {e}")
        await message.answer("Ошибка при отправке сообщения")

# Функция для создания анонимного чата
async def create_anonymous_chat(order_number: str, customer_id: int, courier_id: int):
    """Создает анонимный чат между клиентом и курьером"""
    chat_id = f"{order_number}_{customer_id}_{courier_id}"
    
    active_chats[chat_id] = {
        "order_number": order_number,
        "customer_id": customer_id,
        "courier_id": courier_id
    }
    
    user_to_chat[customer_id] = chat_id
    user_to_chat[courier_id] = chat_id
    
    # Отправляем приглашения в анонимный чат
    chat_invitation = (
        f"💬 <b>Создан анонимный чат</b>\n"
        f"📦 Заказ: #{order_number}\n\n"
        f"Перейдите в анонимный бот для безопасного общения:\n"
        f"@YOUR_ANONYMOUS_BOT_USERNAME"  # Замените на username анонимного бота
    )
    
    kb = InlineKeyboardBuilder()
    kb.button(text="💬 Перейти в анонимный чат", url="https://t.me/YOUR_ANONYMOUS_BOT_USERNAME")
    
    try:
        await anonymous_bot.send_message(customer_id, chat_invitation, reply_markup=kb.as_markup())
        await anonymous_bot.send_message(courier_id, chat_invitation, reply_markup=kb.as_markup())
        
        # Уведомляем администратора
        await anonymous_bot.send_message(
            ADMIN_ID,
            f"💬 <b>Создан анонимный чат</b>\n"
            f"📦 Заказ: #{order_number}\n"
            f"👤 Клиент: ID {customer_id}\n"
            f"🚗 Курьер: ID {courier_id}"
        )
        
        return True
    except Exception as e:
        logging.error(f"Error creating anonymous chat: {e}")
        return False

async def start_anonymous_bot():
    """Запуск анонимного бота"""
    logging.info("Starting anonymous bot...")
    await anonymous_dp.start_polling(anonymous_bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_anonymous_bot())
