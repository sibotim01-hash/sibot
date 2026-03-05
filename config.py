"""
Konfiguratsiya sozlamalari
"""
import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    # Bot sozlamalari
    BOT_TOKEN: str = field(default_factory=lambda: os.getenv("BOT_TOKEN", ""))
    
    # Admin ID lar (vergul bilan ajratilgan)
    ADMIN_IDS: List[int] = field(default_factory=lambda: [
        int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
    ])
    
    # Ma'lumotlar bazasi
    DATABASE_URL: str = field(default_factory=lambda: os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:password@localhost:5432/multichannel_bot"
    ))
    
    # Kanal soni limiti
    MAX_CHANNELS: int = 42
    
    # Telegram API limitlari uchun kutish vaqti (soniyada)
    BROADCAST_DELAY: float = 0.05   # Har bir kanal orasidagi interval
    
    # Timezone
    TIMEZONE: str = "Asia/Tashkent"
    
    # Cross-promotion intervali (soat)
    CROSS_PROMO_INTERVAL: int = 24
    
    # Reyting hisoblash uchun og'irlik koeffitsientlari
    RATING_WEIGHTS = {
        "subscribers": 0.4,    # Obunachilar soni
        "views_24h": 0.35,     # 24 soatdagi ko'rishlar
        "reactions_24h": 0.25  # Reaksiyalar soni
    }
