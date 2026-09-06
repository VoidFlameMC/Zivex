import discord
from discord.ext import commands

from database import db


class Levels(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if message.guild is None:
            return

        settings = await db.get_guild(message.guild.id)

        if not settings:
            await db.ensure_guild(
                guild_id=message.guild.id,
                guild_name=message.guild.name,
                guild_icon=(
                    str(message.guild.icon.url)
                    if message.guild.icon
                    else ""
                )
            )
            settings = await db.get_guild(message.guild.id)

        if not settings:
            return

        if not settings["level_enabled"]:
            return

        channel_id = settings["level_channel_id"]

        if not channel_id:
            return

        channel = message.guild.get_channel(channel_id)

        if not isinstance(channel, discord.TextChannel):
            return

        # نظام XP الأساسي سيتم تطويره لاحقًا
        # حاليًا هذا الحدث مجهز للربط مع قاعدة البيانات.

    @commands.command(name="ليفل")
    async def level_prefix(self, ctx: commands.Context):
        await ctx.send(
            "📊 نظام الليفلز موجود، "
            "وسيتم عرض مستواك هنا بعد تفعيل نظام XP."
        )

    @commands.command(name="مستوى")
    async def level_prefix_alt(self, ctx: commands.Context):
        await ctx.send(
            "📊 سيتم عرض مستواك بعد تفعيل نظام XP."
        )

    @commands.command(name="ترتيب")
    async def leaderboard_prefix(
        self,
        ctx: commands.Context
    ):
        await ctx.send(
            "🏆 لوحة المتصدرين سيتم إضافتها مع نظام XP."
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Levels(bot))
