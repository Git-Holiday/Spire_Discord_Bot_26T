import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN", "")
GUILD_ID = int(os.getenv("GUILD_ID", 0))
RESERVATIONS_CHANNEL_ID = int(os.getenv("RESERVATIONS_CHANNEL_ID", 0))
TIMEZONE = os.getenv("TIMEZONE", "Europe/London")

# Time the daily reservation post goes up (24h)
DAILY_POST_HOUR = int(os.getenv("DAILY_POST_HOUR", 8))
DAILY_POST_MINUTE = int(os.getenv("DAILY_POST_MINUTE", 0))

# Time confirmation DMs are sent on the day of the reservation
CONFIRMATION_HOUR = int(os.getenv("CONFIRMATION_HOUR", 9))
CONFIRMATION_MINUTE = int(os.getenv("CONFIRMATION_MINUTE", 0))

# Club tables
TABLES = [
    {"id": 1, "name": "Table 1", "size": "8×4", "type": "Standard", "emoji": "🟫", "colour": 0x8B4513},
    {"id": 2, "name": "Table 2", "size": "8×4", "type": "Standard", "emoji": "🟫", "colour": 0x8B4513},
    {"id": 3, "name": "Table 3", "size": "8×4", "type": "Standard", "emoji": "🟫", "colour": 0x8B4513},
    {"id": 4, "name": "Table 4", "size": "6×4", "type": "Raised",   "emoji": "🟦", "colour": 0x4169E1},
    {"id": 5, "name": "Table 5", "size": "6×4", "type": "Raised",   "emoji": "🟦", "colour": 0x4169E1},
    {"id": 6, "name": "Table 6", "size": "6×4", "type": "Low",      "emoji": "🟩", "colour": 0x228B22},
    {"id": 7, "name": "Hobby Table", "size": "Small", "type": "Hobby", "emoji": "🎨", "colour": 0x9B59B6},
]

# Booking time slots (3–4 hours each)
SLOTS = [
    {"id": 0, "name": "Morning",   "time": "10:00–13:00", "emoji": "🌅"},
    {"id": 1, "name": "Afternoon", "time": "13:00–17:00", "emoji": "☀️"},
    {"id": 2, "name": "Evening",   "time": "17:00–21:00", "emoji": "🌆"},
]

TABLE_MAP = {t["id"]: t for t in TABLES}
SLOT_MAP  = {s["id"]: s for s in SLOTS}
