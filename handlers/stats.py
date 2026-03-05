"""
Statistika handleri
"""
from datetime import datetime, timedelta
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from config import Config
from database.db import Database
from database.repositories import ChannelRepository, StatsRepository
from keyboards.keyboards import stats_keyboard, stats_period_keyboard, back_keyboard

stats_router = Router()


def is_admin(user_id: int, config: Config) -> bool:
    return user_id in config.ADMIN_IDS


def format_number(n: int) -> str:
    """Sonni chiroyli formatlash"""
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    elif n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


@stats_router.message(F.text == "📊 Statistika")
@stats_router.message(Command("stats"))
async def show_stats_menu(message: Message, config: Config, db: Database, bot: Bot):
    if not is_admin(message.from_user.id, config):
        return
    
    async with db.get_session() as session:
        ch_repo = ChannelRepository(session)
        stats_repo = StatsRepository(session)
        channels = await ch_repo.get_all_channels()
    
    total_subs = sum(ch.subscribers_count for ch in channels)
    
    text = (
        f"📊 <b>Umumiy Statistika</b>\n\n"
        f"📢 Faol kanallar: <b>{len(channels)}</b>\n"
        f"👥 Jami obunachilar: <b>{format_number(total_subs)}</b>\n\n"
        f"Batafsil statistika uchun bo'limni tanlang:"
    )
    
    await message.answer(text, reply_markup=stats_keyboard())


@stats_router.callback_query(F.data == "stats_today")
async def stats_today(callback: CallbackQuery, config: Config, db: Database, bot: Bot):
    if not is_admin(callback.from_user.id, config):
        await callback.answer("❌ Ruxsat yo'q")
        return
    
    async with db.get_session() as session:
        ch_repo = ChannelRepository(session)
        stats_repo = StatsRepository(session)
        channels = await ch_repo.get_all_channels()
    
    text = "📅 <b>BUGUNGI STATISTIKA</b>\n"
    text += "━━━━━━━━━━━━━━━━━━\n\n"
    
    total_views = 0
    total_subs = 0
    
    for channel in channels[:10]:  # Top 10
        stats = await stats_repo.get_latest_stats(channel.channel_id) if hasattr(stats_repo, 'get_latest_stats') else None
        
        async with db.get_session() as s:
            sr = StatsRepository(s)
            stats = await sr.get_latest_stats(channel.channel_id)
        
        views = stats.views_24h if stats else 0
        subs = channel.subscribers_count
        total_views += views
        total_subs += subs
        
        name = channel.channel_title[:20]
        text += f"📢 <b>{name}</b>\n"
        text += f"   👥 {format_number(subs)} | 👁 {format_number(views)}\n\n"
    
    text += "━━━━━━━━━━━━━━━━━━\n"
    text += f"📊 Jami obunachilar: <b>{format_number(total_subs)}</b>\n"
    text += f"👁 Jami ko'rishlar: <b>{format_number(total_views)}</b>"
    
    await callback.message.edit_text(text, reply_markup=stats_keyboard())
    await callback.answer()


@stats_router.callback_query(F.data == "stats_all")
async def stats_all_channels(callback: CallbackQuery, config: Config, db: Database):
    if not is_admin(callback.from_user.id, config):
        await callback.answer("❌ Ruxsat yo'q")
        return
    
    async with db.get_session() as session:
        ch_repo = ChannelRepository(session)
        channels = await ch_repo.get_all_channels()
    
    text = "📊 <b>BARCHA KANALLAR STATISTIKASI</b>\n"
    text += "━━━━━━━━━━━━━━━━━━\n\n"
    
    for i, channel in enumerate(channels, 1):
        name = channel.channel_title[:22]
        subs = format_number(channel.subscribers_count)
        last_scan = channel.last_scanned.strftime("%H:%M") if channel.last_scanned else "—"
        
        text += f"{i}. <b>{name}</b>\n"
        text += f"   👥 {subs} | 🕐 {last_scan}\n"
    
    text += f"\n━━━━━━━━━━━━━━━━━━\n"
    text += f"Jami: <b>{len(channels)}</b> kanal"
    
    await callback.message.edit_text(text, reply_markup=stats_keyboard())
    await callback.answer()


@stats_router.callback_query(F.data == "stats_growth")
async def stats_growth(callback: CallbackQuery, config: Config, db: Database):
    if not is_admin(callback.from_user.id, config):
        await callback.answer("❌ Ruxsat yo'q")
        return
    
    async with db.get_session() as session:
        ch_repo = ChannelRepository(session)
        channels = await ch_repo.get_all_channels()
    
    text = "📈 <b>7 KUNLIK O'SISH</b>\n"
    text += "━━━━━━━━━━━━━━━━━━\n\n"
    
    for channel in channels[:15]:
        async with db.get_session() as session:
            stats_repo = StatsRepository(session)
            growth = await stats_repo.get_subscriber_growth(channel.channel_id, 7)
        
        name = channel.channel_title[:20]
        g = growth["growth"]
        pct = growth["percentage"]
        
        if g > 0:
            trend = f"📈 +{format_number(g)} (+{pct:.1f}%)"
        elif g < 0:
            trend = f"📉 {format_number(g)} ({pct:.1f}%)"
        else:
            trend = "➡️ O'zgarishsiz"
        
        text += f"• <b>{name}</b>\n  {trend}\n\n"
    
    await callback.message.edit_text(text, reply_markup=stats_keyboard())
    await callback.answer()


@stats_router.callback_query(F.data == "stats_week")
async def stats_week(callback: CallbackQuery, config: Config, db: Database):
    if not is_admin(callback.from_user.id, config):
        await callback.answer("❌ Ruxsat yo'q")
        return
    
    async with db.get_session() as session:
        ch_repo = ChannelRepository(session)
        channels = await ch_repo.get_all_channels()
    
    total_subs = sum(ch.subscribers_count for ch in channels)
    active = len(channels)
    
    text = (
        f"📆 <b>HAFTALIK HISOBOT</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"📢 Faol kanallar: <b>{active}</b>\n"
        f"👥 Jami obunachilar: <b>{format_number(total_subs)}</b>\n\n"
        f"<i>Batafsil ma'lumot uchun Kun bo'yicha statistikani ko'ring</i>"
    )
    
    await callback.message.edit_text(text, reply_markup=stats_keyboard())
    await callback.answer()


@stats_router.callback_query(F.data.startswith("ch_stats:"))
async def channel_stats(callback: CallbackQuery, config: Config, db: Database):
    if not is_admin(callback.from_user.id, config):
        await callback.answer("❌ Ruxsat yo'q")
        return
    
    channel_id = int(callback.data.split(":")[1])
    
    async with db.get_session() as session:
        ch_repo = ChannelRepository(session)
        stats_repo = StatsRepository(session)
        channel = await ch_repo.get_channel(channel_id)
        stats_7d = await stats_repo.get_channel_stats(channel_id, 7)
        growth = await stats_repo.get_subscriber_growth(channel_id, 7)
    
    if not channel:
        await callback.answer("❌ Kanal topilmadi!")
        return
    
    text = (
        f"📊 <b>{channel.channel_title}</b>\n\n"
        f"👥 Obunachilar: <b>{format_number(channel.subscribers_count)}</b>\n"
        f"📈 7 kunlik o'sish: <b>{'+' if growth['growth'] >= 0 else ''}{growth['growth']}</b> "
        f"({growth['percentage']:+.1f}%)\n\n"
        f"📅 So'nggi ma'lumotlar ({len(stats_7d)} yozuv):\n"
    )
    
    for stat in stats_7d[:5]:
        date = stat.recorded_at.strftime("%d.%m %H:%M")
        text += f"• {date}: 👥{format_number(stat.subscribers_count)} | 👁{format_number(stat.views_24h)}\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=stats_period_keyboard(channel_id)
    )
    await callback.answer()
