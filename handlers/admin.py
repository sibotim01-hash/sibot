"""
Admin panel handleri - Asosiy menyu va kirish nazorati
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from config import Config
from database.db import Database
from database.repositories import ChannelRepository
from keyboards.keyboards import main_menu_keyboard, back_keyboard

admin_router = Router()


def is_admin(user_id: int, config: Config) -> bool:
    return user_id in config.ADMIN_IDS


@admin_router.message(Command("start"))
async def cmd_start(message: Message, config: Config, db: Database):
    if not is_admin(message.from_user.id, config):
        await message.answer("❌ Sizda ruxsat yo'q.")
        return
    
    async with db.get_session() as session:
        repo = ChannelRepository(session)
        count = await repo.count_channels()
    
    text = (
        f"👋 <b>Xush kelibsiz, {message.from_user.first_name}!</b>\n\n"
        f"🤖 <b>Multi-Channel Manager Bot</b>\n\n"
        f"📢 Faol kanallar: <b>{count}/42</b>\n\n"
        f"Quyidagi bo'limlardan birini tanlang:"
    )
    await message.answer(text, reply_markup=main_menu_keyboard())


@admin_router.message(Command("help"))
async def cmd_help(message: Message, config: Config):
    if not is_admin(message.from_user.id, config):
        return
    
    help_text = (
        "📖 <b>Bot Buyruqlari:</b>\n\n"
        "/start - Asosiy menyu\n"
        "/channels - Kanallar ro'yxati\n"
        "/stats - Statistika\n"
        "/rating - Reyting\n"
        "/post - Post yaratish\n"
        "/scheduled - Rejalashtirilgan postlar\n\n"
        "<b>Funksiyalar:</b>\n"
        "• 42 ta kanal boshqaruvi\n"
        "• Smart broadcasting\n"
        "• Kunlik reyting tizimi\n"
        "• Cross-promotion\n"
        "• Rejalashtirilgan postlar\n"
        "• Batafsil statistika"
    )
    await message.answer(help_text)


@admin_router.message(F.text == "⚙️ Sozlamalar")
async def settings_menu(message: Message, config: Config):
    if not is_admin(message.from_user.id, config):
        return
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="🕐 Scan Intervali", callback_data="setting_scan")
    builder.button(text="⏱ Broadcast Delay", callback_data="setting_delay")
    builder.button(text="🔄 Cross-Promo ON/OFF", callback_data="setting_promo")
    builder.button(text="👥 Admin qo'shish", callback_data="setting_admin")
    builder.adjust(1)
    
    await message.answer(
        "⚙️ <b>Sozlamalar</b>\n\nQuyidagi parametrlarni o'zgartirish mumkin:",
        reply_markup=builder.as_markup()
    )


@admin_router.callback_query(F.data == "main_menu")
async def back_to_main(callback: CallbackQuery, config: Config, db: Database):
    if not is_admin(callback.from_user.id, config):
        await callback.answer("❌ Ruxsat yo'q")
        return
    
    async with db.get_session() as session:
        repo = ChannelRepository(session)
        count = await repo.count_channels()
    
    await callback.message.edit_text(
        f"🏠 <b>Asosiy Menyu</b>\n\n📢 Faol kanallar: <b>{count}/42</b>",
        reply_markup=None
    )
    await callback.message.answer("Menyuni tanlang:", reply_markup=main_menu_keyboard())
    await callback.answer()


@admin_router.callback_query(F.data == "cancel")
async def cancel_action(callback: CallbackQuery):
    await callback.message.edit_text("❌ Bekor qilindi.")
    await callback.answer()
