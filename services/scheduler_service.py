"""
Scheduler servisi - Avtomatik vazifalar
"""
import asyncio
import logging
import random
from datetime import datetime, timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database.db import Database
from database.repositories import (
    ChannelRepository, StatsRepository, PostRepository
)

logger = logging.getLogger(__name__)


class SchedulerService:
    def __init__(self, bot: Bot, db: Database, scheduler: AsyncIOScheduler):
        self.bot = bot
        self.db = db
        self.scheduler = scheduler
    
    async def scan_all_channels(self):
        """
        Har soatda barcha kanallarni scan qilish
        Obunachilar sonini va viewlarni bazaga yozish
        """
        logger.info("🔍 Kanallar scan qilinmoqda...")
        
        async with self.db.get_session() as session:
            ch_repo = ChannelRepository(session)
            channels = await ch_repo.get_all_channels()
        
        scanned = 0
        errors = 0
        
        for channel in channels:
            try:
                # Obunachilar soni
                member_count = await self.bot.get_chat_member_count(channel.channel_id)
                
                # So'nggi postlar statistikasi (viewlar)
                views_24h = await self._get_recent_views(channel.channel_id)
                reactions_24h = await self._get_recent_reactions(channel.channel_id)
                
                # Bazaga saqlash
                async with self.db.get_session() as session:
                    ch_repo = ChannelRepository(session)
                    stats_repo = StatsRepository(session)
                    
                    await ch_repo.update_channel_subscribers(channel.channel_id, member_count)
                    await stats_repo.save_stats(
                        channel_id=channel.channel_id,
                        subscribers=member_count,
                        views_24h=views_24h,
                        reactions_24h=reactions_24h
                    )
                
                scanned += 1
                
                # API limit - kanallar orasida kutish
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"❌ Kanal scan xatosi {channel.channel_id}: {e}")
                errors += 1
        
        logger.info(f"✅ Scan yakunlandi: {scanned} muvaffaqiyatli, {errors} xatolik")
    
    async def _get_recent_views(self, channel_id: int) -> int:
        """
        24 soatdagi viewlar soni
        Telegram Bot API orqali so'nggi xabarlar statistikasini olish
        
        Note: To'liq view statistikasi faqat channels.getFullChannel
        (Telethon/Pyrogram) orqali mumkin. Bot API da limitlar bor.
        """
        try:
            # Kanaldan so'nggi xabarni olish
            # Bu yerda Telethon integratsiyasi bo'lsa to'liq ishlaydi
            # Bot API uchun forward-dan olish mumkin
            return 0  # Placeholder - Telethon bilan to'ldirish kerak
        except Exception:
            return 0
    
    async def _get_recent_reactions(self, channel_id: int) -> int:
        """24 soatdagi reaksiyalar"""
        return 0  # Placeholder - Telethon bilan to'ldirish kerak
    
    async def check_scheduled_posts(self):
        """
        Har daqiqada rejalashtirilgan postlarni tekshirish
        va vaqti kelgan postlarni yuborish
        """
        async with self.db.get_session() as session:
            post_repo = PostRepository(session)
            pending = await post_repo.get_pending_posts()
        
        if not pending:
            return
        
        logger.info(f"📅 {len(pending)} ta rejalashtirilgan post topildi")
        
        for post in pending:
            await self._send_scheduled_post(post)
    
    async def _send_scheduled_post(self, post):
        """Rejalashtirilgan postni yuborish"""
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        
        # Inline tugmalar
        reply_markup = None
        if post.buttons:
            builder = InlineKeyboardBuilder()
            for btn in post.buttons:
                builder.button(text=btn["text"], url=btn.get("url", "#"))
            builder.adjust(1)
            reply_markup = builder.as_markup()
        
        # Qayerga yuborish?
        async with self.db.get_session() as session:
            ch_repo = ChannelRepository(session)
            
            if post.send_to_all:
                channels = await ch_repo.get_all_channels()
            elif post.channel_id:
                channel = await ch_repo.get_channel(post.channel_id)
                channels = [channel] if channel else []
            else:
                channels = []
        
        success = 0
        for channel in channels:
            try:
                if post.media_type == "photo":
                    await self.bot.send_photo(
                        channel.channel_id,
                        post.media_file_id,
                        caption=post.text,
                        reply_markup=reply_markup
                    )
                elif post.media_type == "video":
                    await self.bot.send_video(
                        channel.channel_id,
                        post.media_file_id,
                        caption=post.text,
                        reply_markup=reply_markup
                    )
                else:
                    await self.bot.send_message(
                        channel.channel_id,
                        post.text,
                        reply_markup=reply_markup
                    )
                
                success += 1
                
                # API limit
                await asyncio.sleep(post.broadcast_interval or 0.05)
                
            except Exception as e:
                logger.error(f"❌ Post yuborish xatosi {channel.channel_id}: {e}")
        
        # Postni yuborildi deb belgilash
        async with self.db.get_session() as session:
            post_repo = PostRepository(session)
            await post_repo.mark_as_sent(post.id)
        
        logger.info(f"✅ Rejalashtirilgan post yuborildi: {success} ta kanal")
    
    async def run_cross_promotion(self):
        """
        Kanallar orasida o'zaro reklama (Cross-Promotion)
        Har bir kanal boshqa kanallardan birini reklama qiladi
        """
        logger.info("🔄 Cross-promotion boshlandi...")
        
        async with self.db.get_session() as session:
            ch_repo = ChannelRepository(session)
            channels = await ch_repo.get_cross_promo_channels()
        
        if len(channels) < 2:
            logger.info("Cross-promotion uchun yetarli kanal yo'q")
            return
        
        sent_pairs = set()
        promo_count = 0
        
        for channel in channels:
            # Bu kanal uchun reklama qilinadigan kanal tanlash
            available = [
                ch for ch in channels
                if ch.channel_id != channel.channel_id
                and (channel.channel_id, ch.channel_id) not in sent_pairs
                and ch.channel_link  # Linki bo'lgan kanallar
            ]
            
            if not available:
                continue
            
            # Random tanlash
            promo_channel = random.choice(available)
            
            promo_text = (
                f"📢 <b>Tavsiya etamiz!</b>\n\n"
                f"👉 <a href='{promo_channel.channel_link}'>{promo_channel.channel_title}</a>\n\n"
                f"👥 {promo_channel.subscribers_count:,} ta obunachilar bilan kanalimiz "
                f"siz uchun foydali ma'lumotlar ulashadi!\n\n"
                f"🔗 Obuna bo'ling!"
            )
            
            try:
                msg = await self.bot.send_message(
                    channel.channel_id,
                    promo_text,
                    disable_web_page_preview=False
                )
                
                async with self.db.get_session() as session:
                    post_repo = PostRepository(session)
                    await post_repo.save_cross_promo_log(
                        from_id=channel.channel_id,
                        to_id=promo_channel.channel_id,
                        msg_id=msg.message_id
                    )
                
                sent_pairs.add((channel.channel_id, promo_channel.channel_id))
                promo_count += 1
                
                # API limit
                await asyncio.sleep(1.0)
                
            except Exception as e:
                logger.error(f"❌ Cross-promo xatosi: {e}")
        
        logger.info(f"✅ Cross-promotion yakunlandi: {promo_count} ta post yuborildi")
