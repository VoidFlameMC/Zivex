import asyncio
import os

import discord
from discord.ext import commands

from config import DISCORD_TOKEN, PREFIX
from database import db


# =========================================================
# Zivex Bot
# =========================================================

intents = discord.Intents.default()

intents.members = True
intents.message_content = True


class Zivex(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=PREFIX,
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        # تشغيل قاعدة البيانات
        await db.setup()

        # تحميل جميع الـ Cogs تلقائيًا
        cog_files = [
            "cogs.utility",
            "cogs.welcome",
        ]

        for extension in cog_files:
            try:
                await self.load_extension(extension)
                print(f"✅ Loaded: {extension}")
            except Exception as error:
                print(
                    f"❌ Failed to load {extension}: "
                    f"{type(error).__name__}: {error}"
                )

        # مزامنة Slash Commands
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

        print("✅ Database initialized.")

    async def on_ready(self):
        print("=" * 50)
        print(f"🤖 Logged in as: {self.user}")
        print(f"🆔 Bot ID: {self.user.id}")
        print(f"🌐 Servers: {len(self.guilds)}")
        print("=" * 50)

        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{len(self.guilds)} servers"
        )

        await self.change_presence(
            status=discord.Status.online,
            activity=activity
        )

    async def on_guild_join(
        self,
        guild: discord.Guild
    ):
        icon_url = ""

        if guild.icon:
            icon_url = str(guild.icon.url)

        await db.ensure_guild(
            guild_id=guild.id,
            guild_name=guild.name,
            guild_icon=icon_url
        )

        print(
            f"➕ Joined server: "
            f"{guild.name} ({guild.id})"
        )

    async def on_guild_remove(
        self,
        guild: discord.Guild
    ):
        print(
            f"➖ Left server: "
            f"{guild.name} ({guild.id})"
        )


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

    await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
