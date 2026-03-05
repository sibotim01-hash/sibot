"""
Klaviaturalar - Inline va Reply tugmalar
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Asosiy menyu"""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📢 Kanallar"),
        KeyboardButton(text="✍️ Post Yaratish")
    )
    builder.row(
        KeyboardButton(text="📊 Statistika"),
        KeyboardButton(text="🏆 Reyting")
    )
    builder.row(
        KeyboardButton(text="⚙️ Sozlamalar"),
        KeyboardButton(text="📅 Rejalashtirilgan Postlar")
    )
    return builder.as_markup(resize_keyboard=True)


def channels_keyboard(channels: list) -> InlineKeyboardMarkup:
    """Kanallar ro'yxati"""
    builder = InlineKeyboardBuilder()
    for ch in channels:
        status = "✅" if ch.is_active else "❌"
        builder.button(
            text=f"{status} {ch.channel_title}",
            callback_data=f"channel_info:{ch.channel_id}"
        )
    builder.button(text="➕ Kanal Qo'shish", callback_data="add_channel")
    builder.button(text="🔙 Orqaga", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()


def channel_actions_keyboard(channel_id: int) -> InlineKeyboardMarkup:
    """Kanal amallari"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Statistika", callback_data=f"ch_stats:{channel_id}")
    builder.button(text="🏆 Reyting", callback_data=f"ch_rating:{channel_id}")
    builder.button(text="✍️ Post Yuborish", callback_data=f"post_to:{channel_id}")
    builder.button(text="🔄 Cross-Promo", callback_data=f"toggle_promo:{channel_id}")
    builder.button(text="❌ O'chirish", callback_data=f"del_channel:{channel_id}")
    builder.button(text="🔙 Orqaga", callback_data="channels_list")
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()


def post_constructor_keyboard() -> InlineKeyboardMarkup:
    """Post yaratish konstruktori"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Matn Qo'shish", callback_data="post_add_text")
    builder.button(text="🖼 Rasm Qo'shish", callback_data="post_add_photo")
    builder.button(text="🎬 Video Qo'shish", callback_data="post_add_video")
    builder.button(text="🔘 Tugma Qo'shish", callback_data="post_add_button")
    builder.button(text="👁 Ko'rish", callback_data="post_preview")
    builder.button(text="📤 Yuborish", callback_data="post_send_now")
    builder.button(text="📅 Rejalashtirish", callback_data="post_schedule")
    builder.button(text="📡 Barcha Kanallarga", callback_data="post_broadcast")
    builder.button(text="🗑 Tozalash", callback_data="post_clear")
    builder.adjust(2, 2, 1, 2, 1, 1)
    return builder.as_markup()


def broadcast_target_keyboard() -> InlineKeyboardMarkup:
    """Broadcast nishon"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📡 Barcha Kanallarga", callback_data="broadcast_all")
    builder.button(text="📋 Kanallarni Tanlash", callback_data="broadcast_select")
    builder.button(text="⏱ Interval Bilan", callback_data="broadcast_interval")
    builder.button(text="🔙 Orqaga", callback_data="post_constructor")
    builder.adjust(1)
    return builder.as_markup()


def stats_keyboard() -> InlineKeyboardMarkup:
    """Statistika menyusi"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Bugungi", callback_data="stats_today")
    builder.button(text="📆 Haftalik", callback_data="stats_week")
    builder.button(text="📊 Barcha Kanallar", callback_data="stats_all")
    builder.button(text="📈 O'sish Grafigi", callback_data="stats_growth")
    builder.button(text="🔙 Orqaga", callback_data="main_menu")
    builder.adjust(2, 1, 1, 1)
    return builder.as_markup()


def rating_keyboard() -> InlineKeyboardMarkup:
    """Reyting menyusi"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🏆 Kunlik TOP", callback_data="rating_daily")
    builder.button(text="📆 Haftalik TOP", callback_data="rating_weekly")
    builder.button(text="🔄 Yangilash", callback_data="rating_recalculate")
    builder.button(text="📤 Kanalga Yuborish", callback_data="rating_publish")
    builder.button(text="🔙 Orqaga", callback_data="main_menu")
    builder.adjust(2, 1, 1, 1)
    return builder.as_markup()


def confirm_keyboard(action: str) -> InlineKeyboardMarkup:
    """Tasdiqlash"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Ha", callback_data=f"confirm:{action}")
    builder.button(text="❌ Yo'q", callback_data="cancel")
    builder.adjust(2)
    return builder.as_markup()


def stats_period_keyboard(channel_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="24 soat", callback_data=f"stat_period:{channel_id}:1")
    builder.button(text="7 kun", callback_data=f"stat_period:{channel_id}:7")
    builder.button(text="30 kun", callback_data=f"stat_period:{channel_id}:30")
    builder.button(text="🔙 Orqaga", callback_data=f"channel_info:{channel_id}")
    builder.adjust(3, 1)
    return builder.as_markup()


def back_keyboard(callback: str = "main_menu") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Orqaga", callback_data=callback)
    return builder.as_markup()
