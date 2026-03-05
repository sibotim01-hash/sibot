"""
Kanal ma'lumotlari bilan ishlash uchun repository
"""
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import select, update, delete, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import Channel, ChannelStats, ChannelRating, ScheduledPost, BroadcastLog, CrossPromoLog


class ChannelRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_channel(self, channel_id: int, title: str, username: str = None,
                          link: str = None, added_by: int = None) -> Channel:
        channel = Channel(
            channel_id=channel_id,
            channel_title=title,
            channel_username=username,
            channel_link=link,
            added_by=added_by
        )
        self.session.add(channel)
        await self.session.commit()
        return channel

    async def get_channel(self, channel_id: int) -> Optional[Channel]:
        result = await self.session.execute(
            select(Channel).where(Channel.channel_id == channel_id)
        )
        return result.scalar_one_or_none()

    async def get_all_channels(self, active_only: bool = True) -> List[Channel]:
        query = select(Channel)
        if active_only:
            query = query.where(Channel.is_active == True)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def update_channel_subscribers(self, channel_id: int, count: int):
        await self.session.execute(
            update(Channel)
            .where(Channel.channel_id == channel_id)
            .values(subscribers_count=count, last_scanned=datetime.utcnow())
        )
        await self.session.commit()

    async def remove_channel(self, channel_id: int):
        await self.session.execute(
            update(Channel).where(Channel.channel_id == channel_id).values(is_active=False)
        )
        await self.session.commit()

    async def count_channels(self) -> int:
        result = await self.session.execute(
            select(func.count(Channel.id)).where(Channel.is_active == True)
        )
        return result.scalar()

    async def get_cross_promo_channels(self) -> List[Channel]:
        result = await self.session.execute(
            select(Channel).where(
                Channel.is_active == True,
                Channel.cross_promo_enabled == True
            )
        )
        return result.scalars().all()


class StatsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_stats(self, channel_id: int, subscribers: int,
                         views_24h: int = 0, reactions_24h: int = 0,
                         posts_count: int = 0):
        stat = ChannelStats(
            channel_id=channel_id,
            subscribers_count=subscribers,
            views_24h=views_24h,
            reactions_24h=reactions_24h,
            posts_count_24h=posts_count
        )
        self.session.add(stat)
        await self.session.commit()

    async def get_channel_stats(self, channel_id: int, days: int = 7) -> List[ChannelStats]:
        since = datetime.utcnow() - timedelta(days=days)
        result = await self.session.execute(
            select(ChannelStats)
            .where(
                ChannelStats.channel_id == channel_id,
                ChannelStats.recorded_at >= since
            )
            .order_by(desc(ChannelStats.recorded_at))
        )
        return result.scalars().all()

    async def get_latest_stats(self, channel_id: int) -> Optional[ChannelStats]:
        result = await self.session.execute(
            select(ChannelStats)
            .where(ChannelStats.channel_id == channel_id)
            .order_by(desc(ChannelStats.recorded_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_subscriber_growth(self, channel_id: int, days: int = 7) -> dict:
        """Obunachilar o'sishini hisoblash"""
        since = datetime.utcnow() - timedelta(days=days)
        result = await self.session.execute(
            select(ChannelStats)
            .where(
                ChannelStats.channel_id == channel_id,
                ChannelStats.recorded_at >= since
            )
            .order_by(ChannelStats.recorded_at)
        )
        stats = result.scalars().all()
        
        if len(stats) < 2:
            return {"growth": 0, "percentage": 0.0}
        
        first = stats[0].subscribers_count
        last = stats[-1].subscribers_count
        growth = last - first
        percentage = (growth / first * 100) if first > 0 else 0
        return {"growth": growth, "percentage": round(percentage, 2)}


class RatingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_rating(self, channel_id: int, score: float, rank: int,
                          subscribers: int, views_24h: int, reactions_24h: int,
                          er: float, period: str = "daily"):
        rating = ChannelRating(
            channel_id=channel_id,
            rating_score=score,
            rank_position=rank,
            subscribers_count=subscribers,
            views_24h=views_24h,
            reactions_24h=reactions_24h,
            engagement_rate=er,
            period=period
        )
        self.session.add(rating)
        await self.session.commit()

    async def get_latest_ratings(self, period: str = "daily", limit: int = 42) -> List[ChannelRating]:
        # Eng so'nggi kunning reytingini olish
        latest_date_result = await self.session.execute(
            select(func.max(ChannelRating.calculated_at)).where(ChannelRating.period == period)
        )
        latest_date = latest_date_result.scalar()
        
        if not latest_date:
            return []
        
        # O'sha kunning boshidan oxirigacha
        day_start = latest_date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        result = await self.session.execute(
            select(ChannelRating)
            .where(
                ChannelRating.period == period,
                ChannelRating.calculated_at >= day_start,
                ChannelRating.calculated_at < day_end
            )
            .order_by(ChannelRating.rank_position)
            .limit(limit)
        )
        return result.scalars().all()


class PostRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_post(self, channel_id: int = None, title: str = None,
                          text: str = None, media_type: str = None,
                          media_file_id: str = None, buttons: list = None,
                          scheduled_at: datetime = None, send_to_all: bool = False,
                          broadcast_interval: float = 0.05,
                          created_by: int = None) -> ScheduledPost:
        post = ScheduledPost(
            channel_id=channel_id,
            title=title,
            text=text,
            media_type=media_type,
            media_file_id=media_file_id,
            buttons=buttons or [],
            scheduled_at=scheduled_at or datetime.utcnow(),
            send_to_all=send_to_all,
            broadcast_interval=broadcast_interval,
            created_by=created_by
        )
        self.session.add(post)
        await self.session.commit()
        return post

    async def get_pending_posts(self) -> List[ScheduledPost]:
        """Yuborilishi kerak bo'lgan postlarni olish"""
        now = datetime.utcnow()
        result = await self.session.execute(
            select(ScheduledPost).where(
                ScheduledPost.is_sent == False,
                ScheduledPost.scheduled_at <= now
            )
        )
        return result.scalars().all()

    async def mark_as_sent(self, post_id: int):
        await self.session.execute(
            update(ScheduledPost)
            .where(ScheduledPost.id == post_id)
            .values(is_sent=True, sent_at=datetime.utcnow())
        )
        await self.session.commit()

    async def get_all_posts(self, limit: int = 20) -> List[ScheduledPost]:
        result = await self.session.execute(
            select(ScheduledPost)
            .order_by(desc(ScheduledPost.created_at))
            .limit(limit)
        )
        return result.scalars().all()

    async def save_broadcast_log(self, post_id: int, channel_id: int,
                                  message_id: int = None, status: str = "sent",
                                  error: str = None):
        log = BroadcastLog(
            post_id=post_id,
            channel_id=channel_id,
            message_id=message_id,
            status=status,
            error_message=error,
            sent_at=datetime.utcnow() if status == "sent" else None
        )
        self.session.add(log)
        await self.session.commit()

    async def save_cross_promo_log(self, from_id: int, to_id: int, msg_id: int):
        log = CrossPromoLog(from_channel_id=from_id, to_channel_id=to_id, message_id=msg_id)
        self.session.add(log)
        await self.session.commit()
