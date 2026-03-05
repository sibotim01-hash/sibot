"""
Post yaratish va yuborish handleri - Constructor pattern
"""
import asyncio
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import Config
from database.db import Database
from database.repositories import ChannelRepository, PostRepository
from keyboards.keyboards import (
    post_constructor_keyboard, broadcast_target_keyboard,
    back_keyboard, main_menu_keyboard
)

post_router = Router()


class PostState(StatesGroup):
    """Post yaratish holatlari"""
    constructing = State()
    waiting_text = State()
    waiting_photo = State()
    waiting_video = State()
    waiting_button = State()
    waiting_schedule_time = State()
    waiting_interval = State()
    selecting_channels = State()


class PostCreatorState(StatesGroup):
    """Post ma'lumotlarini saqlash"""
    pass


def is_admin(user_id: int, config: Config) -> bool:
    return user_id in config.ADMIN_IDS


def get_post_preview(post_data: dict) -> str:
    """Post preview matni"""
    parts = []
    if post_data.get("text"):
        parts.append(post_data["text"])
    if post_data.get("media_type"):
        parts.append(f"\n[{post_data['media_type'].upper()} biriktirilgan]")
    if post_data.get("buttons"):
        parts.append("\n🔘 Tugmalar:")
        for btn in post_data["buttons"]:
            parts.append(f"  • {btn['text']} → {btn.get('url', '')}")
    return "\n".join(parts) if parts else "(Bo'sh post)"


@post_router.message(F.text == "✍️ Post Yaratish")
@post_router.message(Command("post"))
async def start_post_creator(message: Message, config: Config, state: FSMContext):
    if not is_admin(message.from_user.id, config):
        return
    
    # Post ma'lumotlarini tozalash
    await state.update_data(post={
        "text": None,
        "media_type": None,
        "media_file_id": None,
        "buttons": []
    })
    await state.set_state(PostState.constructing)
    
    await message.answer(
        "✍️ <b>Post Konstruktori</b>\n\n"
        "Quyidagi elementlardan foydalanib post yarating:\n\n"
        "📝 Matn → Video → Rasm → Tugmalar\n\n"
        "Tayyor bo'lgach <b>Ko'rish</b> yoki <b>Yuborish</b>ni bosing.",
        reply_markup=post_constructor_keyboard()
    )


@post_router.callback_query(PostState.constructing, F.data == "post_add_text")
async def add_text(callback: CallbackQuery, state: FSMContext):
    await state.set_state(PostState.waiting_text)
    await callback.message.edit_text(
        "📝 <b>Matn kiriting:</b>\n\n"
        "HTML teglari qo'llab-quvvatlanadi:\n"
        "<code>&lt;b&gt;qalin&lt;/b&gt;</code>, <code>&lt;i&gt;kursiv&lt;/i&gt;</code>, "
        "<code>&lt;a href='url'&gt;link&lt;/a&gt;</code>",
        reply_markup=back_keyboard("post_constructor_back")
    )
    await callback.answer()


@post_router.message(PostState.waiting_text)
async def process_text(message: Message, state: FSMContext):
    data = await state.get_data()
    post = data.get("post", {})
    post["text"] = message.text or message.caption
    await state.update_data(post=post)
    await state.set_state(PostState.constructing)
    
    await message.answer(
        f"✅ Matn saqlandi!\n\n"
        f"<b>Ko'rinish:</b>\n{post['text'][:200]}{'...' if len(post['text']) > 200 else ''}",
        reply_markup=post_constructor_keyboard()
    )


@post_router.callback_query(PostState.constructing, F.data == "post_add_photo")
async def add_photo(callback: CallbackQuery, state: FSMContext):
    await state.set_state(PostState.waiting_photo)
    await callback.message.edit_text(
        "🖼 <b>Rasm yuboring:</b>",
        reply_markup=back_keyboard("post_constructor_back")
    )
    await callback.answer()


@post_router.message(PostState.waiting_photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    post = data.get("post", {})
    post["media_type"] = "photo"
    post["media_file_id"] = message.photo[-1].file_id
    if message.caption:
        post["text"] = message.caption
    await state.update_data(post=post)
    await state.set_state(PostState.constructing)
    await message.answer("✅ Rasm saqlandi!", reply_markup=post_constructor_keyboard())


@post_router.callback_query(PostState.constructing, F.data == "post_add_video")
async def add_video(callback: CallbackQuery, state: FSMContext):
    await state.set_state(PostState.waiting_video)
    await callback.message.edit_text(
        "🎬 <b>Video yuboring:</b>",
        reply_markup=back_keyboard("post_constructor_back")
    )
    await callback.answer()


@post_router.message(PostState.waiting_video, F.video)
async def process_video(message: Message, state: FSMContext):
    data = await state.get_data()
    post = data.get("post", {})
    post["media_type"] = "video"
    post["media_file_id"] = message.video.file_id
    if message.caption:
        post["text"] = message.caption
    await state.update_data(post=post)
    await state.set_state(PostState.constructing)
    await message.answer("✅ Video saqlandi!", reply_markup=post_constructor_keyboard())


@post_router.callback_query(PostState.constructing, F.data == "post_add_button")
async def add_button(callback: CallbackQuery, state: FSMContext):
    await state.set_state(PostState.waiting_button)
    await callback.message.edit_text(
        "🔘 <b>Tugma qo'shish</b>\n\n"
        "Quyidagi formatda yuboring:\n"
        "<code>Tugma Matni | https://link.com</code>\n\n"
        "<i>Misol: Kanalga o'tish | https://t.me/mykanalim</i>",
        reply_markup=back_keyboard("post_constructor_back")
    )
    await callback.answer()


@post_router.message(PostState.waiting_button)
async def process_button(message: Message, state: FSMContext):
    try:
        parts = message.text.split("|", 1)
        if len(parts) != 2:
            raise ValueError("Format noto'g'ri")
        
        btn_text = parts[0].strip()
        btn_url = parts[1].strip()
        
        data = await state.get_data()
        post = data.get("post", {})
        if "buttons" not in post:
            post["buttons"] = []
        
        if len(post["buttons"]) >= 5:
            await message.answer("⚠️ Maksimal 5 ta tugma qo'shish mumkin!")
        else:
            post["buttons"].append({"text": btn_text, "url": btn_url})
            await state.update_data(post=post)
            await message.answer(
                f"✅ Tugma qo'shildi: <b>{btn_text}</b>\n"
                f"Jami tugmalar: {len(post['buttons'])}",
                reply_markup=post_constructor_keyboard()
            )
        await state.set_state(PostState.constructing)
    except Exception:
        await message.answer("❌ Format noto'g'ri! Misol:\n<code>Matn | https://link.com</code>")


@post_router.callback_query(PostState.constructing, F.data == "post_preview")
async def preview_post(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    post = data.get("post", {})
    
    if not post.get("text") and not post.get("media_file_id"):
        await callback.answer("❌ Post bo'sh! Matn yoki media qo'shing.", show_alert=True)
        return
    
    # Inline tugmalar yaratish
    reply_markup = None
    if post.get("buttons"):
        builder = InlineKeyboardBuilder()
        for btn in post["buttons"]:
            builder.button(text=btn["text"], url=btn["url"])
        builder.adjust(1)
        reply_markup = builder.as_markup()
    
    await callback.answer("👁 Ko'rinish:")
    
    try:
        if post.get("media_type") == "photo":
            await callback.message.answer_photo(
                post["media_file_id"],
                caption=post.get("text"),
                reply_markup=reply_markup
            )
        elif post.get("media_type") == "video":
            await callback.message.answer_video(
                post["media_file_id"],
                caption=post.get("text"),
                reply_markup=reply_markup
            )
        else:
            await callback.message.answer(
                post["text"],
                reply_markup=reply_markup
            )
        
        await callback.message.answer("👆 Yuqoridagi post ko'rinishi", reply_markup=post_constructor_keyboard())
    except Exception as e:
        await callback.answer(f"❌ Xatolik: {str(e)}", show_alert=True)


@post_router.callback_query(PostState.constructing, F.data == "post_clear")
async def clear_post(callback: CallbackQuery, state: FSMContext):
    await state.update_data(post={"text": None, "media_type": None, "media_file_id": None, "buttons": []})
    await callback.answer("✅ Post tozalandi!")
    await callback.message.edit_text(
        "✍️ <b>Post Konstruktori</b>\n\n(Post tozalandi)",
        reply_markup=post_constructor_keyboard()
    )


@post_router.callback_query(PostState.constructing, F.data == "post_broadcast")
async def broadcast_options(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    post = data.get("post", {})
    
    if not post.get("text") and not post.get("media_file_id"):
        await callback.answer("❌ Post bo'sh!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📡 <b>Broadcast Sozlamalari</b>\n\nQayerga yuborishni tanlang:",
        reply_markup=broadcast_target_keyboard()
    )
    await callback.answer()


@post_router.callback_query(F.data == "broadcast_all")
async def broadcast_all_channels(callback: CallbackQuery, state: FSMContext,
                                  bot: Bot, config: Config, db: Database):
    if not is_admin(callback.from_user.id, config):
        await callback.answer("❌ Ruxsat yo'q")
        return
    
    data = await state.get_data()
    post = data.get("post", {})
    
    await callback.message.edit_text("📡 <b>Barcha kanallarga yuborilmoqda...</b>")
    
    async with db.get_session() as session:
        ch_repo = ChannelRepository(session)
        post_repo = PostRepository(session)
        channels = await ch_repo.get_all_channels()
        
        # Postni bazaga saqlash
        db_post = await post_repo.create_post(
            text=post.get("text"),
            media_type=post.get("media_type"),
            media_file_id=post.get("media_file_id"),
            buttons=post.get("buttons"),
            scheduled_at=datetime.utcnow(),
            send_to_all=True,
            created_by=callback.from_user.id
        )
    
    # Broadcast
    success = 0
    failed = 0
    
    # Inline tugmalar
    reply_markup = None
    if post.get("buttons"):
        builder = InlineKeyboardBuilder()
        for btn in post["buttons"]:
            builder.button(text=btn["text"], url=btn["url"])
        builder.adjust(1)
        reply_markup = builder.as_markup()
    
    for i, channel in enumerate(channels):
        try:
            if post.get("media_type") == "photo":
                msg = await bot.send_photo(
                    channel.channel_id,
                    post["media_file_id"],
                    caption=post.get("text"),
                    reply_markup=reply_markup
                )
            elif post.get("media_type") == "video":
                msg = await bot.send_video(
                    channel.channel_id,
                    post["media_file_id"],
                    caption=post.get("text"),
                    reply_markup=reply_markup
                )
            else:
                msg = await bot.send_message(
                    channel.channel_id,
                    post["text"],
                    reply_markup=reply_markup
                )
            
            async with db.get_session() as session:
                post_repo = PostRepository(session)
                await post_repo.save_broadcast_log(db_post.id, channel.channel_id, msg.message_id)
            
            success += 1
            
        except Exception as e:
            async with db.get_session() as session:
                post_repo = PostRepository(session)
                await post_repo.save_broadcast_log(db_post.id, channel.channel_id,
                                                    status="failed", error=str(e))
            failed += 1
        
        # Telegram API limitlari - interval kutish
        await asyncio.sleep(config.BROADCAST_DELAY)
        
        # Progress yangilash (har 10 ta)
        if (i + 1) % 10 == 0:
            try:
                await callback.message.edit_text(
                    f"📡 Yuborilmoqda... {i+1}/{len(channels)}\n"
                    f"✅ {success} | ❌ {failed}"
                )
            except Exception:
                pass
    
    # Postni yuborildi deb belgilash
    async with db.get_session() as session:
        post_repo = PostRepository(session)
        await post_repo.mark_as_sent(db_post.id)
    
    await callback.message.edit_text(
        f"✅ <b>Broadcast Yakunlandi!</b>\n\n"
        f"📊 Natijalar:\n"
        f"✅ Muvaffaqiyatli: <b>{success}</b>\n"
        f"❌ Xatolik: <b>{failed}</b>\n"
        f"📢 Jami kanallar: <b>{len(channels)}</b>",
        reply_markup=back_keyboard("main_menu")
    )
    
    # Post ma'lumotlarini tozalash
    await state.update_data(post={"text": None, "media_type": None, "media_file_id": None, "buttons": []})
    await callback.answer()


@post_router.callback_query(PostState.constructing, F.data == "post_schedule")
async def schedule_post(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    post = data.get("post", {})
    
    if not post.get("text") and not post.get("media_file_id"):
        await callback.answer("❌ Post bo'sh!", show_alert=True)
        return
    
    await state.set_state(PostState.waiting_schedule_time)
    await callback.message.edit_text(
        "📅 <b>Rejalashtirish</b>\n\n"
        "Vaqtni quyidagi formatda kiriting:\n"
        "<code>DD.MM.YYYY HH:MM</code>\n\n"
        "<i>Misol: 25.12.2024 18:00</i>",
        reply_markup=back_keyboard("post_constructor_back")
    )
    await callback.answer()


@post_router.message(PostState.waiting_schedule_time)
async def process_schedule_time(message: Message, state: FSMContext, db: Database, config: Config):
    if not is_admin(message.from_user.id, config):
        return
    
    try:
        scheduled_at = datetime.strptime(message.text.strip(), "%d.%m.%Y %H:%M")
        
        if scheduled_at <= datetime.utcnow():
            await message.answer("❌ Vaqt o'tmishda! Kelajak vaqtni kiriting.")
            return
        
        data = await state.get_data()
        post = data.get("post", {})
        
        async with db.get_session() as session:
            post_repo = PostRepository(session)
            await post_repo.create_post(
                text=post.get("text"),
                media_type=post.get("media_type"),
                media_file_id=post.get("media_file_id"),
                buttons=post.get("buttons"),
                scheduled_at=scheduled_at,
                send_to_all=True,
                created_by=message.from_user.id
            )
        
        await state.set_state(PostState.constructing)
        await state.update_data(post={"text": None, "media_type": None, "media_file_id": None, "buttons": []})
        
        await message.answer(
            f"✅ <b>Post rejalashtirildi!</b>\n\n"
            f"📅 Vaqt: <b>{scheduled_at.strftime('%d.%m.%Y %H:%M')}</b>\n"
            f"📡 Barcha kanallarga yuboriladi.",
            reply_markup=main_menu_keyboard()
        )
    
    except ValueError:
        await message.answer("❌ Noto'g'ri format! Misol: <code>25.12.2024 18:00</code>")


@post_router.message(F.text == "📅 Rejalashtirilgan Postlar")
async def show_scheduled(message: Message, config: Config, db: Database):
    if not is_admin(message.from_user.id, config):
        return
    
    async with db.get_session() as session:
        post_repo = PostRepository(session)
        posts = await post_repo.get_all_posts(20)
    
    pending = [p for p in posts if not p.is_sent]
    sent = [p for p in posts if p.is_sent]
    
    text = f"📅 <b>Rejalashtirilgan Postlar</b>\n\n"
    text += f"⏳ Kutilayotgan: <b>{len(pending)}</b>\n"
    text += f"✅ Yuborilgan: <b>{len(sent)}</b>\n\n"
    
    if pending:
        text += "<b>Kutilayotgan postlar:</b>\n"
        for p in pending[:5]:
            preview = (p.text or "")[:50]
            text += f"• {p.scheduled_at.strftime('%d.%m %H:%M')} - {preview}...\n"
    
    await message.answer(text, reply_markup=back_keyboard("main_menu"))


@post_router.callback_query(F.data == "post_constructor_back")
async def back_to_constructor(callback: CallbackQuery, state: FSMContext):
    await state.set_state(PostState.constructing)
    await callback.message.edit_text(
        "✍️ <b>Post Konstruktori</b>",
        reply_markup=post_constructor_keyboard()
    )
    await callback.answer()
