"""
Ma'lumotlar bazasi - SQLAlchemy async modellari
"""
from datetime import datetime
from sqlalchemy import (
    Column, BigInteger, String, Integer, Float, Boolean,
    DateTime, Text, ForeignKey, JSON
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Channel(Base):
    """Kanal modeli"""
    __tablename__ = "channels"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(BigInteger, unique=True, nullable=False)  # Telegram channel ID
    channel_username = Column(String(100), nullable=True)
    channel_title = Column(String(255), nullable=False)
    channel_link = Column(String(255), nullable=True)
    subscribers_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    added_by = Column(BigInteger, nullable=False)  # Admin user ID
    added_at = Column(DateTime, default=datetime.utcnow)
    last_scanned = Column(DateTime, nullable=True)
    
    # Cross-promotion
    cross_promo_enabled = Column(Boolean, default=True)
    
    # Relationships
    stats = relationship("ChannelStats", back_populates="channel", cascade="all, delete-orphan")
    posts = relationship("ScheduledPost", back_populates="channel", cascade="all, delete-orphan")
    ratings = relationship("ChannelRating", back_populates="channel", cascade="all, delete-orphan")


class ChannelStats(Base):
    """Kanal statistikasi (soatlik)"""
    __tablename__ = "channel_stats"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(BigInteger, ForeignKey("channels.channel_id"), nullable=False)
    subscribers_count = Column(Integer, default=0)
    views_24h = Column(Integer, default=0)
    reactions_24h = Column(Integer, default=0)
    posts_count_24h = Column(Integer, default=0)
    recorded_at = Column(DateTime, default=datetime.utcnow)
    
    channel = relationship("Channel", back_populates="stats")


class ChannelRating(Base):
    """Kunlik reyting"""
    __tablename__ = "channel_ratings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(BigInteger, ForeignKey("channels.channel_id"), nullable=False)
    rating_score = Column(Float, default=0.0)
    rank_position = Column(Integer, default=0)
    subscribers_count = Column(Integer, default=0)
    views_24h = Column(Integer, default=0)
    reactions_24h = Column(Integer, default=0)
    engagement_rate = Column(Float, default=0.0)
    calculated_at = Column(DateTime, default=datetime.utcnow)
    period = Column(String(20), default="daily")  # daily / weekly
    
    channel = relationship("Channel", back_populates="ratings")


class ScheduledPost(Base):
    """Rejalashtirilgan postlar"""
    __tablename__ = "scheduled_posts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(BigInteger, ForeignKey("channels.channel_id"), nullable=True)  # NULL = barcha kanallar
    title = Column(String(255), nullable=True)
    text = Column(Text, nullable=True)
    media_type = Column(String(20), nullable=True)  # photo, video, document, None
    media_file_id = Column(String(255), nullable=True)
    buttons = Column(JSON, nullable=True)  # [{text: "...", url: "..."}]
    scheduled_at = Column(DateTime, nullable=False)
    is_sent = Column(Boolean, default=False)
    send_to_all = Column(Boolean, default=False)
    broadcast_interval = Column(Float, default=0.05)  # Kanallar orasidagi interval
    created_by = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)
    
    channel = relationship("Channel", back_populates="posts")


class BroadcastLog(Base):
    """Broadcast tarixi"""
    __tablename__ = "broadcast_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("scheduled_posts.id"), nullable=True)
    channel_id = Column(BigInteger, nullable=False)
    message_id = Column(Integer, nullable=True)
    status = Column(String(20), default="pending")  # pending, sent, failed
    error_message = Column(Text, nullable=True)
    sent_at = Column(DateTime, nullable=True)


class CrossPromoLog(Base):
    """Cross-promotion tarixi"""
    __tablename__ = "cross_promo_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    from_channel_id = Column(BigInteger, nullable=False)
    to_channel_id = Column(BigInteger, nullable=False)
    message_id = Column(Integer, nullable=True)
    sent_at = Column(DateTime, default=datetime.utcnow)


class Database:
    """Async database manager"""
    
    def __init__(self, database_url: str):
        if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
self.engine = create_async_engine(database_url, echo=False)
        self.session_factory = async_sessionmaker(
            self.engine, 
            class_=AsyncSession,
            expire_on_commit=False
        )
    
    async def init(self):
        """Jadvallarni yaratish"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def close(self):
        """Ulanishni yopish"""
        await self.engine.dispose()
    
    def get_session(self) -> AsyncSession:
        return self.session_factory()
