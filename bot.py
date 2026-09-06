import asyncio

import discord
from discord.ext import commands

from config import DISCORD_TOKEN, PREFIX
from database import db


# =========================================================
# Zivex Bot
# =========================================================

intents = discord.Intents.default()

# مهم للترحيب والليفلات
intents.members = True

# مهم لأوامر ! العربية ونظام الليفلات
intents.message_content = True


class Zivex(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=PREFIX,
            intents=intents,
            help_command=None
        )

    # =====================================================
    # تحميل الأنظمة
    # =====================================================

    async def setup_hook(self):

        # -------------------------------------------------
        # تشغيل قاعدة البيانات
        # -------------------------------------------------

        await db.setup()

        print("✅ Database initialized.")

        # -------------------------------------------------
        # جميع Cogs
        # -------------------------------------------------

        cog_files = [
            "cogs.utility",
            "cogs.welcome",
            "cogs.levels",
            "cogs.moderation",
            "cogs.tickets",
            "cogs.applications",
            "cogs.owner",
        ]

        for extension in cog_files:
            try:
                await self.load_extension(extension)

                print(
                    f"✅ Loaded: {extension}"
                )

            except Exception as error:
                print(
                    f"❌ Failed to load {extension}: "
                    f"{type(error).__name__}: {error}"
                )

        # -------------------------------------------------
        # إنشاء إعدادات السيرفرات الموجودة
        # -------------------------------------------------

        for guild in self.guilds:
            try:
                icon_url = ""

                if guild.icon:
                    icon_url = str(
                        guild.icon.url
                    )

                await db.ensure_guild(
                    guild_id=guild.id,
                    guild_name=guild.name,
                    guild_icon=icon_url
                )

            except Exception as error:
                print(
                    f"⚠️ Failed to initialize guild "
                    f"{guild.id}: "
                    f"{type(error).__name__}: {error}"
                )

        # -------------------------------------------------
        # مزامنة Slash Commands
        # -------------------------------------------------

        try:
            synced = await self.tree.sync()

            print(
                f"✅ Synced {len(synced)} Slash Commands."
            )

        except Exception as error:
            print(
                "❌ Failed to sync Slash Commands: "
                f"{type(error).__name__}: {error}"
            )

    # =====================================================
    # Bot Ready
    # =====================================================

    async def on_ready(self):

        print("=" * 60)
        print("🤖 Zivex is online!")
        print(f"👤 Logged in as: {self.user}")
        print(f"🆔 Bot ID: {self.user.id}")
        print(f"🌐 Servers: {len(self.guilds)}")
        print("=" * 60)

        # -------------------------------------------------
        # تحديث إعدادات السيرفرات
        # -------------------------------------------------

        for guild in self.guilds:
            try:
                icon_url = ""

                if guild.icon:
                    icon_url = str(
                        guild.icon.url
                    )

                await db.ensure_guild(
                    guild_id=guild.id,
                    guild_name=guild.name,
                    guild_icon=icon_url
                )

            except Exception as error:
                print(
                    f"⚠️ Failed to update guild "
                    f"{guild.id}: "
                    f"{type(error).__name__}: {error}"
                )

        # -------------------------------------------------
        # حالة البوت
        # -------------------------------------------------

        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{len(self.guilds)} servers"
        )

        await self.change_presence(
            status=discord.Status.online,
            activity=activity
        )

    # =====================================================
    # دخول سيرفر جديد
    # =====================================================

    async def on_guild_join(
        self,
        guild: discord.Guild
    ):

        icon_url = ""

        if guild.icon:
            icon_url = str(
                guild.icon.url
            )

        try:
            await db.ensure_guild(
                guild_id=guild.id,
                guild_name=guild.name,
                guild_icon=icon_url
            )

            print(
                f"➕ Joined server: "
                f"{guild.name} ({guild.id})"
            )

        except Exception as error:
            print(
                f"❌ Failed to initialize new guild "
                f"{guild.id}: "
                f"{type(error).__name__}: {error}"
            )

    # =====================================================
    # خروج من سيرفر
    # =====================================================

    async def on_guild_remove(
        self,
        guild: discord.Guild
    ):

        print(
            f"➖ Left server: "
            f"{guild.name} ({guild.id})"
        )

    # =====================================================
    # التعامل مع أخطاء الأوامر
    # =====================================================

    async def on_command_error(
        self,
        ctx: commands.Context,
        error: commands.CommandError
    ):

        # تجاهل الأمر غير الموجود
        if isinstance(
            error,
            commands.CommandNotFound
        ):
            return

        # تجاهل نقص الصلاحيات
        if isinstance(
            error,
            commands.MissingPermissions
        ):
            await ctx.send(
                "❌ ما عندك الصلاحيات المطلوبة."
            )
            return

        # نقص Arguments
        if isinstance(
            error,
            commands.MissingRequiredArgument
        ):
            await ctx.send(
                "❌ ناقصك معلومات لاستخدام الأمر."
            )
            return

        # Argument غير صحيح
        if isinstance(
            error,
            commands.BadArgument
        ):
            await ctx.send(
                "❌ المعلومات التي أدخلتها غير صحيحة."
            )
            return

        # الخطأ الحقيقي
        print(
            f"❌ Command error: "
            f"{type(error).__name__}: {error}"
        )

        try:
            await ctx.send(
                "❌ حدث خطأ أثناء تنفيذ الأمر."
            )
        except discord.HTTPException:
            pass


# =========================================================
# إنشاء البوت
# =========================================================

bot = Zivex()


# =========================================================
# تشغيل البوت
# =========================================================

async def main():

    if not DISCORD_TOKEN:
        raise RuntimeError(
            "DISCORD_TOKEN غير موجود في Railway Variables."
        )

    await bot.start(
        DISCORD_TOKEN
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        pass
