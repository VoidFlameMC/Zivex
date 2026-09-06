import os

from dotenv import load_dotenv


# =========================================================
# Load Environment Variables
# =========================================================

load_dotenv()


# =========================================================
# Helper
# =========================================================

def get_env(name, default=""):
    """
    قراءة Environment Variable وتنظيفها.
    """

    return os.getenv(
        name,
        default,
    ).strip()


def get_port():
    """
    Railway يوفر PORT تلقائيًا.
    WEB_PORT يستخدم كخيار احتياطي.
    """

    value = (
        os.getenv("PORT")
        or os.getenv("WEB_PORT")
        or "8080"
    ).strip()

    try:
        port = int(value)

    except (
        TypeError,
        ValueError,
    ):
        port = 8080

    # منع المنافذ غير الصالحة
    if not 1 <= port <= 65535:
        port = 8080

    return port


# =========================================================
# Discord
# =========================================================

DISCORD_TOKEN = get_env(
    "DISCORD_TOKEN"
)

DISCORD_CLIENT_ID = get_env(
    "DISCORD_CLIENT_ID"
)

DISCORD_CLIENT_SECRET = get_env(
    "DISCORD_CLIENT_SECRET"
)


# =========================================================
# Flask / Security
# =========================================================

SESSION_SECRET = get_env(
    "SESSION_SECRET"
)


# =========================================================
# Database
# =========================================================

DATABASE_URL = get_env(
    "DATABASE_URL",
    "sqlite:///zivex.db",
)


# =========================================================
# Web Server
# =========================================================

WEB_HOST = get_env(
    "WEB_HOST",
    "0.0.0.0",
)

WEB_PORT = get_port()


# =========================================================
# Website URL
# =========================================================

WEB_URL = get_env(
    "WEB_URL",
    "http://localhost:8080",
).rstrip("/")


# =========================================================
# Zivex Settings
# =========================================================

BOT_NAME = "Zivex"

# Prefix للأوامر القديمة
PREFIX = "!"


# =========================================================
# Configuration Warnings
# =========================================================

if not DISCORD_TOKEN:
    print(
        "⚠️ DISCORD_TOKEN غير موجود في Environment Variables."
    )


if not DISCORD_CLIENT_ID:
    print(
        "⚠️ DISCORD_CLIENT_ID غير موجود في Environment Variables."
    )


if not DISCORD_CLIENT_SECRET:
    print(
        "⚠️ DISCORD_CLIENT_SECRET غير موجود في Environment Variables."
    )


if not SESSION_SECRET:
    print(
        "⚠️ SESSION_SECRET غير موجود في Environment Variables."
    )


# =========================================================
# Production Warning
# =========================================================

if (
    WEB_URL.startswith("http://")
    and not WEB_URL.startswith(
        "http://localhost"
    )
):
    print(
        "⚠️ WEB_URL يستخدم HTTP. "
        "في الإنتاج استخدم HTTPS."
    )
