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

# نحتاج هذه للترحيب والليفلات والتعامل مع الأعضاء
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
        # تجهيز قاعدة البيانات
        await db.setup()

        # تحميل الـ Cogs لاحقًا
        # سيتم تفعيلها بعد إنشاء ملفاتها

        print("✅ Database initialized.")

    async def on_ready(self):
        print("=" * 45)
        print(f"🤖 Logged in as: {self.user}")
        print(f"🆔 Bot ID: {self.user.id}")
        print(f"🌐 Servers: {len(self.guilds)}")
        print("=" * 45)

        # تحديث حالة البوت
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name=f"{len(self.guilds)} servers"
        )

        await self.change_presence(
            status=discord.Status.online,
            activity=activity
        )

    async def on_guild_join(self, guild: discord.Guild):
        icon_url = None

        if guild.icon:
            icon_url = guild.icon.url

        await db.ensure_guild(
            guild_id=guild.id,
            guild_name=guild.name,
            guild_icon=str(icon_url) if icon_url else ""
        )

        print(
            f"➕ Joined server: "
            f"{guild.name} ({guild.id})"
        )

    async def on_guild_remove(self, guild: discord.Guild):
        print(
            f"➖ Left server: "
            f"{guild.name} ({guild.id})"
        )


# =========================================================
# إنشاء البوت
# =========================================================

bot = Zivex()


# =========================================================
# أمر اختبار
# =========================================================

@bot.command(name="ping")
async def ping(ctx: commands.Context):
    latency = round(bot.latency * 1000)

    await ctx.send(
        f"🏓 Pong!\n"
        f"**Latency:** `{latency}ms`"
    )


# =========================================================
# أمر معلومات Zivex
# =========================================================

@bot.command(name="zivex")
async def zivex(ctx: commands.Context):
    embed = discord.Embed(
        title="Zivex",
        description=(
            "بوت Discord متعدد الأنظمة.\n"
            "إعدادات السيرفر يتم التحكم بها من لوحة التحكم."
        ),
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="🤖 السيرفرات",
        value=f"`{len(bot.guilds)}`",
        inline=True
    )

    embed.add_field(
        name="⚡ Ping",
        value=f"`{round(bot.latency * 1000)}ms`",
        inline=True
    )

    await ctx.send(embed=embed)


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
