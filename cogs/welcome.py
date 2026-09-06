import discord
from discord.ext import commands

from database import db


class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        settings = await db.get_guild(member.guild.id)

        if not settings:
            await db.ensure_guild(
                guild_id=member.guild.id,
                guild_name=member.guild.name,
                guild_icon=str(member.guild.icon.url)
                if member.guild.icon else ""
            )

            settings = await db.get_guild(member.guild.id)

        if not settings:
            return

        # إذا الترحيب غير مفعل
        if not settings["welcome_enabled"]:
            return

        channel_id = settings["welcome_channel_id"]

        # إذا ما تم تحديد قناة
        if not channel_id:
            return

        channel = member.guild.get_channel(channel_id)

        if not isinstance(channel, discord.TextChannel):
            return

        embed = discord.Embed(
            title=f"مرحبًا بك في {member.guild.name}",
            description=(
                f"أهلًا {member.mention} 👋\n"
                f"نتمنى لك وقتًا ممتعًا في السيرفر!"
            ),
            color=discord.Color.blurple()
        )

        if member.guild.icon:
            embed.set_thumbnail(
                url=member.guild.icon.url
            )

        embed.set_footer(
            text=f"عضو جديد #{member.guild.member_count}"
        )

        await channel.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))
