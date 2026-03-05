"""
Kanallar boshqaruvi handleri
"""
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import Config
from database.db import Database
from database.repositories import ChannelRepository
from keyboards.keyboards import (
    channels_keyboard, channel_actions_keyboard,
    confirm_keyboard, back_keyboard
)

channels_router = Router()


class AddChannelState(StatesGroup):
    waiting_for_channel = State()


def is_admin(user_id: int, config: Config) -> bool:
    return user_id in config.ADMIN_IDS


@channels_router.message(F.text == "📢 Kanallar")
@channels_router.message(Command("channels"))
async def show_channels(message: Message, config: Config, db: Database):
    if not is_admin(message.from_user.id, config):
        return
    
    async with db.get_session() as session:
        repo = ChannelRepository(session)
        channels = await repo.get_all_channels()
        count = len(channels)
    
    text = f"📢 <b>Kanallar Ro'yxati</b>\n\n"
    text += f"Jami: <b>{count}/{config.MAX_CHANNELS}</b> kanal\n\n"
    
    if not channels:
        text += "Hali kanal qo'shilmagan. ➕ Kanal Qo'shish tugmasini bosing."
    
    await message.answer(text, reply_markup=channels_keyboard(channels))


@channels_router.callback_query(F.data == "channels_list")
async def channels_list_callback(callback: CallbackQuery, config: Config, db: Database):
    if not is_admin(callback.from_user.id, config):
        await callback.answer("❌ Ruxsat yo'q")
        return
    
    async with db.get_session() as session:
        repo = ChannelRepository(session)
        channels = await repo.get_all_channels()
        count = len(channels)
    
    text = f"📢 <b>Kanallar Ro'yxati</b>\n\nJami: <b>{count}/42</b> kanal"
    await callback.message.edit_text(text, reply_markup=channels_keyboard(channels))
    await callback.answer()


@channels_router.callback_query(F.data == "add_channel")
async def add_channel_start(callback: CallbackQuery, config: Config, db: Database, state: FSMContext):
    if not is_admin(callback.from_user.id, config):
        await callback.answer("❌ Ruxsat yo'q")
        return
    
    async with db.get_session() as session:
        repo = ChannelRepository(session)
        count = await repo.count_channels()
    
    if count >= config.MAX_CHANNELS:
        await callback.answer(f"❌ Maksimal kanal soni ({config.MAX_CHANNELS}) ga yetdi!", show_alert=True)
        return
    
    await state.set_state(AddChannelState.waiting_for_channel)
    await callback.message.edit_text(
        "➕ <b>Kanal Qo'shish</b>\n\n"
        "Kanalni qo'shish uchun:\n"
        "1️⃣ Botni kanalga <b>Admin</b> qilib qo'shing\n"
        "2️⃣ Kanal ID yoki @username yuboring\n\n"
        "<i>Misol: -1001234567890 yoki @mykanalim</i>",
        reply_markup=back_keyboard("channels_list")
    )
    await callback.answer()


@channels_router.message(AddChannelState.waiting_for_channel)
async def process_add_channel(message: Message, state: FSMContext, bot: Bot,
                               config: Config, db: Database):
    if not is_admin(message.from_user.id, config):
        return
    
    channel_input = message.text.strip()
    
    # Channel ID yoki username
    try:
        if channel_input.startswith("-100") or channel_input.lstrip("-").isdigit():
            channel_id = int(channel_input)
        elif channel_input.startswith("@"):
            channel_id = channel_input
        elif "t.me/" in channel_input:
            username = channel_input.split("t.me/")[-1].strip("/")
            channel_id = f"@{username}"
        else:
            channel_id = f"@{channel_input}"
        
        # Telegram dan kanal ma'lumotlarini olish
        chat = await bot.get_chat(channel_id)
        
        # Bot admin ekanligini tekshirish
        try:
            bot_member = await bot.get_chat_member(chat.id, (await bot.get_me()).id)
            if bot_member.status not in ["administrator", "creator"]:
                await message.answer(
                    "❌ Bot kanalda admin emas!\n\n"
                    "Bot ni kanalga admin qilib qo'sing va qayta urinib ko'ring.",
                    reply_markup=back_keyboard("channels_list")
                )
                await state.clear()
                return
        except Exception:
            await message.answer("❌ Bot kanalda topilmadi yoki admin emas!")
            await state.clear()
            return
        
        # Bazada mavjudligini tekshirish
        async with db.get_session() as session:
            repo = ChannelRepository(session)
            existing = await repo.get_channel(chat.id)
            
            if existing and existing.is_active:
                await message.answer("⚠️ Bu kanal allaqachon qo'shilgan!")
                await state.clear()
                return
            
            # Kanalga obunachilar soni
            member_count = await bot.get_chat_member_count(chat.id)
            
            # Kanal qo'shish
            username = f"@{chat.username}" if chat.username else None
            link = chat.invite_link or (f"https://t.me/{chat.username}" if chat.username else None)
            
            await repo.add_channel(
                channel_id=chat.id,
                title=chat.title,
                username=username,
                link=link,
                added_by=message.from_user.id
            )
            await repo.update_channel_subscribers(chat.id, member_count)
            count = await repo.count_channels()
        
        await message.answer(
            f"✅ <b>Kanal muvaffaqiyatli qo'shildi!</b>\n\n"
            f"📢 Kanal: <b>{chat.title}</b>\n"
            f"🔗 Link: {link or 'Private'}\n"
            f"👥 Obunachilar: <b>{member_count:,}</b>\n\n"
            f"Jami kanallar: <b>{count}/42</b>",
            reply_markup=channels_keyboard([])
        )
    
    except Exception as e:
        await message.answer(
            f"❌ Xatolik yuz berdi:\n<code>{str(e)}</code>\n\n"
            "Kanal ID yoki username ni to'g'ri kiriting.",
            reply_markup=back_keyboard("channels_list")
        )
    
    await state.clear()


@channels_router.callback_query(F.data.startswith("channel_info:"))
async def channel_info(callback: CallbackQuery, config: Config, db: Database, bot: Bot):
    if not is_admin(callback.from_user.id, config):
        await callback.answer("❌ Ruxsat yo'q")
        return
    
    channel_id = int(callback.data.split(":")[1])
    
    async with db.get_session() as session:
        repo = ChannelRepository(session)
        channel = await repo.get_channel(channel_id)
    
    if not channel:
        await callback.answer("❌ Kanal topilmadi!")
        return
    
    try:
        member_count = await bot.get_chat_member_count(channel_id)
    except Exception:
        member_count = channel.subscribers_count
    
    status = "✅ Faol" if channel.is_active else "❌ Nofaol"
    promo = "✅ Yoqilgan" if channel.cross_promo_enabled else "❌ O'chirilgan"
    
    text = (
        f"📢 <b>{channel.channel_title}</b>\n\n"
        f"🆔 ID: <code>{channel.channel_id}</code>\n"
        f"🔗 Link: {channel.channel_link or 'Private'}\n"
        f"👥 Obunachilar: <b>{member_count:,}</b>\n"
        f"📊 Status: {status}\n"
        f"🔄 Cross-Promo: {promo}\n"
        f"📅 Qo'shilgan: {channel.added_at.strftime('%d.%m.%Y')}\n"
        f"🕐 So'nggi scan: {channel.last_scanned.strftime('%d.%m.%Y %H:%M') if channel.last_scanned else 'Hali yo\'q'}"
    )
    
    await callback.message.edit_text(text, reply_markup=channel_actions_keyboard(channel_id))
    await callback.answer()


@channels_router.callback_query(F.data.startswith("del_channel:"))
async def delete_channel_confirm(callback: CallbackQuery, config: Config, db: Database):
    if not is_admin(callback.from_user.id, config):
        await callback.answer("❌ Ruxsat yo'q")
        return
    
    channel_id = callback.data.split(":")[1]
    await callback.message.edit_text(
        "❓ Rostdan ham bu kanalni o'chirmoqchimisiz?\n"
        "Barcha statistika ham o'chib ketadi!",
        reply_markup=confirm_keyboard(f"del_ch_{channel_id}")
    )
    await callback.answer()


@channels_router.callback_query(F.data.startswith("confirm:del_ch_"))
async def delete_channel_execute(callback: CallbackQuery, config: Config, db: Database):
    if not is_admin(callback.from_user.id, config):
        await callback.answer("❌ Ruxsat yo'q")
        return
    
    channel_id = int(callback.data.split("del_ch_")[1])
    
    async with db.get_session() as session:
        repo = ChannelRepository(session)
        await repo.remove_channel(channel_id)
    
    await callback.message.edit_text("✅ Kanal o'chirildi.")
    await callback.answer()


@channels_router.callback_query(F.data.startswith("toggle_promo:"))
async def toggle_cross_promo(callback: CallbackQuery, config: Config, db: Database):
    if not is_admin(callback.from_user.id, config):
        await callback.answer("❌ Ruxsat yo'q")
        return
    
    channel_id = int(callback.data.split(":")[1])
    
    from sqlalchemy import update
    from database.db import Channel
    
    async with db.get_session() as session:
        repo = ChannelRepository(session)
        channel = await repo.get_channel(channel_id)
        if channel:
            new_status = not channel.cross_promo_enabled
            await session.execute(
                update(Channel)
                .where(Channel.channel_id == channel_id)
                .values(cross_promo_enabled=new_status)
            )
            await session.commit()
            status_text = "✅ Yoqildi" if new_status else "❌ O'chirildi"
            await callback.answer(f"Cross-Promo {status_text}!", show_alert=True)
