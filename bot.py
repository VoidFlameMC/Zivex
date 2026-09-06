import asyncio
import os
import threading

import discord
from discord.ext import commands

from config import DISCORD_TOKEN, PREFIX, WEB_HOST, WEB_PORT
from database import db
from web.app import create_app


# =========================================================
# Zivex Bot
# =========================================================

class Zivex(commands.Bot):

    def __init__(self):

        intents = discord.Intents.default()

        intents.members = True
        intents.message_content = True

        super().__init__(
            command_prefix=PREFIX,
            intents=intents,
            help_command=None,
        )

    # =====================================================
    # Setup
    # =====================================================

    async def setup_hook(self):

        print("🔧 Starting Zivex...")

        # -------------------------------------------------
        # Database
        # -------------------------------------------------

        try:
            await db.setup()
            print("✅ Database ready.")

        except Exception as error:
            print(f"❌ Database setup failed: {error}")
            raise

        # -------------------------------------------------
        # Load Cogs
        # -------------------------------------------------

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

                print(f"✅ Loaded: {cog}")

            except Exception as error:

                print(
                    f"❌ Failed to load {cog}: {error}"
                )

        # -------------------------------------------------
        # Ensure Guilds
        # -------------------------------------------------

        for guild in self.guilds:

            try:

                await db.ensure_guild(
                    guild.id,
                    guild.name,
                    str(guild.icon.url)
                    if guild.icon
                    else None,
                )

            except Exception as error:

                print(
                    f"⚠️ Guild setup error "
                    f"({guild.id}): {error}"
                )

        # -------------------------------------------------
        # Sync Slash Commands
        # -------------------------------------------------

        try:

            synced = await self.tree.sync()

            print(
                f"✅ Synced {len(synced)} slash commands."
            )

        except Exception as error:

            print(
                f"❌ Slash sync failed: {error}"
            )


# =========================================================
# Bot Instance
# =========================================================

bot = Zivex()


# =========================================================
# Ready Event
# =========================================================

@bot.event
async def on_ready():

    print(
        f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 Zivex Online
📌 Name: {bot.user}
🆔 ID: {bot.user.id}
🌐 Servers: {len(bot.guilds)}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    )

    # -----------------------------------------------------
    # Update Guild Information
    # -----------------------------------------------------

    for guild in bot.guilds:

        try:

            await db.ensure_guild(
                guild.id,
                guild.name,
                str(guild.icon.url)
                if guild.icon
                else None,
            )

        except Exception as error:

            print(
                f"⚠️ Failed to update guild "
                f"{guild.id}: {error}"
            )

    # -----------------------------------------------------
    # Presence
    # -----------------------------------------------------

    try:

        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{len(bot.guilds)} servers",
        )

        await bot.change_presence(
            activity=activity
        )

    except Exception as error:

        print(
            f"⚠️ Presence error: {error}"
        )


# =========================================================
# Guild Join
# =========================================================

@bot.event
async def on_guild_join(guild):

    print(
        f"➕ Joined server: "
        f"{guild.name} ({guild.id})"
    )

    try:

        await db.ensure_guild(
            guild.id,
            guild.name,
            str(guild.icon.url)
            if guild.icon
            else None,
        )

    except Exception as error:

        print(
            f"⚠️ Guild database error: {error}"
        )


# =========================================================
# Guild Remove
# =========================================================

@bot.event
async def on_guild_remove(guild):

    print(
        f"➖ Left server: "
        f"{guild.name} ({guild.id})"
    )


# =========================================================
# Command Errors
# =========================================================

@bot.event
async def on_command_error(
    ctx,
    error,
):

    # -----------------------------------------------------
    # Unknown Command
    # -----------------------------------------------------

    if isinstance(
        error,
        commands.CommandNotFound,
    ):
        return

    # -----------------------------------------------------
    # Missing Permissions
    # -----------------------------------------------------

    if isinstance(
        error,
        commands.MissingPermissions,
    ):

        await ctx.send(
            "❌ ما عندك الصلاحيات المطلوبة."
        )

        return

    # -----------------------------------------------------
    # Missing Argument
    # -----------------------------------------------------

    if isinstance(
        error,
        commands.MissingRequiredArgument,
    ):

        await ctx.send(
            "❌ ناقصك بعض المعلومات في الأمر."
        )

        return

    # -----------------------------------------------------
    # Bad Argument
    # -----------------------------------------------------

    if isinstance(
        error,
        commands.BadArgument,
    ):

        await ctx.send(
            "❌ البيانات التي أدخلتها غير صحيحة."
        )

        return

    # -----------------------------------------------------
    # Unexpected Error
    # -----------------------------------------------------

    print(
        f"❌ Command error: {error}"
    )


# =========================================================
# Flask Dashboard
# =========================================================

def start_web():

    try:

        # -------------------------------------------------
        # Railway PORT
        # -------------------------------------------------

        railway_port = os.getenv("PORT")

        try:

            port = int(
                railway_port
                if railway_port
                else WEB_PORT
            )

        except (
            TypeError,
            ValueError,
        ):

            port = int(WEB_PORT)

        # -------------------------------------------------
        # Create Flask App
        # -------------------------------------------------

        app = create_app(bot)

        print(
            f"🌐 Zivex Dashboard starting "
            f"on {WEB_HOST}:{port}"
        )

        # -------------------------------------------------
        # Start Flask
        # -------------------------------------------------

        app.run(
            host=WEB_HOST,
            port=port,
            debug=False,
            use_reloader=False,
        )

    except Exception as error:

        print(
            f"❌ Dashboard failed to start: {error}"
        )


# =========================================================
# Main
# =========================================================

async def main():

    # -----------------------------------------------------
    # Check Token
    # -----------------------------------------------------

    if not DISCORD_TOKEN:

        raise RuntimeError(
            "❌ DISCORD_TOKEN is missing "
            "from Railway Variables."
        )

    # -----------------------------------------------------
    # Start Dashboard
    # -----------------------------------------------------

    web_thread = threading.Thread(
        target=start_web,
        name="ZivexDashboard",
        daemon=True,
    )

    web_thread.start()

    # -----------------------------------------------------
    # Start Discord Bot
    # -----------------------------------------------------

    print(
        "🚀 Starting Zivex Bot..."
    )

    await bot.start(
        DISCORD_TOKEN
    )


# =========================================================
# Start
# =========================================================

if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        print(
            "🛑 Zivex stopped."
        )
