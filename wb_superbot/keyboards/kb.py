"""
Клавиатуры для всех разделов бота.
"""

from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


# ─── ГЛАВНОЕ МЕНЮ ─────────────────────────────────────────────────────────────

def main_menu() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.button(text="⚡ Авто-бронь")
    kb.button(text="🔍 Поиск таймслотов")
    kb.button(text="📋 Список запросов")
    kb.button(text="🔄 Перераспределение")
    kb.button(text="📊 Статистика")
    kb.button(text="❓ Помощь")
    kb.adjust(2, 2, 2)
    return kb.as_markup(resize_keyboard=True)


# ─── ОТМЕНА ──────────────────────────────────────────────────────────────────

def cancel_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.button(text="❌ Отмена")
    return kb.as_markup(resize_keyboard=True)


# ─── ТИП ПОСТАВКИ ────────────────────────────────────────────────────────────

def supply_type_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📦 Короб", callback_data="stype:box")
    builder.button(text="🪵 Монопаллета", callback_data="stype:pallet")
    builder.button(text="🔒 Суперсейф", callback_data="stype:supersafe")
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(2, 1, 1)
    return builder.as_markup()


# ─── ПЕРИОД ──────────────────────────────────────────────────────────────────

def period_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Неделя (7 дней)", callback_data="period:week")
    builder.button(text="🗓 Месяц (30 дней)", callback_data="period:month")
    builder.button(text="✏️ Свои даты", callback_data="period:custom_dates")
    builder.button(text="📌 Свой период", callback_data="period:custom_range")
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


# ─── КОЭФФИЦИЕНТ ─────────────────────────────────────────────────────────────

def coef_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Только бесплатно (х0)", callback_data="coef:0")
    for c in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20]:
        builder.button(text=f"до х{c}", callback_data=f"coef:{c}")
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(1, 3, 3, 3, 2, 1)
    return builder.as_markup()


# ─── ЗАЩИТА ──────────────────────────────────────────────────────────────────

def protection_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🛡 Включить защиту (+72ч от сегодня)",
        callback_data="prot:1",
    )
    builder.button(
        text="⚡ Выключить (бронировать любые даты)",
        callback_data="prot:0",
    )
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(1, 1, 1)
    return builder.as_markup()


# ─── СПИСОК ЗАДАЧ ────────────────────────────────────────────────────────────

def task_actions_kb(task_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 Удалить заявку", callback_data=f"del_task:{task_id}")
    builder.button(text="◀️ Назад", callback_data="back_to_tasks")
    builder.adjust(1)
    return builder.as_markup()


def tasks_list_kb(tasks: list[dict], prefix: str = "task") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for t in tasks:
        status_icon = "✅" if t["status"] == "done" else ("📦" if t["status"] == "active" else "📁")
        label = (
            f"{status_icon} #{t['id']} | {t.get('warehouse_id','')} | "
            f"{t.get('date_from','')[:10]}–{t.get('date_to','')[:10]}"
        )
        builder.button(text=label[:60], callback_data=f"{prefix}:{t['id']}")
    builder.button(text="❌ Закрыть", callback_data="cancel")
    builder.adjust(1)
    return builder.as_markup()


# ─── ОПЛАТА ──────────────────────────────────────────────────────────────────

TARIFF_AUTOBRON = [
    (310, 1, "1 авто-бронь"),
    (1050, 5, "5 авто-броней"),
    (1890, 10, "10 авто-броней"),
    (5250, 30, "30 авто-броней"),
]

TARIFF_SUBSCRIPTION = 290  # 30 дней


def payment_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=f"⭐ Подписка 30 дней — {TARIFF_SUBSCRIPTION}₽",
        callback_data="pay:sub",
    )
    for price, count, label in TARIFF_AUTOBRON:
        builder.button(
            text=f"⚡ {label} — {price}₽",
            callback_data=f"pay:ab:{count}:{price}",
        )
    builder.button(text="📋 История оплат", callback_data="pay:history")
    builder.button(text="❌ Закрыть", callback_data="cancel")
    builder.adjust(1)
    return builder.as_markup()


def confirm_payment_kb(payment_db_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Оплатил, проверить", callback_data=f"check_pay:{payment_db_id}")
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(1)
    return builder.as_markup()
