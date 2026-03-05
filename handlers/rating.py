"""
Reyting tizimi handleri
"""
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from config import Config
from database.db import Database
from database.repositories import ChannelRepository, RatingRepository
from keyboards.keyboards import rating_keyboard, back_keyboard
from services.rating_service import RatingService

rating_router = Router()

MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


def is_admin(user_id: int, config: Config) -> bool:
    return user_id in config.ADMIN_IDS


@rating_router.message(F.text == "🏆 Reyting")
@rating_router.message(Command("rating"))
async def show_rating_menu(message: Message, config: Config):
    if not is_admin(message.from_user.id, config):
        return
    
    await message.answer(
        "🏆 <b>Reyting Tizimi</b>\n\n"
        "Kanallar faolligiga asosan reyting hisoblanadi:\n"
        "• Obunachilar soni (40%)\n"
        "• 24 soatdagi ko'rishlar (35%)\n"
        "• Reaksiyalar soni (25%)\n",
        reply_markup=rating_keyboard()
    )


@rating_router.callback_query(F.data == "rating_daily")
async def show_daily_rating(callback: CallbackQuery, config: Config, db: Database):
    if not is_admin(callback.from_user.id, config):
        await callback.answer("❌ Ruxsat yo'q")
        return
    
    await callback.answer("⏳ Reyting yuklanmoqda...")
    
    async with db.get_session() as session:
        rating_repo = RatingRepository(session)
        ch_repo = ChannelRepository(session)
        ratings = await rating_repo.get_latest_ratings("daily")
        
        # Kanal nomlarini olish
        channel_map = {}
        channels = await ch_repo.get_all_channels()
        for ch in channels:
            channel_map[ch.channel_id] = ch
    
    if not ratings:
        await callback.message.edit_text(
            "📊 Hali reyting hisoblanmagan.\n🔄 Yangilash tugmasini bosing.",
            reply_markup=rating_keyboard()
        )
        return
    
    text = "🏆 <b>KUNLIK REYTING</b>\n"
    text += "━━━━━━━━━━━━━━━━━━\n\n"
    
    for rating in ratings[:10]:
        channel = channel_map.get(rating.channel_id)
        if not channel:
            continue
        
        medal = MEDALS.get(rating.rank_position, f"{rating.rank_position}.")
        name = channel.channel_title[:25]
        
        text += (
            f"{medal} <b>{name}</b>\n"
            f"   👥 {rating.subscribers_count:,} | "
            f"👁 {rating.views_24h:,} | "
            f"❤️ {rating.reactions_24h:,}\n"
            f"   📊 ER: {rating.engagement_rate:.2f}% | "
            f"⭐ {rating.rating_score:.1f}\n\n"
        )
    
    text += f"━━━━━━━━━━━━━━━━━━\n"
    text += f"📢 Jami: {len(ratings)} ta kanal"
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="📤 Kanallarga Yuborish", callback_data="rating_publish_daily")
    builder.button(text="🔙 Orqaga", callback_data="rating_menu")
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())


@rating_router.callback_query(F.data == "rating_weekly")
async def show_weekly_rating(callback: CallbackQuery, config: Config, db: Database):
    if not is_admin(callback.from_user.id, config):
        await callback.answer("❌ Ruxsat yo'q")
        return
    
    await callback.answer("⏳ Haftalik reyting yuklanmoqda...")
    
    async with db.get_session() as session:
        rating_repo = RatingRepository(session)
        ch_repo = ChannelRepository(session)
        ratings = await rating_repo.get_latest_ratings("weekly")
        channels = await ch_repo.get_all_channels()
        channel_map = {ch.channel_id: ch for ch in channels}
    
    if not ratings:
        await callback.message.edit_text(
            "📊 Hali haftalik reyting hisoblanmagan.",
            reply_markup=rating_keyboard()
        )
        return
    
    text = "📆 <b>HAFTALIK REYTING</b>\n"
    text += "━━━━━━━━━━━━━━━━━━\n\n"
    
    for rating in ratings[:15]:
        channel = channel_map.get(rating.channel_id)
        if not channel:
            continue
        
        medal = MEDALS.get(rating.rank_position, f"{rating.rank_position}.")
        name = channel.channel_title[:25]
        
        text += f"{medal} <b>{name}</b> — ⭐{rating.rating_score:.1f}\n"
        text += f"   👥 {rating.subscribers_count:,} | 👁 {rating.views_24h:,}\n\n"
    
    await callback.message.edit_text(text, reply_markup=rating_keyboard())


@rating_router.callback_query(F.data == "rating_recalculate")
async def recalculate_rating(callback: CallbackQuery, config: Config,
                               db: Database, rating_service: RatingService, bot: Bot):
    if not is_admin(callback.from_user.id, config):
        await callback.answer("❌ Ruxsat yo'q")
        return
    
    await callback.answer("⏳ Reyting hisoblanmoqda...")
    await callback.message.edit_text("⏳ <b>Reyting hisoblanmoqda...</b>\n\nBirozdan so'ng tayyor bo'ladi.")
    
    try:
        await rating_service.calculate_daily_rating()
        await callback.message.edit_text(
            "✅ <b>Reyting muvaffaqiyatli yangilandi!</b>",
            reply_markup=rating_keyboard()
        )
    except Exception as e:
        await callback.message.edit_text(
            f"❌ Xatolik: {str(e)}",
            reply_markup=rating_keyboard()
        )


@rating_router.callback_query(F.data.in_(["rating_publish", "rating_publish_daily"]))
async def publish_rating(callback: CallbackQuery, config: Config, db: Database,
                          rating_service: RatingService, bot: Bot):
    if not is_admin(callback.from_user.id, config):
        await callback.answer("❌ Ruxsat yo'q")
        return
    
    await callback.answer("📤 Yuborilmoqda...")
    
    # Kanallarga reyting postini yuborish
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    async with db.get_session() as session:
        ch_repo = ChannelRepository(session)
        rating_repo = RatingRepository(session)
        channels = await ch_repo.get_all_channels()
        ratings = await rating_repo.get_latest_ratings("daily", 10)
        channel_map = {ch.channel_id: ch for ch in channels}
    
    if not ratings:
        await callback.answer("❌ Reyting ma'lumotlari yo'q!", show_alert=True)
        return
    
    # Reyting matni
    text = "🏆 <b>KANAL REYTINGI</b>\n"
    text += "━━━━━━━━━━━━━━━━━━\n\n"
    
    for rating in ratings[:5]:
        channel = channel_map.get(rating.channel_id)
        if not channel:
            continue
        medal = MEDALS.get(rating.rank_position, f"{rating.rank_position}.")
        name = channel.channel_title[:20]
        link = channel.channel_link or "#"
        text += f"{medal} <a href='{link}'>{name}</a>\n"
        text += f"   👥 {rating.subscribers_count:,} | ⭐ {rating.rating_score:.1f}\n\n"
    
    text += "━━━━━━━━━━━━━━━━━━\n"
    text += "📲 Obuna bo'ling!"
    
    success = 0
    for channel in channels[:5]:  # Demo uchun faqat 5 ta
        try:
            await bot.send_message(channel.channel_id, text, disable_web_page_preview=True)
            success += 1
        except Exception:
            pass
    
    await callback.message.edit_text(
        f"✅ Reyting {success} ta kanalga yuborildi!",
        reply_markup=rating_keyboard()
    )


@rating_router.callback_query(F.data == "rating_menu")
async def back_to_rating_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "🏆 <b>Reyting Tizimi</b>",
        reply_markup=rating_keyboard()
    )
    await callback.answer()
