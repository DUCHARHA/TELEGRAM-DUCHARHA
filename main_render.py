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
from enum import Enum
from aiogram.fsm.storage.memory import MemoryStorage
from datetime import datetime, timedelta

daily_order_counter = {}
order_number_to_user = {}

API_TOKEN = os.getenv("API_TOKEN", "7582557120:AAGJKYgjXIocys3aZyNaVQlp_k892ARKBz0")
ADMIN_ID = int(os.getenv("ADMIN_ID", "1648127193"))
COURIERS_CHAT_ID = int(os.getenv("COURIERS_CHAT_ID", "-1002297990202"))

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
```
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

# Здесь вставьте весь остальной код из main.py, но без импорта keep_alive и без вызова keep_alive()

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

# ... здесь должен быть весь остальной код из main.py ...

async def main():
    print("Bot is starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())