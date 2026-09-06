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
        # Maintenance State
        # =====================================================

        self.maintenance_mode = False

        # =====================================================
        # Global Slash Command Check
        # =====================================================

        self.tree.interaction_check = (
            self._maintenance_interaction_check
        )

    # =========================================================
    # Database - Maintenance
    # =========================================================

    async def setup_maintenance_database(self):

        async with db.connect() as database:

            await db.configure_connection(database)

            await database.execute(
                """
                CREATE TABLE IF NOT EXISTS zivex_global_settings (
                    setting TEXT PRIMARY KEY,
                    value TEXT NOT NULL DEFAULT ''
                )
                """
            )

            cursor = await database.execute(
                """
                SELECT value
                FROM zivex_global_settings
                WHERE setting = ?
                """,
                ("maintenance_mode",),
            )

            row = await cursor.fetchone()

            if row:

                self.maintenance_mode = (
                    str(row[0]) == "1"
                )

            else:

                await database.execute(
                    """
                    INSERT INTO zivex_global_settings
                    (setting, value)
                    VALUES (?, ?)
                    """,
                    (
                        "maintenance_mode",
                        "0",
                    ),
                )

                await database.commit()

        print(
            "🔧 Maintenance:",
            "ON" if self.maintenance_mode else "OFF",
        )

    async def set_maintenance(
        self,
        enabled: bool,
    ):

        self.maintenance_mode = bool(enabled)

        async with db.connect() as database:

            await db.configure_connection(database)

            await database.execute(
                """
                INSERT INTO zivex_global_settings
                (setting, value)
                VALUES (?, ?)
                ON CONFLICT(setting)
                DO UPDATE SET value = excluded.value
                """,
                (
                    "maintenance_mode",
                    "1" if enabled else "0",
                ),
            )

            await database.commit()

    # =========================================================
    # Prefix Command Protection
    # =========================================================

    async def bot_check(self, ctx):

        # -----------------------------------------------------
        # !صيانة لازم يظل شغال دائمًا
        # -----------------------------------------------------

        if ctx.command:

            command_name = str(
                ctx.command.name
            ).lower()

            if command_name == "صيانة":
                return True

        # -----------------------------------------------------
        # الوضع الطبيعي
        # -----------------------------------------------------

        if not self.maintenance_mode:
            return True

        # -----------------------------------------------------
        # وضع الصيانة
        # -----------------------------------------------------

        try:

            await ctx.send(
                "🔧 **البوت تحت الصيانة حاليًا.**\n"
                "⏳ جميع الأوامر متوقفة مؤقتًا.\n"
                "يرجى المحاولة لاحقًا."
            )

        except Exception:
            pass

        return False

    # =========================================================
    # Slash Command Protection
    # =========================================================

    async def _maintenance_interaction_check(
        self,
        interaction,
    ):

        # -----------------------------------------------------
        # إذا ليست Slash Command
        # لا نوقف الأزرار والمودالات
        # -----------------------------------------------------

        if (
            interaction.type
            != discord.InteractionType.application_command
        ):
            return True

        # -----------------------------------------------------
        # الوضع الطبيعي
        # -----------------------------------------------------

        if not self.maintenance_mode:
            return True

        # -----------------------------------------------------
        # وضع الصيانة
        # -----------------------------------------------------

        try:

            if interaction.response.is_done():

                await interaction.followup.send(
                    "🔧 **البوت تحت الصيانة حاليًا.**\n"
                    "⏳ جميع الأوامر متوقفة مؤقتًا.\n"
                    "يرجى المحاولة لاحقًا.",
                    ephemeral=True,
                )

            else:

                await interaction.response.send_message(
                    "🔧 **البوت تحت الصيانة حاليًا.**\n"
                    "⏳ جميع الأوامر متوقفة مؤقتًا.\n"
                    "يرجى المحاولة لاحقًا.",
                    ephemeral=True,
                )

        except Exception:
            pass

        return False

    # =========================================================
    # Setup
    # =========================================================

    async def setup_hook(self):

        print("🔧 Starting Zivex...")

        # =====================================================
        # Database
        # =====================================================

        await db.setup()

        # =====================================================
        # Maintenance Database
        # =====================================================

        try:

            await self.setup_maintenance_database()

        except Exception as error:

            print(
                f"❌ Maintenance database error: {error}"
            )

        # =====================================================
        # Load Cogs
        # =====================================================

        cogs = [
            "cogs.utility",
            "cogs.welcome",
            "cogs.levels",
            "cogs.moderation",
            "cogs.tickets",
            "cogs.applications",
            "cogs.owner",
        ]

        for cog in cogs:

            try:

                await self.load_extension(cog)

                print(
                    f"✅ Loaded: {cog}"
                )

            except Exception as error:

                print(
                    f"❌ Failed to load {cog}: {error}"
                )

        # =====================================================
        # Ensure Guilds
        # =====================================================

        for guild in self.guilds:

            try:

                await db.ensure_guild(
                    guild.id,
                    guild.name,
                    (
                        str(guild.icon.url)
                        if guild.icon
                        else None
                    ),
                )

            except Exception as error:

                print(
                    f"⚠️ Guild setup error "
                    f"({guild.id}): {error}"
                )

        # =====================================================
        # Sync Slash Commands
        # =====================================================

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
# Maintenance Command
# =========================================================

@bot.command(
    name="صيانة",
    help="تشغيل أو إيقاف وضع الصيانة."
)
async def maintenance(ctx):

    # =====================================================
    # Owner Only
    # =====================================================

    try:

        is_owner = await bot.is_owner(
            ctx.author
        )

    except Exception:

        is_owner = False

    if not is_owner:

        await ctx.send(
            "❌ هذا الأمر مخصص لصاحب البوت فقط."
        )

        return

    # =====================================================
    # Toggle
    # =====================================================

    new_state = not bot.maintenance_mode

    try:

        await bot.set_maintenance(
            new_state
        )

    except Exception as error:

        await ctx.send(
            "❌ حدث خطأ أثناء تغيير وضع الصيانة."
        )

        print(
            f"❌ Maintenance toggle error: {error}"
        )

        return

    # =====================================================
    # Maintenance ON
    # =====================================================

    if new_state:

        try:

            await bot.change_presence(
                status=discord.Status.dnd,
                activity=discord.Game(
                    "🔧 تحت الصيانة"
                ),
            )

        except Exception as error:

            print(
                f"⚠️ Maintenance presence error: {error}"
            )

        await ctx.send(
            "🔧 **تم تفعيل وضع الصيانة.**\n\n"
            "🚫 جميع أوامر البوت توقفت الآن.\n"
            "🚫 Prefix Commands متوقفة.\n"
            "🚫 Slash Commands متوقفة.\n\n"
            "✅ الأمر الوحيد الذي يعمل أثناء الصيانة هو:\n"
            "`!صيانة`\n\n"
            "يمكنك كتابة `!صيانة` مرة أخرى لإيقاف الصيانة."
        )

        print(
            "🔧 Maintenance mode ENABLED."
        )

        return

    # =====================================================
    # Maintenance OFF
    # =====================================================

    try:

        await bot.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{len(bot.guilds)} servers",
            ),
        )

    except Exception as error:

        print(
            f"⚠️ Normal presence error: {error}"
        )

    await ctx.send(
        "✅ **تم إيقاف وضع الصيانة.**\n\n"
        "🟢 جميع أوامر البوت عادت للعمل."
    )

    print(
        "🟢 Maintenance mode DISABLED."
    )


# =========================================================
# Bot Events
# =========================================================

@bot.event
async def on_ready():

    print(
        f""
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 Zivex Online\n"
        f"📌 Name: {bot.user}\n"
        f"🆔 ID: {bot.user.id}\n"
        f"🌐 Servers: {len(bot.guilds)}\n"
        f"🔧 Maintenance: "
        f"{'ON' if bot.maintenance_mode else 'OFF'}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    # =====================================================
    # Update Guild Information
    # =====================================================

    for guild in bot.guilds:

        try:

            await db.ensure_guild(
                guild.id,
                guild.name,
                (
                    str(guild.icon.url)
                    if guild.icon
                    else None
                ),
            )

        except Exception as error:

            print(
                f"⚠️ Failed to update guild "
                f"{guild.id}: {error}"
            )

    # =====================================================
    # Presence
    # =====================================================

    try:

        if bot.maintenance_mode:

            await bot.change_presence(
                status=discord.Status.dnd,
                activity=discord.Game(
                    "🔧 تحت الصيانة"
                ),
            )

        else:

            await bot.change_presence(
                status=discord.Status.online,
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name=f"{len(bot.guilds)} servers",
                ),
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
            (
                str(guild.icon.url)
                if guild.icon
                else None
            ),
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

    # =====================================================
    # Maintenance Check
    # =====================================================

    if isinstance(
        error,
        commands.CheckFailure,
    ):

        return

    # =====================================================
    # Command Not Found
    # =====================================================

    if isinstance(
        error,
        commands.CommandNotFound,
    ):

        return

    # =====================================================
    # Missing Permissions
    # =====================================================

    if isinstance(
        error,
        commands.MissingPermissions,
    ):

        await ctx.send(
            "❌ ما عندك الصلاحيات المطلوبة."
        )

        return

    # =====================================================
    # Missing Argument
    # =====================================================

    if isinstance(
        error,
        commands.MissingRequiredArgument,
    ):

        await ctx.send(
            "❌ ناقصك بعض المعلومات في الأمر."
        )

        return

    # =====================================================
    # Bad Argument
    # =====================================================

    if isinstance(
        error,
        commands.BadArgument,
    ):

        await ctx.send(
            "❌ البيانات التي أدخلتها غير صحيحة."
        )

        return

    # =====================================================
    # Other Errors
    # =====================================================

    print(
        f"❌ Command error: {error}"
    )


# =========================================================
# Flask Dashboard
# =========================================================

def start_web():

    try:

        # =====================================================
        # Railway PORT
        # =====================================================

        railway_port = os.getenv(
            "PORT"
        )

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

        # =====================================================
        # Create Flask using SAME bot instance
        # =====================================================

        app = create_app(bot)

        print(
            f"🌐 Zivex Dashboard starting "
            f"on {WEB_HOST}:{port}"
        )

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

    if not DISCORD_TOKEN:

        raise RuntimeError(
            "❌ DISCORD_TOKEN is missing "
            "from Railway Variables."
        )

    # =====================================================
    # Start Dashboard
    # =====================================================

    web_thread = threading.Thread(
        target=start_web,
        name="ZivexDashboard",
        daemon=True,
    )

    web_thread.start()

    # =====================================================
    # Start Discord Bot
    # =====================================================

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
