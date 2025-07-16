from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.enums import ParseMode
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command, CommandStart
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import asyncio
import os
from keep_alive import keep_alive
from enum import Enum
from aiogram.fsm.storage.memory import MemoryStorage
from datetime import datetime, timedelta

daily_order_counter = {}
order_number_to_user = {}

API_TOKEN = os.getenv("API_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
COURIERS_CHAT_ID = int(os.getenv("COURIERS_CHAT_ID"))

last_help_message_id = None

# --- Bot Initialization ---
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# --- Keyboards ---
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📂 Каталог"), KeyboardButton(text="🛍 Корзина")],
        [KeyboardButton(text="📦 Мои заказы"), KeyboardButton(text="📢 Новости")],
        [KeyboardButton(text="⭐️ Оставить отзыв"), KeyboardButton(text="❓ Помощь")]
    ],
    resize_keyboard=True
)

# --- FSM States ---
class OrderForm(StatesGroup):
    waiting_for_location = State()
    confirm_address = State()
    waiting_for_phone = State()
    waiting_for_address_details = State()

class SearchState(StatesGroup):
    waiting_for_query = State()

class OrderStatus(Enum):
    ACCEPTED = "Ваш заказ принят"
    PREPARING = "Ваш заказ собирается"
    ON_THE_WAY = "Ваш заказ едет к вам"
    DELIVERED = "Ваш заказ доставлен"

# --- In-memory Data Storage ---
user_carts = {}
user_orders = {}
order_couriers = {}

# Product catalog with subcategories and item variants
products = {
    "category_fruits": {
        "Яблоки": {
            "Яблоко": {
                "Красное": {"price": 3, "unit": "кг"}, 
                "Зеленое": {"price": 3, "unit": "кг"}, 
                "Желтое": {"price": 3, "unit": "кг"}
            }
        },
        "Цитрусовые": {
            "Апельсин": {
                "Обычный": {"price": 5, "unit": "кг"}
            }, 
            "Мандарин": {
                "Обычный": {"price": 6, "unit": "кг"}
            }, 
            "Лимон": {
                "Обычный": {"price": 8, "unit": "кг"}
            }, 
            "Грейпфрут": {
                "Обычный": {"price": 7, "unit": "кг"}
            }
        },
        "Экзотические": {
            "Банан": {
                "Обычный": {"price": 4, "unit": "кг"}
            }, 
            "Киви": {
                "Обычный": {"price": 7, "unit": "шт"}
            }, 
            "Ананас": {
                "Обычный": {"price": 15, "unit": "шт"}
            }
        },
        "Сезонные": {
            "Виноград": {
                "Обычный": {"price": 8, "unit": "кг"}
            }, 
            "Персик": {
                "Обычный": {"price": 6, "unit": "кг"}
            }, 
            "Нектарин": {
                "Обычный": {"price": 6, "unit": "кг"}
            }, 
            "Слива": {
                "Обычный": {"price": 4, "unit": "кг"}
            }, 
            "Груша": {
                "Обычный": {"price": 4, "unit": "кг"}
            }
        }
    },
    "category_vegetables": {
        "Корнеплоды": {
            "Картошка": {
                "Молодая": {"price": 3, "unit": "кг"}, 
                "Обычная": {"price": 2, "unit": "кг"}
            }, 
            "Морковь": {
                "Обычная": {"price": 1, "unit": "кг"}
            }, 
            "Свекла": {
                "Обычная": {"price": 2, "unit": "кг"}
            }
        },
        "Зелень": {
            "Лук зеленый": {
                "Обычный": {"price": 3, "unit": "кг"}
            }, 
            "Укроп": {
                "Обычный": {"price": 5, "unit": "кг"}
            }, 
            "Петрушка": {
                "Обычная": {"price": 5, "unit": "кг"}
            }, 
            "Кинза": {
                "Обычная": {"price": 4, "unit": "кг"}
            }
        },
        "Овощи для салата": {
            "Огурец": {
                "Парниковый": {"price": 4, "unit": "кг"}, 
                "Грунтовый": {"price": 3, "unit": "кг"}
            }, 
            "Помидор": {
                "Розовый": {"price": 5, "unit": "кг"}, 
                "Красный": {"price": 4, "unit": "кг"}
            }, 
            "Капуста": {
                "Белокочанная": {"price": 3, "unit": "шт"}
            }
        },
        "Приправы": {
            "Лук репчатый": {
                "Обычный": {"price": 2, "unit": "кг"}
            }, 
            "Чеснок": {
                "Обычный": {"price": 3, "unit": "кг"}
            }, 
            "Перец болгарский": {
                "Обычный": {"price": 5, "unit": "кг"}
            }, 
            "Перец острый": {
                "Обычный": {"price": 8, "unit": "кг"}
            }
        }
    },
    "category_drinks": {
        "Газированные": {
            "Coca-Cola": {
                "0.5л": {"price": 6, "unit": "шт"},
                "1л": {"price": 10, "unit": "шт"},
                "1.5л": {"price": 12, "unit": "шт"}
            }, 
            "Pepsi": {
                "0.5л": {"price": 6, "unit": "шт"},
                "1л": {"price": 10, "unit": "шт"},
                "1.5л": {"price": 12, "unit": "шт"}
            }, 
            "Fanta": {
                "0.5л": {"price": 6, "unit": "шт"},
                "1л": {"price": 10, "unit": "шт"}
            }, 
            "Sprite": {
                "0.5л": {"price": 6, "unit": "шт"},
                "1л": {"price": 10, "unit": "шт"}
            }, 
            "7UP": {
                "0.5л": {"price": 6, "unit": "шт"}
            }
        },
        "Соки": {
            "Сок яблочный J7": {
                "1л": {"price": 8, "unit": "шт"}
            }, 
            "Сок апельсиновый J7": {
                "1л": {"price": 8, "unit": "шт"}
            }, 
            "Сок томатный": {
                "1л": {"price": 7, "unit": "шт"}
            }, 
            "Нектар персиковый": {
                "1л": {"price": 6, "unit": "шт"}
            }
        },
        "Вода": {
            "Вода Ессентуки": {
                "0.5л": {"price": 4, "unit": "шт"}
            }, 
            "Вода обычная": {
                "1.5л": {"price": 2, "unit": "шт"},
                "5л": {"price": 5, "unit": "шт"}
            }, 
            "Вода газированная": {
                "0.5л": {"price": 3, "unit": "шт"}
            }
        },
        "Энергетики": {
            "Red Bull": {
                "250мл": {"price": 12, "unit": "шт"}
            }, 
            "Monster": {
                "500мл": {"price": 10, "unit": "шт"}
            }, 
            "Burn": {
                "250мл": {"price": 8, "unit": "шт"}
            }
        },
        "Чай/Кофе": {
            "Холодный чай Lipton": {
                "0.5л": {"price": 5, "unit": "шт"}
            }, 
            "Квас Никола": {
                "1л": {"price": 4, "unit": "шт"}
            }, 
            "Компот домашний": {
                "1л": {"price": 4, "unit": "шт"}
            }
        }
    },
    "category_snacks": {
        "Чипсы": {
            "Lay's": {
                "Классические": {"price": 5, "unit": "шт"}, 
                "Сметана-лук": {"price": 5, "unit": "шт"},
                "Сыр": {"price": 5, "unit": "шт"}
            }, 
            "Pringles": {
                "Original": {"price": 8, "unit": "шт"},
                "Сметана-лук": {"price": 8, "unit": "шт"}
            }, 
            "Estrella": {
                "Классические": {"price": 4, "unit": "шт"}
            }
        },
        "Сухарики": {
            "Кириешки": {
                "Бекон": {"price": 3, "unit": "шт"}, 
                "Сыр": {"price": 3, "unit": "шт"}
            }, 
            "Сухарики ржаные": {
                "Обычные": {"price": 2, "unit": "шт"}
            }
        },
        "Шоколад": {
            "Snickers": {
                "Обычный": {"price": 6, "unit": "шт"}
            }, 
            "Twix": {
                "Обычный": {"price": 6, "unit": "шт"}
            }, 
            "KitKat": {
                "Обычный": {"price": 6, "unit": "шт"}
            }, 
            "Alpen Gold": {
                "Молочный": {"price": 8, "unit": "шт"}
            }, 
            "Аленка": {
                "Молочный": {"price": 5, "unit": "шт"}
            }
        },
        "Печенье": {
            "Oreo": {
                "Классическое": {"price": 5, "unit": "шт"}
            }, 
            "Юбилейное": {
                "Классическое": {"price": 4, "unit": "шт"}
            }, 
            "Крекер TUC": {
                "Классический": {"price": 4, "unit": "шт"}
            }
        },
        "Орехи/Семечки": {
            "Семечки": {
                "Жареные": {"price": 2, "unit": "шт"}
            }, 
            "Арахис": {
                "Соленый": {"price": 4, "unit": "шт"}
            }, 
            "Миндаль": {
                "Обычный": {"price": 12, "unit": "шт"}
            }, 
            "Фисташки": {
                "Соленые": {"price": 15, "unit": "шт"}
            }
        }
    },
    "category_milks": {
        "Молоко": {
            "Простоквашино": {
                "1л": {"price": 18, "unit": "шт"}
            }, 
            "Молоко домашнее": {
                "1л": {"price": 15, "unit": "шт"}
            }, 
            "Веселый молочник": {
                "1л": {"price": 16, "unit": "шт"}
            }
        },
        "Кисломолочные": {
            "Кефир": {
                "Простоквашино": {"price": 12, "unit": "шт"}
            }, 
            "Ряженка": {
                "Обычная": {"price": 15, "unit": "шт"}
            }, 
            "Простокваша": {
                "Обычная": {"price": 13, "unit": "шт"}
            }, 
            "Айран": {
                "Обычный": {"price": 10, "unit": "шт"}
            }
        },
        "Сметана/Творог": {
            "Сметана": {
                "20%": {"price": 14, "unit": "шт"}, 
                "Домашняя": {"price": 18, "unit": "шт"}
            }, 
            "Творог": {
                "Зернистый": {"price": 16, "unit": "шт"}, 
                "Обезжиренный": {"price": 14, "unit": "шт"}
            }
        },
        "Йогурты": {
            "Данон": {
                "Классический": {"price": 8, "unit": "шт"}
            }, 
            "Активиа": {
                "Классическая": {"price": 9, "unit": "шт"}
            }, 
            "Йогурт домашний": {
                "Обычный": {"price": 6, "unit": "шт"}
            }
        },
        "Сыр/Масло": {
            "Сыр": {
                "Российский": {"price": 25, "unit": "кг"}, 
                "Голландский": {"price": 30, "unit": "кг"}
            }, 
            "Масло сливочное": {
                "Обычное": {"price": 20, "unit": "шт"}
            }, 
            "Сливки": {
                "20%": {"price": 19, "unit": "шт"}
            }
        }
    }
}

# Category names in Russian
category_names = {
    "category_fruits": "Фрукты",
    "category_vegetables": "Овощи", 
    "category_drinks": "Напитки",
    "category_snacks": "Снеки",
    "category_milks": "Молочка"
}

active_users = set()
user_search_history = {}
search_cache = {}
popular_searches = ["яблоко", "молоко", "хлеб", "картошка", "банан"]

# Global mapping for shorter callback data
current_subcategory_mapping = {}
current_item_mapping = {}

# --- Command Handlers ---
@dp.message(CommandStart())
async def send_welcome(message: Message):
    user_id = message.from_user.id
    active_users.add(user_id)

    kb = InlineKeyboardBuilder()
    kb.button(text="Фрукты", callback_data="category_fruits")
    kb.button(text="Овощи", callback_data="category_vegetables")
    kb.button(text="Напитки", callback_data="category_drinks")
    kb.button(text="Снеки", callback_data="category_snacks")
    kb.button(text="Молочка", callback_data="category_milks")
    kb.adjust(2,2,1)

    # Add search button in initial start menu
    kb.row(types.InlineKeyboardButton(text="🔍 Поиск", callback_data="search_menu"))

    await message.answer(
        "Добро пожаловать! Ждём ваших заказов 💜",
        reply_markup=main_menu
    )
    await bot.send_sticker(
        message.chat.id,
        "CAACAgQAAxkBAAIJT2gmdq7qFlY80egtqdn3Q0QPoA5iAAISDQAC1MiAUAXbnVAhxur0NgQ"
    )
    await message.answer("Выберите категорию:", reply_markup=kb.as_markup())

@dp.message(Command("status"))
async def change_order_status(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("Эта команда доступна только администратору.")
        return

    try:
        parts = message.text.split()
        if len(parts) != 3:
            raise ValueError("Неверный формат команды. Используйте: /status <номер_заказа> <статус>")

        _, order_number_str, status_str = parts
        order_number = int(order_number_str)

        valid_statuses = [s.name for s in OrderStatus]
        if status_str.upper() not in valid_statuses:
            raise ValueError(f"Неверный статус. Доступные статусы: {', '.join(s.lower() for s in valid_statuses)}")

        status = OrderStatus[status_str.upper()]

        target_user_id = None
        order_to_update = None

        for uid, orders_list in user_orders.items():
            for order_data in orders_list:
                if order_data.get("order_number") == order_number:
                    target_user_id = uid
                    order_to_update = order_data
                    break
            if target_user_id:
                break

        if target_user_id and order_to_update:
            order_to_update["status"] = status
            await bot.send_message(target_user_id, f"<b>Статус вашего заказа #{order_number} изменен: {status.value}</b>")
            await message.answer(f"Статус заказа №{order_number} обновлён на: {status.value}")
        else:
            await message.answer(f"Заказ с номером {order_number} не найден.")

    except ValueError as e:
        await message.answer(f"Ошибка: {e}")
    except Exception as e:
        await message.answer(
            "Произошла непредвиденная ошибка при обновлении статуса.\n"
            "Убедитесь, что формат команды: /status <номер_заказа> <статус>\n"
            f"Например: /status 1 preparing\n"
            f"Доступные статусы: {', '.join(s.name.lower() for s in OrderStatus)}"
        )
        print(f"Error in change_order_status: {e}")

@dp.message(F.sticker)
async def get_sticker_id(message: Message):
    user_id = message.from_user.id
    active_users.add(user_id)

    if message.from_user.id == ADMIN_ID:
        await message.answer(f"file_id стикера:\n<code>{message.sticker.file_id}</code>")

# --- Callback Query Handlers ---
@dp.callback_query(lambda c: c.data.startswith("category_"))
async def show_category(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    active_users.add(user_id)

    category_key = callback.data
    category_name_display = category_names.get(category_key, category_key.replace("category_", "").capitalize())
    subcategories = products.get(category_key, {})

    if not subcategories:
        await callback.message.edit_text(f"В категории '{category_name_display}' пока нет товаров.", 
                                       reply_markup=InlineKeyboardBuilder().button(text="⬅️ Назад к категориям", callback_data="back_to_categories").as_markup())
        await callback.answer()
        return

    kb = InlineKeyboardBuilder()
    # Create mapping for shorter callback data
    subcategory_mapping = {}
    for idx, subcategory_name in enumerate(subcategories.keys()):
        short_id = f"sub_{idx}"
        subcategory_mapping[short_id] = subcategory_name
        kb.button(text=f"{subcategory_name}", callback_data=f"subcategory_{category_key}_{short_id}")

    # Store mapping in a global variable for later use
    global current_subcategory_mapping
    current_subcategory_mapping = subcategory_mapping

    # Grid layout for subcategories
    subcategory_count = len(subcategories)
    if subcategory_count <= 4:
        kb.adjust(2)
    elif subcategory_count <= 6:
        kb.adjust(3)
    else:
        kb.adjust(2)

    kb.row(
        types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_categories"),
        types.InlineKeyboardButton(text="🛒 Корзина", callback_data="cart")
    )

    kb.row(types.InlineKeyboardButton(text="🔍 Поиск", callback_data="search_menu"))

    await callback.message.edit_text(f"<b>{category_name_display}</b>\nВыберите подкатегорию:", reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("subcategory_"))
async def show_subcategory(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    active_users.add(user_id)

    # Parse callback data: subcategory_category_fruits_sub_0
    callback_data = callback.data.replace("subcategory_", "")

    parts = callback_data.split("_")
    if len(parts) < 4:
        await callback.answer("Ошибка: неверный формат подкатегории.", show_alert=True)
        return

    # Reconstruct category_key and get subcategory by short ID
    category_key = f"category_{parts[1]}"  # category_fruits, category_vegetables, etc.
    short_id = "_".join(parts[2:])  # sub_0, sub_1, etc.

    # Get real subcategory name from mapping
    subcategory_name = current_subcategory_mapping.get(short_id)
    if not subcategory_name:
        await callback.answer("Ошибка: подкатегория не найдена.", show_alert=True)
        return

    category_name_display = category_names.get(category_key, category_key.replace("category_", "").capitalize())

    subcategories = products.get(category_key, {})
    items = subcategories.get(subcategory_name, {})

    if not items:
        await callback.message.edit_text(f"В подкатегории '{subcategory_name}' пока нет товаров.", 
                                       reply_markup=InlineKeyboardBuilder().button(text="⬅️ Назад", callback_data=category_key).as_markup())
        await callback.answer()
        return

    kb = InlineKeyboardBuilder()
    # Create mapping for shorter callback data
    item_mapping = {}
    for idx, item_name in enumerate(items.keys()):
        short_item_id = f"itm_{idx}"
        item_mapping[short_item_id] = item_name
        kb.button(text=f"{item_name}", callback_data=f"show_item_{category_key.replace('category_', '')}_{short_item_id}")

    # Store item mapping globally 
    global current_item_mapping
    current_item_mapping.update(item_mapping)

    # Smart grid layout
    item_count = len(items)
    if item_count <= 6:
        kb.adjust(2)
    elif item_count <= 12:
        kb.adjust(3)
    else:
        kb.adjust(2)

    kb.row(
        types.InlineKeyboardButton(text="⬅️ Назад", callback_data=category_key),
        types.InlineKeyboardButton(text="🛒 Корзина", callback_data="cart")
    )

    kb.row(types.InlineKeyboardButton(text="🔍 Поиск", callback_data="search_menu"))

    await callback.message.edit_text(f"<b>{category_name_display} → {subcategory_name}</b>:", reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("show_item_"))
async def show_item_variants(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    active_users.add(user_id)

    # Parse callback data: show_item_fruits_itm_0
    callback_data = callback.data.replace("show_item_", "")
    parts = callback_data.split("_")

    if len(parts) < 3:
        await callback.answer("Ошибка: неверный формат товара.", show_alert=True)
        return

    # Get category and item short ID
    category_name = parts[0]  # fruits, vegetables, etc.
    item_short_id = "_".join(parts[1:])  # itm_0, itm_1, etc.

    category_key = f"category_{category_name}"

    # Get real item name from mapping
    item_name = current_item_mapping.get(item_short_id)
    if not item_name:
        await callback.answer("Ошибка: товар не найден.", show_alert=True)
        return

    # Find which subcategory contains this item
    subcategories = products.get(category_key, {})
    subcategory_name = None
    item_variants = None

    for subcat_name, subcat_items in subcategories.items():
        if item_name in subcat_items:
            subcategory_name = subcat_name
            item_variants = subcat_items[item_name]
            break

    if not subcategory_name or not item_variants:
        await callback.answer("Ошибка: товар не найден.", show_alert=True)
        return

    category_name_display = category_names.get(category_key, category_key.replace("category_", "").capitalize())

    kb = InlineKeyboardBuilder()
    # Create mapping for shorter callback data
    variant_mapping = {}
    for idx, (variant_name, variant_data) in enumerate(item_variants.items()):
        price = variant_data["price"]
        unit = variant_data["unit"]
        short_variant_id = f"var_{idx}"
        variant_mapping[short_variant_id] = variant_name
        kb.button(text=f"{variant_name} - {price} сом/{unit}", callback_data=f"add_variant_{category_name}_{item_short_id}_{short_variant_id}")

    # Store variant mapping globally 
    global current_variant_mapping
    current_variant_mapping = getattr(show_item_variants, 'current_variant_mapping', {})
    current_variant_mapping.update(variant_mapping)
    show_item_variants.current_variant_mapping = current_variant_mapping

    # Smart grid layout
    variant_count = len(item_variants)
    if variant_count <= 6:
        kb.adjust(2)
    elif variant_count <= 12:
        kb.adjust(3)
    else:
        kb.adjust(2)

    kb.row(
        types.InlineKeyboardButton(text="⬅️ Назад", callback_data=f"subcategory_{category_key}_{[k for k, v in current_subcategory_mapping.items() if v == subcategory_name][0]}"),
        types.InlineKeyboardButton(text="🛒 Корзина", callback_data="cart")
    )

    kb.row(types.InlineKeyboardButton(text="🔍 Поиск", callback_data="search_menu"))

    await callback.message.edit_text(f"<b>{category_name_display} → {subcategory_name} → {item_name}</b>:", reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("add_variant_"))
async def add_variant_to_cart(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    active_users.add(user_id)

    # Parse callback data: add_variant_fruits_itm_0_var_0
    callback_data = callback.data.replace("add_variant_", "")
    parts = callback_data.split("_")

    if len(parts) < 4:
        await callback.answer("Ошибка: неверный формат товара.", show_alert=True)
        return

    # Get category, item and variant short IDs
    category_name = parts[0]  # fruits, vegetables, etc.
    item_short_id = "_".join(parts[1:3])  # itm_0
    variant_short_id = "_".join(parts[3:])  # var_0

    category_key = f"category_{category_name}"

    # Get real names from mappings
    item_name = current_item_mapping.get(item_short_id)
    variant_name = getattr(show_item_variants, 'current_variant_mapping', {}).get(variant_short_id)

    if not item_name or not variant_name:
        await callback.answer("Ошибка: товар не найден.", show_alert=True)
        return

    # Find the item data
    subcategories = products.get(category_key, {})
    subcategory_name = None
    variant_data = None

    for subcat_name, subcat_items in subcategories.items():
        if item_name in subcat_items and variant_name in subcat_items[item_name]:
            subcategory_name = subcat_name
            variant_data = subcat_items[item_name][variant_name]
            break

    if not variant_data:
        await callback.answer("Ошибка: товар не найден в каталоге.", show_alert=True)
        return

    price = variant_data["price"]
    unit = variant_data["unit"]
    cart = user_carts.setdefault(user_id, {})

    # Use combined name for cart item
    cart_item_name = f"{item_name} {variant_name}"

    if cart_item_name in cart:
        cart[cart_item_name]["quantity"] += 1
    else:
        cart[cart_item_name] = {"price": price, "quantity": 1, "category": category_key, "subcategory": subcategory_name, "unit": unit}

    await callback.answer(f"{cart_item_name} добавлен в корзину!")

@dp.callback_query(lambda c: c.data.startswith("add_sub_"))
async def add_subcategory_to_cart(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    active_users.add(user_id)

    # Parse callback data: add_sub_fruits_itm_0
    callback_data = callback.data.replace("add_sub_", "")
    parts = callback_data.split("_")

    if len(parts) < 3:
        await callback.answer("Ошибка: неверный формат товара.", show_alert=True)
        return

    # Get category and item short ID
    category_name = parts[0]  # fruits, vegetables, etc.
    item_short_id = "_".join(parts[1:])  # itm_0, itm_1, etc.

    category_key = f"category_{category_name}"

    # Get real item name from mapping
    item_name = current_item_mapping.get(item_short_id)
    if not item_name:
        await callback.answer("Ошибка: товар не найден.", show_alert=True)
        return

    # Find which subcategory contains this item
    subcategories = products.get(category_key, {})
    subcategory_name = None
    items = None

    for subcat_name, subcat_items in subcategories.items():
        if item_name in subcat_items:
            subcategory_name = subcat_name
            items = subcat_items
            break

    if not subcategory_name or not items:
        await callback.answer("Ошибка: подкатегория не найдена.", show_alert=True)
        return

    if item_name not in items:
        await callback.answer(f"Товар '{item_name}' не найден в этой подкатегории.", show_alert=True)
        return

    item_data = items[item_name]
    price = item_data["price"]
    unit = item_data["unit"]
    cart = user_carts.setdefault(user_id, {})

    if item_name in cart:
        cart[item_name]["quantity"] += 1
    else:
        cart[item_name] = {"price": price, "quantity": 1, "category": category_key, "subcategory": subcategory_name, "unit": unit}

    await callback.answer(f"{item_name} добавлен в корзину!")

@dp.callback_query(lambda c: c.data.startswith("search_add_"))
async def add_search_to_cart(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    active_users.add(user_id)

    # Parse callback data: search_add_fruits_123
    callback_data = callback.data.replace("search_add_", "")
    parts = callback_data.split("_")

    if len(parts) < 2:
        await callback.answer("Ошибка: неверный формат товара.", show_alert=True)
        return

    category_name = parts[0]
    item_hash = parts[1]
    category_key = f"category_{category_name}"

    # Get real item name from mapping
    item_name = current_item_mapping.get(f"search_{item_hash}")
    if not item_name:
        await callback.answer("Ошибка: товар не найден.", show_alert=True)
        return

    # Find which subcategory contains this item
    subcategories = products.get(category_key, {})
    subcategory_name = None
    item_data = None

    for subcat_name, subcat_items in subcategories.items():
        if item_name in subcat_items:
            subcategory_name = subcat_name
            item_data = subcat_items[item_name]
            break

    if not item_data:
        await callback.answer("Ошибка: товар не найден в каталоге.", show_alert=True)
        return

    price = item_data["price"]
    unit = item_data["unit"]
    cart = user_carts.setdefault(user_id, {})

    if item_name in cart:
        cart[item_name]["quantity"] += 1
    else:
        cart[item_name] = {"price": price, "quantity": 1, "category": category_key, "subcategory": subcategory_name, "unit": unit}

    await callback.answer(f"{item_name} добавлен в корзину!")

@dp.callback_query(lambda c: c.data.startswith("add_"))
async def add_to_cart(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    active_users.add(user_id)

    try:
        _, category, category_name, item_name = callback.data.split("_", 3)
        category_key = f"category_{category_name}"
    except ValueError:
        await callback.answer("Ошибка: неверный формат товара.", show_alert=True)
        return

    category_items = products.get(category_key)
    if not category_items or item_name not in category_items:
        await callback.answer(f"Товар '{item_name}' не найден в этой категории.", show_alert=True)
        return

    item_data = category_items[item_name]
    price = item_data["price"]
    unit = item_data["unit"]
    cart = user_carts.setdefault(user_id, {})

    if item_name in cart:
        cart[item_name]["quantity"] += 1
    else:
        cart[item_name] = {"price": price, "quantity": 1, "category": category_key, "unit": unit}

    await callback.answer(f"{item_name} добавлен в корзину!")

@dp.callback_query(lambda c: c.data.startswith("increase_"))
async def increase_quantity(callback: types.CallbackQuery):
    item_name = callback.data.replace("increase_", "")
    user_id = callback.from_user.id
    active_users.add(user_id)
    cart = user_carts.get(user_id, {})

    if item_name in cart:
        cart[item_name]["quantity"] += 1
        await show_cart_logic(callback.message, user_id, edit_message=True)
        await callback.answer(f"Количество {item_name} увеличено")
    else:
        await callback.answer("Товар не найден в корзине.", show_alert=True)


@dp.callback_query(lambda c: c.data.startswith("decrease_"))
async def decrease_quantity(callback: types.CallbackQuery):
    item_name = callback.data.replace("decrease_", "")
    user_id = callback.from_user.id
    active_users.add(user_id)
    cart = user_carts.get(user_id, {})

    if item_name in cart:
        if cart[item_name]["quantity"] > 1:
            cart[item_name]["quantity"] -= 1
        else:
            del cart[item_name]
        await show_cart_logic(callback.message, user_id, edit_message=True)
        await callback.answer(f"Количество {item_name} уменьшено")
    else:
        await callback.answer("Товар не найден в корзине.", show_alert=True)


@dp.callback_query(lambda c: c.data.startswith("remove_"))
async def remove_from_cart(callback: types.CallbackQuery):
    item_to_remove = callback.data.replace("remove_", "")
    user_id = callback.from_user.id
    active_users.add(user_id)
    cart = user_carts.get(user_id, {})

    if item_to_remove in cart:
        del cart[item_to_remove]
        await show_cart_logic(callback.message, user_id, edit_message=True)
        await callback.answer(f"{item_to_remove} удален(а) из корзины.")
    else:
        await callback.answer("Товар не найден в корзине для удаления.", show_alert=True)

# Helper function for showing cart to avoid code duplication
async def show_cart_logic(message_or_callback_message: types.Message, user_id: int, edit_message: bool = False):
    cart = user_carts.get(user_id, {})
    active_users.add(user_id)

    if not cart:
        text = "Корзина пуста."
        kb = InlineKeyboardBuilder().button(text="⬅️ К категориям", callback_data="back_to_categories").as_markup()
        if edit_message:
            await message_or_callback_message.edit_text(text, reply_markup=kb)
        else:
            await message_or_callback_message.answer(text, reply_markup=kb)
        return

    text = "🛒 <b>Ваша корзина:</b>\n\n"
    total = 0
    kb = InlineKeyboardBuilder()

    for item, data in cart.items():
        price = data["price"]
        qty = data["quantity"]
        unit = data.get("unit", "шт")  # Default to "шт" if unit not found
        text += f"▪️ {item} — {qty} {unit} x {price} = {qty * price} сом\n"
        total += qty * price
        kb.row(
            types.InlineKeyboardButton(text="➖", callback_data=f"decrease_{item}"),
            types.InlineKeyboardButton(text=f"{qty}", callback_data="noop"),
            types.InlineKeyboardButton(text="➕", callback_data=f"increase_{item}"),
            types.InlineKeyboardButton(text="❌", callback_data=f"remove_{item}")
        )

    text += f"\n<b>Итого: {total} сом</b>"

    # Always show back to categories button
    kb.row(
        types.InlineKeyboardButton(text="⬅️ К категориям", callback_data="back_to_categories"),
        types.InlineKeyboardButton(text="✅ Оформить", callback_data="checkout")
    )
    kb.row(types.InlineKeyboardButton(text="🗑 Очистить корзину", callback_data="clear_cart"))

    if edit_message:
        await message_or_callback_message.edit_text(text, reply_markup=kb.as_markup())
    else:
        await message_or_callback_message.answer(text, reply_markup=kb.as_markup())

@dp.callback_query(lambda c: c.data == "cart")
async def show_cart_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    await show_cart_logic(callback.message, user_id, edit_message=True)
    await callback.answer()

@dp.callback_query(F.data == "clear_cart")
async def clear_cart_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id in user_carts:
        user_carts[user_id] = {}
        await callback.answer("Корзина очищена!", show_alert=True)
        # Show empty cart message
        await show_cart_logic(callback.message, user_id, edit_message=True)
    else:
        await callback.answer("Корзина уже пуста.", show_alert=True)


# --- Checkout Process (FSM) ---
@dp.callback_query(lambda c: c.data == "checkout")
async def checkout_start(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    active_users.add(user_id)
    cart = user_carts.get(user_id, {})
    if not cart:
        await callback.answer("Ваша корзина пуста. Нечего оформлять.", show_alert=True)
        # Optionally, redirect to categories or show empty cart message
        await show_cart_logic(callback.message, user_id, edit_message=True)
        return

    kb = InlineKeyboardBuilder()
    kb.button(text="📍 Отправить геолокацию", callback_data="send_location_action")
    kb.button(text="📝 Ввести адрес вручную", callback_data="write_address_action")
    kb.button(text="⬅️ Назад в корзину", callback_data="cart")
    kb.adjust(1)
    await callback.message.edit_text(
        "<b>Оформление заказа</b>\nКак вы хотите указать адрес доставки?",
        reply_markup=kb.as_markup()
    )
    await state.set_state(OrderForm.waiting_for_location)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "send_location_action", OrderForm.waiting_for_location)
async def ask_geo_permission(callback: types.CallbackQuery, state: FSMContext):
    # This reply keyboard is temporary and will be replaced by the main_menu later
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Отправить мою геолокацию", request_location=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await callback.message.answer(
        "Нажмите кнопку ниже, чтобы отправить вашу геолокацию.",
        reply_markup=kb
    )
    # The state is already waiting_for_location, user will send a location message
    await callback.answer()

@dp.callback_query(lambda c: c.data == "write_address_action", OrderForm.waiting_for_location)
async def ask_manual_address_input(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Пожалуйста, введите ваш адрес доставки (улица, дом, этаж, квартира, ориентир):",
        # No inline keyboard needed here, user will type.
        # Can add a "cancel" or "back" button if desired.
        reply_markup=InlineKeyboardBuilder().button(text="⬅️ Отмена", callback_data="checkout_cancel").as_markup()
    )
    await state.set_state(OrderForm.confirm_address)
    await callback.answer()

# Handles location sent via button
@router.message(OrderForm.waiting_for_location, F.location)
async def process_location_sent(message: Message, state: FSMContext):
    latitude = message.location.latitude
    longitude = message.location.longitude
    # Using a more common map link format
    address = f"https://www.google.com/maps?q={latitude},{longitude}"
    # address = f"https://yandex.ru/maps/?ll={longitude}%2C{latitude}&z=18&l=map&pt={longitude},{latitude},pm2rdl"
    await state.update_data(address=address, address_type="location")

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, верно", callback_data="confirm_address_yes")
    kb.button(text="✏️ Изменить", callback_data="confirm_address_no")
    await message.answer(
        f"Ваш адрес: <a href='{address}'>посмотреть на карте</a>\nВерно?",
        reply_markup=kb.as_markup(),
        disable_web_page_preview=False
    )

# Handles manually typed address
@router.message(OrderForm.confirm_address, F.text)
async def process_manual_address(message: Message, state: FSMContext):
    address = message.text
    if len(address) < 5:
        await message.reply("Адрес слишком короткий. Пожалуйста, введите более подробный адрес или отмените.",
                            reply_markup=InlineKeyboardBuilder().button(text="⬅️ Отмена", callback_data="checkout_cancel").as_markup())
        return

    # Create Yandex Maps link
    yandex_maps_query = f"https://yandex.ru/maps/?text={address.replace(' ', '+')}"
    await state.update_data(address=f'<a href="{yandex_maps_query}">{address}</a>', address_type="manual")
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, верно", callback_data="confirm_address_yes")
    kb.button(text="✏️ Изменить", callback_data="confirm_address_no")
    await message.answer(
        f"Вы указали адрес: <code>{address}</code>\nВерно?",
        reply_markup=kb.as_markup()
    )
    # State is already confirm_address, or can transition to a dedicated confirmation state.

# General handler for unexpected input during address states
@router.message(OrderForm.waiting_for_location)
@router.message(OrderForm.confirm_address)
async def address_fallback_handler(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == OrderForm.waiting_for_location.state:
        await message.reply("Пожалуйста, отправьте геолокацию с помощью кнопки или выберите ввод адреса вручную.")
    elif current_state == OrderForm.confirm_address.state:
        await message.reply("Пожалуйста, введите ваш адрес текстом или нажмите 'Изменить' для выбора другого способа.")


@dp.callback_query(lambda c: c.data == "confirm_address_yes", OrderForm.waiting_for_location)
@dp.callback_query(lambda c: c.data == "confirm_address_yes", OrderForm.confirm_address)
async def address_confirmed_ask_phone(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Адрес подтвержден. Теперь введите ваш номер телефона (например, +992XXXXXXXXX или 90XXXXXXX):",
        reply_markup=InlineKeyboardBuilder().button(text="⬅️ Отмена", callback_data="checkout_cancel").as_markup()
    )
    await state.set_state(OrderForm.waiting_for_phone)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "confirm_address_no", OrderForm.waiting_for_location)
@dp.callback_query(lambda c: c.data == "confirm_address_no", OrderForm.confirm_address)
async def address_retry_choice(callback: types.CallbackQuery, state: FSMContext):
    # Go back to the initial choice of location vs manual
    kb = InlineKeyboardBuilder()
    kb.button(text="📍 Отправить геолокацию", callback_data="send_location_action")
    kb.button(text="📝 Ввести адрес вручную", callback_data="write_address_action")
    kb.button(text="⬅️ Отмена", callback_data="checkout_cancel")
    kb.adjust(1)
    await callback.message.edit_text(
        "Пожалуйста, укажите адрес доставки еще раз:",
        reply_markup=kb.as_markup()
    )
    await state.set_state(OrderForm.waiting_for_location)
    await callback.answer()

@dp.callback_query(F.data == "checkout_cancel", OrderForm.waiting_for_location)
@dp.callback_query(F.data == "checkout_cancel", OrderForm.confirm_address)
@dp.callback_query(F.data == "checkout_cancel", OrderForm.waiting_for_phone)
async def checkout_cancel_process(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Оформление заказа отменено.")
    # Show cart again or main menu
    await show_cart_logic(callback.message, callback.from_user.id, edit_message=False)
    await callback.answer("Оформление отменено.")

@dp.callback_query(F.data == "back_to_categories", SearchState.waiting_for_query)
async def search_cancel_process(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await go_back_to_categories(callback)


@router.message(OrderForm.waiting_for_phone, F.text)
async def process_phone_and_complete_order(message: Message, state: FSMContext):
    phone = message.text
    # Basic phone validation (can be improved with regex)
    if not (phone.replace("+", "").isdigit() and len(phone.replace("+", "")) >= 7):
        await message.reply("Некорректный формат телефона. Пожалуйста, введите номер еще раз или отмените.",
                            reply_markup=InlineKeyboardBuilder().button(text="⬅️ Отмена", callback_data="checkout_cancel").as_markup())
        return

    data = await state.get_data()
    address = data.get("address", "Не указан")
    user_id = message.from_user.id

    # Generate daily order number
    today = datetime.now().strftime("%Y-%m-%d")
    current_day_count = daily_order_counter.get(today, 0) + 1
    daily_order_counter[today] = current_day_count
    order_display_number = f"{datetime.now().strftime('%d%m')}-{current_day_count}"


    cart = user_carts.get(user_id, {})
    if not cart:
        await message.answer("Произошла ошибка: ваша корзина пуста. Заказ не может быть оформлен.", reply_markup=main_menu)
        await state.clear()
        return

    order_items_text_parts = []
    total_amount = 0
    for item, item_data in cart.items():
        item_total = item_data['price'] * item_data['quantity']
        unit = item_data.get('unit', 'шт')
        order_items_text_parts.append(
            f"- {item} x {item_data['quantity']} {unit} = {item_total} сом"
        )
        total_amount += item_total

    order_details_text = "\n".join(order_items_text_parts)

    # Construct message for user
    user_confirmation_text = (
        f"✅ <b>Заказ #{order_display_number} успешно оформлен!</b>\n\n"
        f"<b>Состав заказа:</b>\n{order_details_text}\n\n"
        f"<b>Итого к оплате: {total_amount} сом</b>\n"
        f"<b>Адрес доставки:</b> {address}\n"
        f"<b>Ваш телефон:</b> {phone}\n\n"
        f"Спасибо за заказ! Мы скоро свяжемся с вами. 💜"
    )

    # Clear cart for this user
    user_carts[user_id] = {}
    await message.answer(user_confirmation_text, reply_markup=main_menu)

    # Prepare notification for admin and couriers
    user_info = message.from_user
    user_mention = f"@{user_info.username}" if user_info.username else f"ID <a href='tg://user?id={user_id}'>{user_id}</a>"

    # Full notification for admin (with customer info)
    admin_notification_text = (
        f"🔔 <b>Новый заказ #{order_display_number}</b> от {user_mention}\n\n"
        f"<b>Состав заказа:</b>\n{order_details_text}\n\n"
        f"<b>Итого: {total_amount} сом</b>\n"
        f"<b>Адрес:</b> {address}\n"
        f"<b>Телефон:</b> <code>{phone}</code> (нажмите для копирования)\n"
        f"<b>Время:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    # Anonymous notification for couriers (without customer info)
    couriers_notification_text = (
        f"🔔 <b>Новый заказ #{order_display_number}</b>\n\n"
        f"<b>Состав заказа:</b>\n{order_details_text}\n\n"
        f"<b>Итого: {total_amount} сом</b>\n"
        f"<b>Адрес:</b> {address}\n"
        f"<b>Время:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    # Create status management buttons
    status_kb = InlineKeyboardBuilder()
    status_kb.button(text="🔄 Собрать заказ", callback_data=f"status_{order_display_number}_preparing")
    status_kb.button(text="🚗 Отдать курьеру", callback_data=f"status_{order_display_number}_on_the_way")
    status_kb.button(text="✅ Доставлен", callback_data=f"status_{order_display_number}_delivered")
    status_kb.adjust(1)

    try:
        # Send full info to admin
        await bot.send_message(ADMIN_ID, admin_notification_text, reply_markup=status_kb.as_markup())
        # Send anonymous version to couriers
        await bot.send_message(COURIERS_CHAT_ID, couriers_notification_text, reply_markup=status_kb.as_markup())
    except Exception as e:
        print(f"Error sending order notification: {e}")
        # Optionally notify admin that notification failed for couriers

    # Store the order
    user_orders.setdefault(user_id, []).append({
        "order_number": order_display_number,
        "status": OrderStatus.ACCEPTED,
        "details_for_user": user_confirmation_text,
        "details_for_admin": admin_notification_text,
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "last_reminder": None
    })


    await state.clear()

# --- Admin Commands ---
@dp.message(Command("active_orders"))
async def cmd_active_orders(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("Эта команда доступна только администратору.")
        return

    active_orders_texts = []
    for user_id, orders_list in user_orders.items():
        for order_data in orders_list:
            # Define "active" statuses
            if order_data["status"] in [OrderStatus.ACCEPTED, OrderStatus.PREPARING, OrderStatus.ON_THE_WAY]:
                # Use the detailed admin notification text
                active_orders_texts.append(order_data.get("details_for_admin", f"Заказ #{order_data['order_number']} - Статус: {order_data['status'].value}"))

    if not active_orders_texts:
        await message.answer("Нет активных заказов.", reply_markup=main_menu)
        return

    response_header = "<b>Активные заказы:</b>\n\n---\n\n"
    full_response = response_header + "\n\n---\n\n".join(active_orders_texts)

    # Telegram message length limit is 4096 characters. Split if necessary.
    if len(full_response) > 4096:
        await message.answer("Слишком много активных заказов для отображения в одном сообщении. Пожалуйста, проверьте логи или базу данных.")
        # Or implement pagination
    else:
        await message.answer(full_response, reply_markup=main_menu)

# --- General User Commands & Menu Handlers ---
@dp.callback_query(lambda c: c.data == "back_to_categories")
async def go_back_to_categories(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    active_users.add(user_id)

    kb = InlineKeyboardBuilder()
    kb.button(text="Фрукты", callback_data="category_fruits")
    kb.button(text="Овощи", callback_data="category_vegetables")
    kb.button(text="Напитки", callback_data="category_drinks")
    kb.button(text="Снеки", callback_data="category_snacks")
    kb.button(text="Молочка", callback_data="category_milks")
    kb.adjust(2,2,1)

    # Add search button in category menu
    kb.row(types.InlineKeyboardButton(text="🔍 Поиск", callback_data="search_menu"))

    await callback.message.edit_text("Выберите категорию:", reply_markup=kb.as_markup())
    await callback.answer()

@dp.message(Command("cart"))
async def cmd_cart(message: Message):
    user_id = message.from_user.id
    await show_cart_logic(message, user_id, edit_message=False)

@dp.message(Command("orders"))
async def cmd_orders(message: Message):
    user_id = message.from_user.id
    active_users.add(user_id)

    user_specific_orders = user_orders.get(user_id, [])
    if not user_specific_orders:
        await message.answer("У вас пока нет заказов.", reply_markup=main_menu)
        return

    response_parts = ["<b>Ваши заказы:</b>\n"]
    for order_data in reversed(user_specific_orders):
        # Using the text that was originally sent to the user for consistency
        order_text_for_user = order_data.get("details_for_user",
                                           f"📦 <b>Заказ #{order_data['order_number']}</b>\n"
                                           f"Статус: {order_data['status'].value}\n"
                                           f"Время: {datetime.fromisoformat(order_data['timestamp']).strftime('%Y-%m-%d %H:%M') if 'timestamp' in order_data else 'N/A'}")

        # Append current status if not already in details_for_user or if it changed
        if "Статус:" not in order_text_for_user or order_data['status'].value not in order_text_for_user :
             current_status_line = f"<b>Текущий статус: {order_data['status'].value}</b>"
             # Check if details_for_user already has a status line to replace or append
             lines = order_text_for_user.split('\n')
             status_line_exists = any("Статус:" in line for line in lines) # Simple check
             if not status_line_exists:
                 order_text_for_user += f"\n{current_status_line}"
             # More complex logic could replace an existing status line if needed

        response_parts.append(order_text_for_user + "\n\n---\n")

    full_response = "\n".join(response_parts)
    if len(full_response) > 4096:
        await message.answer("У вас слишком много заказов для отображения. Показаны последние.", reply_markup=main_menu)
        # Implement pagination or show only a few recent orders
    else:
        await message.answer(full_response, reply_markup=main_menu)

@dp.message(Command("help"))
async def cmd_help(message: Message):
    user_id = message.from_user.id
    active_users.add(user_id)
    help_text = """
<b>Доступные команды и функции:</b>
/start - Перезапустить бота и показать главное меню.
/cart - Показать вашу корзину.
/orders - Показать историю ваших заказов.
/search <code>&lt;запрос&gt;</code> - Поиск товаров (например: /search яблоко).
/help - Показать это сообщение.

<b>Кнопки в меню:</b>
<b>📂 Каталог</b> - Просмотр категорий товаров.
<b>🛍 Корзина</b> - Ваша текущая корзина.
<b>📦 Мои заказы</b> - История ваших заказов.
<b>📢 Новости</b> - Последние новости магазина (пока не реализовано).
<b>⭐️ Оставить отзыв</b> - Оценить сервис и оставить отзыв.
<b>❓ Помощь</b> - Контактная информация и поддержка.
"""
    await message.answer(help_text, reply_markup=main_menu)

# Search history and cache
user_search_history = {}
search_cache = {}
popular_searches = ["яблоко", "молоко", "хлеб", "картошка", "банан"]

def calculate_similarity(word1, word2):
    """Simple similarity calculation for fuzzy search"""
    word1, word2 = word1.lower(), word2.lower()
    if word1 == word2:
        return 1.0

    # Check if one word contains the other
    if word1 in word2 or word2 in word1:
        return 0.8

    # Check character overlap
    common_chars = set(word1) & set(word2)
    total_chars = set(word1) | set(word2)
    if total_chars:
        similarity = len(common_chars) / len(total_chars)
        # Boost similarity if words start with same characters
        if word1[0] == word2[0]:
            similarity += 0.2
        return min(similarity, 1.0)
    return 0.0

def find_similar_products(query):
    """Find products using fuzzy matching"""
    results = []
    query_lower = query.lower()

    # Synonyms mapping
    synonyms = {
        "помидор": "томат",
        "томат": "помидор", 
        "картошка": "картофель",
        "картофель": "картошка",
        "кола": "coca-cola",
        "пепси": "pepsi"
    }

    # Check synonyms
    search_terms = [query_lower]
    if query_lower in synonyms:
        search_terms.append(synonyms[query_lower])

    for category_key, subcategories_dict in products.items():
        category_name = category_names.get(category_key, category_key.replace('category_', '').capitalize())
        for subcategory_name, items_dict in subcategories_dict.items():
            for item_name, variants_dict in items_dict.items():
                item_lower = item_name.lower()

                # Search in item names first
                for term in search_terms:
                    if term in item_lower or item_lower in term:
                        # Add all variants of this item
                        for variant_name, variant_data in variants_dict.items():
                            price = variant_data["price"]
                            unit = variant_data["unit"]
                            full_name = f"{item_name} {variant_name}"
                            results.append((full_name, price, unit, category_key, subcategory_name, category_name, 1.0))
                        break
                else:
                    # Fuzzy matching on item names
                    for term in search_terms:
                        similarity = calculate_similarity(term, item_lower)
                        if similarity >= 0.6:  # Threshold for fuzzy match
                            # Add all variants of this item
                            for variant_name, variant_data in variants_dict.items():
                                price = variant_data["price"]
                                unit = variant_data["unit"]
                                full_name = f"{item_name} {variant_name}"
                                results.append((full_name, price, unit, category_key, subcategory_name, category_name, similarity))
                            break

                # Also search in variant names
                for variant_name, variant_data in variants_dict.items():
                    variant_lower = variant_name.lower()
                    full_name_lower = f"{item_lower} {variant_lower}"

                    for term in search_terms:
                        if term in variant_lower or term in full_name_lower:
                            price = variant_data["price"]
                            unit = variant_data["unit"]
                            full_name = f"{item_name} {variant_name}"
                            # Check if not already added
                            if not any(result[0] == full_name for result in results):
                                results.append((full_name, price, unit, category_key, subcategory_name, category_name, 0.9))

    # Sort by similarity (highest first)
    results.sort(key=lambda x: x[6], reverse=True)
    return results

@router.message(SearchState.waiting_for_query, F.text)
async def handle_search_input(message: Message, state: FSMContext):
    user_id = message.from_user.id
    active_users.add(user_id)
    search_query = message.text.strip()

    if not search_query:
        await message.reply("Пожалуйста, введите название товара для поиска.")
        return

    await search_products_logic(message, search_query)
    await state.clear()

@dp.message(Command("search"))
async def search_products(message: Message):
    user_id = message.from_user.id
    active_users.add(user_id)
    search_query = message.text.replace("/search", "").strip()

    if not search_query:
        await message.answer("Используйте: /search название товара")
        return

    await search_products_logic(message, search_query)

async def search_products_logic(message: Message, search_query: str):
    user_id = message.from_user.id
    search_query_lower = search_query.lower()

    # Check cache first
    cache_key = search_query_lower
    if cache_key in search_cache:
        results = search_cache[cache_key]
    else:
        # Perform search
        results = find_similar_products(search_query)
        # Cache results
        search_cache[cache_key] = results
        # Limit cache size
        if len(search_cache) > 100:
            search_cache.clear()

    # Update search history
    user_history = user_search_history.setdefault(user_id, [])
    if search_query not in user_history:
        user_history.append(search_query)
        # Keep only last 10 searches
        if len(user_history) > 10:
            user_history.pop(0)

    if results:
        await message.answer(f"🔍 <b>Результаты поиска для '{search_query}':</b>")

        # Show top 10 results
        for item_name, price, unit, category_key, subcategory_name, category_name, similarity in results[:10]:
            kb_search = InlineKeyboardBuilder()

            # Create short callback for search results  
            search_callback = f"search_add_{category_key.replace('category_', '')}_{hash(item_name) % 1000}"
            current_item_mapping[f"search_{hash(item_name) % 1000}"] = item_name
            kb_search.button(text="➕ В корзину", callback_data=search_callback)
            kb_search.button(text="🛒 Корзина", callback_data="cart")

            result_text = f"▪️ {item_name} — {price} сом/{unit}\n📁 {category_name} → {subcategory_name}"
            await message.answer(result_text, reply_markup=kb_search.as_markup())

        if len(results) > 10:
            await message.answer(f"... и еще {len(results) - 10} товаров")

    else:
        await message.answer(f"По запросу '{search_query}' ничего не найдено 😔")

        # Suggest browsing categories
        kb_cat = InlineKeyboardBuilder()
        kb_cat.button(text="📂 Посмотреть все категории", callback_data="back_to_categories")
        await message.answer("Посмотрите наш каталог:", reply_markup=kb_cat.as_markup())

# --- Text-based Menu Button Handlers ---
@dp.message(F.text == "📂 Каталог")
async def menu_catalog(message: Message):
    # await message.delete() # Deleting user message can sometimes be confusing
    user_id = message.from_user.id
    active_users.add(user_id)
    kb = InlineKeyboardBuilder()
    kb.button(text="Фрукты", callback_data="category_fruits")
    kb.button(text="Овощи", callback_data="category_vegetables")
    kb.button(text="Напитки", callback_data="category_drinks")
    kb.button(text="Снеки", callback_data="category_snacks")
    kb.button(text="Молочка", callback_data="category_milks")
    kb.adjust(2,2,1)

    # Add search button in category menu
    kb.row(types.InlineKeyboardButton(text="🔍 Поиск", callback_data="search_menu"))

    await message.answer("Выберите категорию:", reply_markup=kb.as_markup())

@dp.message(F.text == "🛍 Корзина")
async def menu_cart(message: Message):
    # await message.delete()
    await cmd_cart(message) # Re-use the /cart command logic

@dp.message(F.text == "📦 Мои заказы")
async def menu_orders(message: Message):
    # await message.delete()
    await cmd_orders(message) # Re-use the /orders command logic

@dp.message(F.text == "📢 Новости")
async def menu_news(message: Message):
    # await message.delete()
    user_id = message.from_user.id
    active_users.add(user_id)
    await message.answer("Раздел новостей пока в разработке. Следите за обновлениями! 📢", reply_markup=main_menu)

# --- Review FSM ---
class ReviewState(StatesGroup):
    waiting_for_rating = State()
    waiting_for_text = State()

# --- Courier Comment FSM ---
class CourierCommentState(StatesGroup):
    waiting_for_comment = State()

@dp.message(F.text == "⭐️ Оставить отзыв")
async def menu_reviews_start(message: Message, state: FSMContext):
    # await message.delete()
    user_id = message.from_user.id
    active_users.add(user_id)
    kb = InlineKeyboardBuilder()
    for i in range(1, 6): # 1 to 5 stars
        kb.button(text="⭐" * i, callback_data=f"rate_{i}")
    kb.adjust(3, 2) # Layout for stars
    kb.row(types.InlineKeyboardButton(text="⬅️ Отмена", callback_data="review_cancel"))
    await message.answer("Пожалуйста, оцените наш сервис от 1 до 5 звезд:", reply_markup=kb.as_markup())
    await state.set_state(ReviewState.waiting_for_rating)

@dp.callback_query(lambda c: c.data.startswith("rate_"), ReviewState.waiting_for_rating)
async def handle_rating_input(callback: types.CallbackQuery, state: FSMContext):
    try:
        rating = int(callback.data.split("_")[1])
        if not 1 <= rating <= 5:
            raise ValueError("Invalid rating value")
    except (ValueError, IndexError):
        await callback.answer("Некорректная оценка.", show_alert=True)
        return

    await state.update_data(rating=rating)
    await callback.message.edit_text(
        f"Вы поставили оценку: {'⭐' * rating}\nТеперь, пожалуйста, напишите ваш отзыв:",
        reply_markup=InlineKeyboardBuilder().button(text="⬅️ Отмена", callback_data="review_cancel").as_markup()
    )
    await state.set_state(ReviewState.waiting_for_text)
    await callback.answer()

@dp.message(ReviewState.waiting_for_text, F.text)
async def handle_review_text_input(message: Message, state: FSMContext):
    data = await state.get_data()
    rating = data.get("rating", "N/A")
    review_text = message.text
    delivery_order = data.get("delivery_order_number")



    user_info = message.from_user
    user_mention = f"@{user_info.username}" if user_info.username else f"ID <a href='tg://user?id={user_info.id}'>{user_info.id}</a>"

    if delivery_order:
        # Delivery review
        review_message_to_admin = (
            f"📊 <b>Отзыв о доставке от {user_mention}</b>\n"
            f"<b>Заказ:</b> #{delivery_order}\n"
            f"<b>Оценка:</b> {'⭐' * rating if isinstance(rating, int) else rating}\n"
            f"<b>Отзыв:</b>\n{review_text}"
        )
        thank_you_message = "Спасибо за отзыв о доставке! Мы ценим ваше мнение. 💜"
    else:
        # General review
        review_message_to_admin = (
            f"📝 <b>Новый отзыв от {user_mention}</b>\n"
            f"<b>Оценка:</b> {'⭐' * rating if isinstance(rating, int) else rating}\n"
            f"<b>Отзыв:</b>\n{review_text}"
        )
        thank_you_message = "Спасибо за ваш отзыв! Мы ценим ваше мнение. 💜"

    try:
        await bot.send_message(ADMIN_ID, review_message_to_admin)
    except Exception as e:
        print(f"Error sending review to admin: {e}")

    await message.answer(thank_you_message, reply_markup=main_menu)
    await state.clear()

@dp.callback_query(F.data == "review_cancel", ReviewState.waiting_for_rating)
@dp.callback_query(F.data == "review_cancel", ReviewState.waiting_for_text)
@dp.callback_query(F.data == "delivery_review_cancel", ReviewState.waiting_for_rating)
@dp.callback_query(F.data == "delivery_review_cancel", ReviewState.waiting_for_text)
async def review_cancel_process(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Оставление отзыва отменено.")
    await callback.answer("Отзыв отменен.")



async def show_category_by_key(callback: types.CallbackQuery, category_key: str):
    """Helper function to show category by key"""
    category_name_display = category_names.get(category_key, category_key.replace("category_", "").capitalize())
    items = products.get(category_key, {})

    if not items:
        await callback.message.edit_text(f"В категории '{category_name_display}' пока нет товаров.", 
                                       reply_markup=InlineKeyboardBuilder().button(text="⬅️ Назад к категориям", callback_data="back_to_categories").as_markup())
        return

    kb = InlineKeyboardBuilder()
    for item, item_data in items.items():
        price = item_data["price"]
        unit = item_data["unit"]
        kb.button(text=f"{item} - {price} сом/{unit}", callback_data=f"add_category_{category_key.replace('category_', '')}_{item}")

    # Calculate grid layout
    item_count = len(items)
    if item_count <= 4:
        kb.adjust(2)
    elif item_count <= 9:
        kb.adjust(3)
    elif item_count <= 16:
        kb.adjust(4)
    else:
        kb.adjust(3)

    kb.row(
        types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_categories"),
        types.InlineKeyboardButton(text="🛒 Корзина", callback_data="cart")
    )
    await callback.message.edit_text(f"<b>{category_name_display}</b>:", reply_markup=kb.as_markup())

@dp.message(F.text == "❓ Помощь")
async def menu_help_contact(message: Message):
    # await message.delete()
    user_id = message.from_user.id
    active_users.add(user_id)
    kb = InlineKeyboardBuilder()
    kb.button(
        text="💬 Написать в Telegram",
        url="https://t.me/DilovarAkhi" # Make sure this is the correct contact
    )
    # You can add more contact methods if available

    await message.answer(
        "<b>📞 Контакты поддержки ДУЧАРХА</b> 💜\n\n"
        "Если у вас возникли вопросы, предложения или проблемы, вы можете связаться с нами:\n"
        "• <b>Telegram:</b> @DilovarAkhi\n"
        "• <b>Телефон:</b> +992 971 84 48 84 (звонки/мессенджеры)\n\n" # Example number
        "Мы постараемся помочь вам как можно скорее!",
        reply_markup=kb.as_markup(),
        parse_mode=ParseMode.HTML
    )

active_users = set()

@dp.message(Command("promote"))
async def send_promotion(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("Эта команда доступна только администратору.")
        return

    promo_text = message.text.replace("/promote", "").strip()
    if not promo_text:
        await message.answer("Использование: /promote <текст акции>\nНапример: <code>/promote Скидка 20% на все фрукты!</code>")
        return

    if not active_users:
        await message.answer("Нет активных пользователей для рассылки.")
        return

    success_count = 0
    failed_count = 0
    # Create a copy for iteration in case the set changes (though unlikely here)
    users_to_message = list(active_users)

    await message.answer(f"Начинаю рассылку для {len(users_to_message)} пользователей...")

    for user_id in users_to_message:
        try:
            await bot.send_message(
                user_id,
                f"🎉 <b>Специальное предложение от ДУЧАРХА!</b> 🎉\n\n{promo_text}\n\nЖелаем приятных покупок!",
                # reply_markup=main_menu # Sending main_menu might be intrusive here.
                # Consider a specific inline button like "К каталогу"
                reply_markup=InlineKeyboardBuilder().button(text="🎁 Перейти к акциям", callback_data="category_fruits").as_markup() # Example
            )
            success_count += 1
        except Exception as e:
            print(f"Failed to send promo to {user_id}: {e}")
            failed_count += 1

        await asyncio.sleep(0.1) # Small delay to avoid hitting Telegram limits too hard

    await message.answer(f"📢 Рассылка завершена!\n✅ Успешно отправлено: {success_count}\n❌ Не удалось отправить: {failed_count}")

# --- Bot Startup ---
@dp.callback_query(lambda c: c.data.startswith("status_"))
async def handle_status_update(callback: types.CallbackQuery):
    try:
        parts = callback.data.split("_", 2)  # Split only on first 2 underscores
        if len(parts) < 3:
            raise ValueError("Invalid callback data format")

        _, order_number, new_status = parts
        courier_id = callback.from_user.id

        # Convert callback data status to enum name
        status_mapping = {
            "preparing": "PREPARING",
            "on_the_way": "ON_THE_WAY", 
            "delivered": "DELIVERED"
        }

        if new_status not in status_mapping:
            await callback.answer("Неверный статус заказа", show_alert=True)
            return

        new_status = status_mapping[new_status]

        if new_status not in [status.name for status in OrderStatus]:
            await callback.answer("Неверный статус заказа", show_alert=True)
            return

        # Check if order is already assigned to another courier
        assigned_courier = order_couriers.get(order_number)
        if assigned_courier and assigned_courier != courier_id and courier_id != ADMIN_ID:
            await callback.answer("Этот заказ уже взят другим курьером", show_alert=True)
            return

        # If taking order for delivery, assign courier
        if new_status == "ON_THE_WAY" and not assigned_courier:
            order_couriers[order_number] = courier_id
            courier_info = callback.from_user
            courier_mention = f"@{courier_info.username}" if courier_info.username else f"ID {courier_info.id}"

            # Notify admin about courier assignment
            await bot.send_message(
                ADMIN_ID,
                f"🚗 <b>Заказ #{order_number} взят курьером</b>\n"
                f"Курьер: {courier_mention}"
            )

        # Find the order and update its status
        found = False
        for user_id, orders_list in user_orders.items():
            for order in orders_list:
                if order["order_number"] == order_number:
                    old_status = order["status"]
                    order["status"] = OrderStatus[new_status]
                    found = True

                    # Enhanced notification with time estimates
                    status_messages = {
                        "PREPARING": {
                            "emoji": "🛒",
                            "message": "Ваш заказ собирается",
                            "estimate": "Примерное время сборки: 1-2 минуты"
                        },
                        "ON_THE_WAY": {
                            "emoji": "🚗", 
                            "message": "Ваш заказ в пути",
                            "estimate": "Примерное время доставки: 10-15 минут"
                        },
                        "DELIVERED": {
                            "message": "Ваш заказ доставлен",
                            "estimate": "Спасибо за заказ! Ждем вас снова! 💜"
                        }
                    }

                    status_info = status_messages.get(new_status, {})
                    emoji = status_info.get("emoji", None)  # Remove default bell emoji
                    message = status_info.get("message", OrderStatus[new_status].value)
                    estimate = status_info.get("estimate", "")

                    # Send main notification
                    notification = f"<b>Обновление статуса заказа #{order_number}</b>\n\n{message}\n{estimate}"

                    # Add quick action buttons for customer
                    customer_kb = InlineKeyboardBuilder()
                    if new_status == "ON_THE_WAY":
                        # Get assigned courier info for contact button
                        assigned_courier_id = order_couriers.get(order_number)
                        if assigned_courier_id:
                            try:
                                courier_chat = await bot.get_chat(assigned_courier_id)
                                if courier_chat.username:
                                    courier_url = f"https://t.me/{courier_chat.username}"
                                else:
                                    courier_url = f"tg://user?id={assigned_courier_id}"
                                customer_kb.button(text="📞 Связаться с курьером", url=courier_url)
                            except:
                                customer_kb.button(text="📞 Связаться с курьером", url="https://t.me/DilovarAkhi")
                        else:
                            customer_kb.button(text="📞 Связаться с курьером", url="https://t.me/DilovarAkhi")
                        customer_kb.button(text="💬 Комментарий для курьера", callback_data=f"comment_for_courier_{order_number}")
                    elif new_status == "DELIVERED":
                        customer_kb.button(text="⭐ Оценить доставку", callback_data=f"rate_delivery_{order_number}")
                        customer_kb.button(text="🔄 Повторить заказ", callback_data="repeat_order")

                    reply_markup = customer_kb.as_markup() if customer_kb.export() else None
                    await bot.send_message(user_id, notification, reply_markup=reply_markup)

                    # Send emoji as separate message only if it exists and not for delivered status
                    if emoji and new_status != "DELIVERED":
                        await bot.send_message(user_id, emoji)

                    # Update buttons in admin/courier messages
                    status_kb = InlineKeyboardBuilder()
                    remaining_statuses = []

                    # Show buttons based on current status and courier assignment
                    if new_status == "PREPARING":
                        remaining_statuses = ["on_the_way", "delivered"]
                    elif new_status == "ON_THE_WAY":
                        remaining_statuses = ["delivered"]

                    for status in remaining_statuses:
                        button_text = "🚗 Отдать курьеру" if status == "on_the_way" else "✅ Доставлен"
                        status_kb.button(text=button_text, callback_data=f"status_{order_number}_{status}")

                    courier_info_text = ""
                    if order_number in order_couriers:
                        try:
                            courier_chat = await bot.get_chat(order_couriers[order_number])
                            courier_name = f"@{courier_chat.username}" if courier_chat.username else f"ID {order_couriers[order_number]}"
                            courier_info_text = f"\n<b>Курьер:</b> {courier_name}"
                        except:
                            courier_info_text = f"\n<b>Курьер:</b> ID {order_couriers[order_number]}"

                    new_message_text = callback.message.text + f"\n\n<b>Текущий статус:</b> {OrderStatus[new_status].value}{courier_info_text}"

                    if remaining_statuses:
                        await callback.message.edit_text(new_message_text, reply_markup=status_kb.adjust(1).as_markup())
                    else:
                        await callback.message.edit_text(new_message_text)

                    break
            if found:
                break

        if not found:
            await callback.answer("Заказ не найден", show_alert=True)
            return

        await callback.answer("Статус заказа обновлен")

    except Exception as e:
        print(f"Error updating order status: {e}")
        await callback.answer("Произошла ошибка при обновлении статуса", show_alert=True)

# --- Customer Notification Handlers ---
@dp.callback_query(lambda c: c.data.startswith("comment_for_courier_"))
async def comment_for_courier(callback: types.CallbackQuery, state: FSMContext):
    order_number = callback.data.replace("comment_for_courier_", "")
    await state.update_data(comment_order_number=order_number)
    await callback.message.answer(
        f"Напишите комментарий для курьера по заказу #{order_number}:\n"
        "(например: \"Звоните в домофон\", \"Жду у подъезда\", \"Квартира на 3 этаже\" и т.д.)",
        reply_markup=InlineKeyboardBuilder().button(text="⬅️ Отмена", callback_data="cancel_comment").as_markup()
    )
    await state.set_state(CourierCommentState.waiting_for_comment)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("rate_delivery_"))
async def rate_delivery_quick(callback: types.CallbackQuery, state: FSMContext):
    order_number = callback.data.replace("rate_delivery_", "")
    await state.update_data(delivery_order_number=order_number)

    kb = InlineKeyboardBuilder()
    for i in range(1, 6):
        kb.button(text="⭐" * i, callback_data=f"delivery_rate_{order_number}_{i}")
    kb.adjust(3, 2)  # Same layout as main review: 3 on top, 2 on bottom
    kb.row(types.InlineKeyboardButton(text="⬅️ Отмена", callback_data="delivery_review_cancel"))

    await callback.message.answer(
        f"Пожалуйста, оцените качество доставки заказа #{order_number}:",
        reply_markup=kb.as_markup()
    )
    await state.set_state(ReviewState.waiting_for_rating)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("delivery_rate_"), ReviewState.waiting_for_rating)
async def process_delivery_rating(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    if len(parts) >= 4:
        order_number = "_".join(parts[2:-1])  # Handle order numbers with underscores
        rating = int(parts[-1])

        await state.update_data(rating=rating, delivery_order_number=order_number)
        await callback.message.edit_text(
            f"Вы поставили оценку: {'⭐' * rating}\nТеперь, пожалуйста, напишите ваш отзыв о доставке:",
            reply_markup=InlineKeyboardBuilder().button(text="⬅️ Отмена", callback_data="delivery_review_cancel").as_markup()
        )
        await state.set_state(ReviewState.waiting_for_text)
        await callback.answer()

@dp.callback_query(F.data == "repeat_order")
async def repeat_last_order(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_specific_orders = user_orders.get(user_id, [])

    if not user_specific_orders:
        await callback.message.answer("У вас пока нет заказов для повтора.")
        await callback.answer()
        return

    # Get last completed order
    last_order = user_specific_orders[-1]
    await callback.message.answer(
        "Функция повтора заказа в разработке. Пока вы можете оформить новый заказ через каталог.",
        reply_markup=InlineKeyboardBuilder().button(text="📂 К каталогу", callback_data="back_to_categories").as_markup()
    )
    await callback.answer()

@dp.message(CourierCommentState.waiting_for_comment, F.text)
async def process_courier_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    order_number = data.get("comment_order_number")
    comment = message.text

    if len(comment.strip()) < 3:
        await message.reply("Комментарий слишком короткий. Напишите подробнее или отмените.",
                           reply_markup=InlineKeyboardBuilder().button(text="⬅️ Отмена", callback_data="cancel_comment").as_markup())
        return

    user_info = message.from_user
    user_mention = f"@{user_info.username}" if user_info.username else f"ID {user_info.id}"

    # Full notification for admin (with customer info)
    admin_comment_notification = (
        f"💬 <b>Комментарий клиента для курьера</b>\n"
        f"<b>Заказ:</b> #{order_number}\n"
        f"<b>Клиент:</b> {user_mention}\n"
        f"<b>Комментарий:</b> {comment}"
    )

    # Anonymous notification for couriers (without customer info)
    courier_comment_notification = (
        f"💬 <b>Комментарий клиента для курьера</b>\n"
        f"<b>Заказ:</b> #{order_number}\n"
        f"<b>Комментарий:</b> {comment}"
    )

    try:
        # Send full info to admin
        await bot.send_message(ADMIN_ID, admin_comment_notification)

        # Send anonymous version to assigned courier if exists, otherwise to couriers chat
        assigned_courier = order_couriers.get(order_number)
        if assigned_courier:
            await bot.send_message(assigned_courier, courier_comment_notification)
        else:
            await bot.send_message(COURIERS_CHAT_ID, courier_comment_notification)

        await message.answer("✅ Ваш комментарий передан курьеру!", reply_markup=main_menu)
    except Exception as e:
        print(f"Error sending courier comment: {e}")
        await message.answer("Произошла ошибка при отправке комментария. Попробуйте позже.", reply_markup=main_menu)

    await state.clear()

@dp.callback_query(F.data == "cancel_comment", CourierCommentState.waiting_for_comment)
async def cancel_courier_comment(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Отправка комментария отменена.")
    await callback.answer("Комментарий отменен.")

# --- Order Reminder System ---
async def send_order_reminders():
    """Send reminders for orders that haven't been updated in a while"""
    current_time = datetime.now()

    for user_id, orders_list in user_orders.items():
        for order in orders_list:
            if order["status"] in [OrderStatus.ACCEPTED, OrderStatus.PREPARING]:
                order_time = datetime.fromisoformat(order["timestamp"])
                time_since_order = current_time - order_time

                # Send reminder if order is older than 30 minutes and no reminder sent yet
                if time_since_order > timedelta(minutes=30) and not order.get("last_reminder"):
                    try:
                        reminder_text = f"⏰ <b>Напоминание о заказе #{order['order_number']}</b>\n\n"

                        if order["status"] == OrderStatus.ACCEPTED:
                            reminder_text += "Ваш заказ принят и ожидает обработки. Мы скоро начнем его собирать!"
                        elif order["status"] == OrderStatus.PREPARING:
                            reminder_text += "Ваш заказ собирается. Спасибо за терпение!"

                        reminder_text += f"\n\nВремя с момента заказа: {int(time_since_order.total_seconds() // 60)} минут"

                        await bot.send_message(user_id, reminder_text)
                        order["last_reminder"] = current_time.isoformat()

                        # Notify admin about delayed order
                        await bot.send_message(
                            ADMIN_ID,
                            f"⚠️ <b>Заказ #{order['order_number']} требует внимания</b>\n"
                            f"Статус: {order['status'].value}\n"
                            f"Время с момента заказа: {int(time_since_order.total_seconds() // 60)} минут"
                        )

                    except Exception as e:
                        print(f"Failed to send reminder for order {order['order_number']}: {e}")

async def reminder_scheduler():
    """Background task to check for reminders every 10 minutes"""
    while True:
        try:
            await send_order_reminders()
        except Exception as e:
            print(f"Error in reminder scheduler: {e}")
        await asyncio.sleep(600)  # Check every 10 minutes

@dp.callback_query(F.data == "search_menu")
async def show_search_menu(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    active_users.add(user_id)

    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад к категориям", callback_data="back_to_categories")

    await callback.message.edit_text(
        "🔍 <b>Поиск товаров</b>\n\nВведите название товара:",
        reply_markup=kb.as_markup()
    )
    await state.set_state(SearchState.waiting_for_query)
    await callback.answer()



async def main():
    print("Bot is starting...")
    # Start reminder scheduler in background
    asyncio.create_task(reminder_scheduler())
    await dp.start_polling(bot)

if __name__ == "__main__":
    keep_alive()
    asyncio.run(main())