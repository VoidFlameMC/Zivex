import os
from dotenv import load_dotenv

load_dotenv()

# =========================================================
# Zivex Configuration
# =========================================================

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "").strip()

DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "").strip()

SESSION_SECRET = os.getenv("SESSION_SECRET", "").strip()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///zivex.db").strip()

# الموقع
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0").strip()

WEB_PORT = int(os.getenv("PORT", "8080"))

# رابط الموقع
WEB_URL = os.getenv(
    "WEB_URL",
    "http://localhost:8080"
).strip().rstrip("/")

# =========================================================
# Zivex Settings
# =========================================================

BOT_NAME = "Zivex"

# Prefix للأوامر القديمة
PREFIX = "cmd"

# =========================================================
# التحقق من الإعدادات الأساسية
# =========================================================

if not DISCORD_TOKEN:
    print("⚠️ DISCORD_TOKEN غير موجود في Environment Variables.")

if not DISCORD_CLIENT_ID:
    print("⚠️ DISCORD_CLIENT_ID غير موجود في Environment Variables.")

if not DISCORD_CLIENT_SECRET:
    print("⚠️ DISCORD_CLIENT_SECRET غير موجود في Environment Variables.")

if not SESSION_SECRET:
    print("⚠️ SESSION_SECRET غير موجود في Environment Variables.")
