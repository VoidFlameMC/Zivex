import os
import asyncio
import logging
from threading import Thread

import discord
from discord.ext import commands
from flask import Flask

from database import db


# =========================================================
# Logging
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("Zivex")


# =========================================================
# Configuration
# =========================================================

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN environment variable is missing."
    )


PREFIX = "!"


# =========================================================
# Intents
# =========================================================

intents = discord.Intents.default()

intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True
intents.presences = True


# =========================================================
# Bot
# =========================================================

class ZivexBot(commands.Bot):

    def __init__(self):
        super().__init__(
            command_prefix=PREFIX,
            intents=intents,
            help_command=None,
            case_insensitive=True,
            strip_after_prefix=True,
        )

        self.ready_once = False
        self.web_server = None

    # =====================================================
    # Setup Hook
    # =====================================================

    async def setup_hook(self):
        cogs = [
            "cogs.utility",
            "cogs.welcome",
            "cogs.levels",
            "cogs.moderation",
            "cogs.tickets",
            "cogs.applications",
            "cogs.owner",
            "cogs.logs",
        ]

        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(
                    "Loaded cog: %s",
                    cog,
                )

            except commands.ExtensionAlreadyLoaded:
                logger.warning(
                    "Cog already loaded: %s",
                    cog,
                )

            except commands.ExtensionNotFound:
                logger.exception(
                    "Cog not found: %s",
                    cog,
                )

            except commands.ExtensionFailed:
                logger.exception(
                    "Cog failed to load: %s",
                    cog,
                )

            except Exception:
                logger.exception(
                    "Unexpected error loading cog: %s",
                    cog,
                )

        # -------------------------------------------------
        # Sync slash commands
        # -------------------------------------------------

        try:
            synced = await self.tree.sync()

            logger.info(
                "Synced %s application command(s).",
                len(synced),
            )

        except Exception:
            logger.exception(
                "Failed to sync application commands."
            )


# =========================================================
# Create Bot
# =========================================================

bot = ZivexBot()


# =========================================================
# Discord Events
# =========================================================

@bot.event
async def on_ready():

    if bot.ready_once:
        logger.info(
            "Reconnected as %s (%s).",
            bot.user,
            bot.user.id if bot.user else "unknown",
        )
        return

    bot.ready_once = True

    logger.info(
        "========================================"
    )

    logger.info(
        "Zivex is online."
    )

    logger.info(
        "Logged in as: %s",
        bot.user,
    )

    logger.info(
        "Bot ID: %s",
        bot.user.id if bot.user else "unknown",
    )

    logger.info(
        "Servers: %s",
        len(bot.guilds),
    )

    logger.info(
        "Users visible: %s",
        sum(
            guild.member_count or 0
            for guild in bot.guilds
        ),
    )

    logger.info(
        "========================================"
    )


@bot.event
async def on_command_error(
    ctx: commands.Context,
    error: commands.CommandError,
):

    # -----------------------------------------------------
    # Ignore command-not-found
    # -----------------------------------------------------

    if isinstance(
        error,
        commands.CommandNotFound,
    ):
        return

    # -----------------------------------------------------
    # Missing arguments
    # -----------------------------------------------------

    if isinstance(
        error,
        commands.MissingRequiredArgument,
    ):
        await ctx.send(
            "❌ ناقصك بعض البيانات المطلوبة للأمر."
        )
        return

    # -----------------------------------------------------
    # Bad argument
    # -----------------------------------------------------

    if isinstance(
        error,
        commands.BadArgument,
    ):
        await ctx.send(
            "❌ البيانات المدخلة غير صحيحة."
        )
        return

    # -----------------------------------------------------
    # Missing permissions
    # -----------------------------------------------------

    if isinstance(
        error,
        commands.MissingPermissions,
    ):
        await ctx.send(
            "❌ ما عندك الصلاحيات المطلوبة لهذا الأمر."
        )
        return

    # -----------------------------------------------------
    # Bot missing permissions
    # -----------------------------------------------------

    if isinstance(
        error,
        commands.BotMissingPermissions,
    ):
        await ctx.send(
            "❌ البوت ما عنده الصلاحيات المطلوبة."
        )
        return

    # -----------------------------------------------------
    # Not owner
    # -----------------------------------------------------

    if isinstance(
        error,
        commands.NotOwner,
    ):
        await ctx.send(
            "❌ هذا الأمر خاص بمالك البوت."
        )
        return

    # -----------------------------------------------------
    # Cooldown
    # -----------------------------------------------------

    if isinstance(
        error,
        commands.CommandOnCooldown,
    ):
        seconds = max(
            1,
            int(error.retry_after),
        )

        await ctx.send(
            f"⏳ انتظر {seconds} ثانية قبل استخدام الأمر مرة أخرى."
        )
        return

    # -----------------------------------------------------
    # Command disabled
    # -----------------------------------------------------

    if isinstance(
        error,
        commands.DisabledCommand,
    ):
        await ctx.send(
            "❌ هذا الأمر معطل حاليًا."
        )
        return

    # -----------------------------------------------------
    # Unwrap original error
    # -----------------------------------------------------

    original = getattr(
        error,
        "original",
        error,
    )

    logger.error(
        "Command error in %s: %s",
        getattr(
            ctx.command,
            "qualified_name",
            "unknown",
        ),
        original,
        exc_info=(
            type(original),
            original,
            original.__traceback__,
        ),
    )

    try:
        await ctx.send(
            "❌ حدث خطأ غير متوقع أثناء تنفيذ الأمر."
        )
    except Exception:
        pass


# =========================================================
# Global Discord Error Handler
# =========================================================

@bot.event
async def on_error(
    event_method: str,
    *args,
    **kwargs,
):
    logger.exception(
        "Unhandled Discord event error: %s",
        event_method,
    )


# =========================================================
# Flask Health Server
# =========================================================

app = Flask(__name__)


@app.get("/")
def home():
    return {
        "status": "online",
        "service": "Zivex Bot",
    }, 200


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "bot": (
            str(bot.user)
            if bot.user
            else None
        ),
        "guilds": len(bot.guilds),
    }, 200


def run_web_server():
    port = int(
        os.getenv(
            "PORT",
            "8080",
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False,
    )


# =========================================================
# Main
# =========================================================

async def main():

    web_thread = Thread(
        target=run_web_server,
        daemon=True,
    )

    web_thread.start()

    try:
        await bot.start(
            TOKEN,
            reconnect=True,
        )

    finally:
        try:
            await db.close()
        except Exception:
            logger.exception(
                "Failed to close database."
            )


if __name__ == "__main__":
    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        logger.info(
            "Zivex stopped manually."
        )

    except Exception:
        logger.exception(
            "Zivex stopped because of an unexpected error."
        )
