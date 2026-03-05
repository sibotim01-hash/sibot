"""
Reyting hisoblash servisi - Avtomatik kunlik/haftalik hisob-kitob
"""
import logging
from datetime import datetime
from typing import List

from aiogram import Bot

from database.db import Database
from database.repositories import ChannelRepository, StatsRepository, RatingRepository

logger = logging.getLogger(__name__)


class RatingService:
    def __init__(self, bot: Bot, db: Database):
        self.bot = bot
        self.db = db
        
        # Og'irlik koeffitsientlari
        self.WEIGHTS = {
            "subscribers": 0.40,
            "views_24h": 0.35,
            "reactions_24h": 0.25
        }
    
    def normalize(self, value: float, max_val: float) -> float:
        """Normalizatsiya: 0-100 oralig'iga keltirish"""
        if max_val == 0:
            return 0.0
        return min(100.0, (value / max_val) * 100)
    
    def calculate_er(self, subscribers: int, views: int, reactions: int) -> float:
        """Engagement Rate hisoblash"""
        if subscribers == 0:
            return 0.0
        return ((views + reactions) / subscribers) * 100
    
    async def calculate_daily_rating(self):
        """Kunlik reyting hisoblash"""
        logger.info("🏆 Kunlik reyting hisoblanmoqda...")
        
        async with self.db.get_session() as session:
            ch_repo = ChannelRepository(session)
            stats_repo = StatsRepository(session)
            rating_repo = RatingRepository(session)
            
            channels = await ch_repo.get_all_channels()
        
        if not channels:
            logger.warning("⚠️ Kanallar topilmadi")
            return
        
        # Har bir kanal uchun ma'lumot yig'ish
        channel_data = []
        
        for channel in channels:
            # Telegram dan so'nggi ma'lumotlar
            try:
                member_count = await self.bot.get_chat_member_count(channel.channel_id)
            except Exception:
                member_count = channel.subscribers_count
            
            # So'nggi statistika
            async with self.db.get_session() as session:
                stats_repo = StatsRepository(session)
                latest = await stats_repo.get_latest_stats(channel.channel_id)
            
            views_24h = latest.views_24h if latest else 0
            reactions_24h = latest.reactions_24h if latest else 0
            
            er = self.calculate_er(member_count, views_24h, reactions_24h)
            
            channel_data.append({
                "channel": channel,
                "subscribers": member_count,
                "views_24h": views_24h,
                "reactions_24h": reactions_24h,
                "er": er
            })
        
        # Normalizatsiya uchun maksimum qiymatlar
        max_subs = max((d["subscribers"] for d in channel_data), default=1)
        max_views = max((d["views_24h"] for d in channel_data), default=1)
        max_reactions = max((d["reactions_24h"] for d in channel_data), default=1)
        
        # Ball hisoblash
        scored = []
        for data in channel_data:
            norm_subs = self.normalize(data["subscribers"], max_subs)
            norm_views = self.normalize(data["views_24h"], max_views)
            norm_reactions = self.normalize(data["reactions_24h"], max_reactions)
            
            score = (
                norm_subs * self.WEIGHTS["subscribers"] +
                norm_views * self.WEIGHTS["views_24h"] +
                norm_reactions * self.WEIGHTS["reactions_24h"]
            )
            
            scored.append({**data, "score": round(score, 2)})
        
        # Tartiblash (yuqoridan pastga)
        scored.sort(key=lambda x: x["score"], reverse=True)
        
        # Bazaga saqlash
        for rank, data in enumerate(scored, 1):
            async with self.db.get_session() as session:
                rating_repo = RatingRepository(session)
                await rating_repo.save_rating(
                    channel_id=data["channel"].channel_id,
                    score=data["score"],
                    rank=rank,
                    subscribers=data["subscribers"],
                    views_24h=data["views_24h"],
                    reactions_24h=data["reactions_24h"],
                    er=round(data["er"], 2),
                    period="daily"
                )
            
            # Obunachilar ham yangilansin
            async with self.db.get_session() as session:
                ch_repo = ChannelRepository(session)
                await ch_repo.update_channel_subscribers(
                    data["channel"].channel_id,
                    data["subscribers"]
                )
        
        logger.info(f"✅ Kunlik reyting hisoblandi: {len(scored)} kanal")
    
    async def calculate_weekly_rating(self):
        """Haftalik reyting - oxirgi 7 kunning o'rtachasi"""
        logger.info("📆 Haftalik reyting hisoblanmoqda...")
        
        async with self.db.get_session() as session:
            ch_repo = ChannelRepository(session)
            channels = await ch_repo.get_all_channels()
        
        channel_data = []
        
        for channel in channels:
            async with self.db.get_session() as session:
                stats_repo = StatsRepository(session)
                stats_7d = await stats_repo.get_channel_stats(channel.channel_id, 7)
            
            if not stats_7d:
                avg_views = 0
                avg_reactions = 0
            else:
                avg_views = sum(s.views_24h for s in stats_7d) / len(stats_7d)
                avg_reactions = sum(s.reactions_24h for s in stats_7d) / len(stats_7d)
            
            subs = channel.subscribers_count
            er = self.calculate_er(subs, int(avg_views), int(avg_reactions))
            
            channel_data.append({
                "channel": channel,
                "subscribers": subs,
                "views_24h": int(avg_views),
                "reactions_24h": int(avg_reactions),
                "er": er
            })
        
        # Normalizatsiya
        max_subs = max((d["subscribers"] for d in channel_data), default=1)
        max_views = max((d["views_24h"] for d in channel_data), default=1)
        max_reactions = max((d["reactions_24h"] for d in channel_data), default=1)
        
        scored = []
        for data in channel_data:
            score = (
                self.normalize(data["subscribers"], max_subs) * self.WEIGHTS["subscribers"] +
                self.normalize(data["views_24h"], max_views) * self.WEIGHTS["views_24h"] +
                self.normalize(data["reactions_24h"], max_reactions) * self.WEIGHTS["reactions_24h"]
            )
            scored.append({**data, "score": round(score, 2)})
        
        scored.sort(key=lambda x: x["score"], reverse=True)
        
        for rank, data in enumerate(scored, 1):
            async with self.db.get_session() as session:
                rating_repo = RatingRepository(session)
                await rating_repo.save_rating(
                    channel_id=data["channel"].channel_id,
                    score=data["score"],
                    rank=rank,
                    subscribers=data["subscribers"],
                    views_24h=data["views_24h"],
                    reactions_24h=data["reactions_24h"],
                    er=round(data["er"], 2),
                    period="weekly"
                )
        
        logger.info(f"✅ Haftalik reyting hisoblandi: {len(scored)} kanal")
