import discord
from discord import app_commands
from discord.ext import commands

from database import db


class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # =========================================================
    # Helpers
    # =========================================================

    async def get_settings(self, guild: discord.Guild):
        settings = await db.get_guild(guild.id)

        if not settings:
            await db.ensure_guild(
                guild_id=guild.id,
                guild_name=guild.name,
                guild_icon=(
                    str(guild.icon.url)
                    if guild.icon
                    else ""
                ),
            )
            settings = await db.get_guild(guild.id)

        return settings

    def create_welcome_embed(
        self,
        member: discord.Member,
    ):
        guild = member.guild

        embed = discord.Embed(
            title=f"مرحبًا بك في {guild.name}",
            description=(
                f"أهلًا وسهلًا {member.mention} 👋\n"
                "نتمنى لك وقتًا ممتعًا معنا!"
            ),
            color=discord.Color.blurple(),
        )

        if guild.icon:
            embed.set_thumbnail(
                url=guild.icon.url
            )

        embed.add_field(
            name="👤 العضو",
            value=member.mention,
            inline=True,
        )

        embed.add_field(
            name="👥 عدد الأعضاء",
            value=f"`{guild.member_count or 0}`",
            inline=True,
        )

        embed.set_footer(
            text=f"عضو جديد #{guild.member_count or 0} • Zivex"
        )

        return embed

    # =========================================================
    # Welcome Event
    # =========================================================

    @commands.Cog.listener()
    async def on_member_join(
        self,
        member: discord.Member,
    ):
        try:
            settings = await self.get_settings(
                member.guild
            )

            if not settings:
                return

            if not settings["welcome_enabled"]:
                return

            channel_id = settings["welcome_channel_id"]

            if not channel_id:
                return

            channel = member.guild.get_channel(
                int(channel_id)
            )

            if not isinstance(
                channel,
                discord.TextChannel,
            ):
                return

            await channel.send(
                embed=self.create_welcome_embed(member)
            )

        except Exception as error:
            print(
                f"❌ Welcome error in "
                f"{member.guild.id}: {error}"
            )

    # =========================================================
    # /welcome
    # =========================================================

    welcome_group = app_commands.Group(
        name="welcome",
        description="Manage the welcome system",
    )

    @welcome_group.command(
        name="status",
        description="Show welcome system status",
    )
    async def welcome_status(
        self,
        interaction: discord.Interaction,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ هذا الأمر يعمل داخل السيرفر فقط.",
                ephemeral=True,
            )
            return

        settings = await self.get_settings(
            interaction.guild
        )

        if not settings:
            await interaction.response.send_message(
                "❌ تعذر الحصول على إعدادات السيرفر.",
                ephemeral=True,
            )
            return

        enabled = settings["welcome_enabled"]
        channel_id = settings["welcome_channel_id"]

        channel = (
            interaction.guild.get_channel(
                int(channel_id)
            )
            if channel_id
            else None
        )

        embed = discord.Embed(
            title="👋 نظام الترحيب",
            color=discord.Color.green()
            if enabled
            else discord.Color.red(),
        )

        embed.add_field(
            name="الحالة",
            value="🟢 مفعل" if enabled else "🔴 متوقف",
            inline=True,
        )

        embed.add_field(
            name="الروم",
            value=(
                channel.mention
                if isinstance(
                    channel,
                    discord.TextChannel,
                )
                else "❌ غير محدد"
            ),
            inline=True,
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    @welcome_group.command(
        name="enable",
        description="Enable the welcome system",
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def welcome_enable(
        self,
        interaction: discord.Interaction,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ هذا الأمر يعمل داخل السيرفر فقط.",
                ephemeral=True,
            )
            return

        await db.set_enabled(
            interaction.guild.id,
            "welcome",
            True,
        )

        await interaction.response.send_message(
            "✅ تم تفعيل نظام الترحيب.",
            ephemeral=True,
        )

    @welcome_group.command(
        name="disable",
        description="Disable the welcome system",
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def welcome_disable(
        self,
        interaction: discord.Interaction,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ هذا الأمر يعمل داخل السيرفر فقط.",
                ephemeral=True,
            )
            return

        await db.set_enabled(
            interaction.guild.id,
            "welcome",
            False,
        )

        await interaction.response.send_message(
            "✅ تم تعطيل نظام الترحيب.",
            ephemeral=True,
        )

    @welcome_group.command(
        name="channel",
        description="Set the welcome channel",
    )
    @app_commands.describe(
        channel="The welcome channel"
    )
    @app_commands.checks.has_permissions(
        manage_guild=True
    )
    async def welcome_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ هذا الأمر يعمل داخل السيرفر فقط.",
                ephemeral=True,
            )
            return

        await db.set_channel(
            interaction.guild.id,
            "welcome",
            channel.id,
        )

        await interaction.response.send_message(
            f"✅ تم تحديد روم الترحيب: {channel.mention}",
            ephemeral=True,
        )

    # =========================================================
    # !ترحيب
    # =========================================================

    @commands.command(name="ترحيب")
    @commands.has_guild_permissions(
        manage_guild=True
    )
    async def prefix_welcome(
        self,
        ctx: commands.Context,
        action: str = "حالة",
        channel: discord.TextChannel | None = None,
    ):
        if ctx.guild is None:
            await ctx.send(
                "❌ هذا الأمر يعمل داخل السيرفر فقط."
            )
            return

        action = action.lower()

        if action in ("تشغيل", "تفعيل"):
            await db.set_enabled(
                ctx.guild.id,
                "welcome",
                True,
            )

            await ctx.send(
                "✅ تم تفعيل نظام الترحيب."
            )
            return

        if action in ("ايقاف", "تعطيل"):
            await db.set_enabled(
                ctx.guild.id,
                "welcome",
                False,
            )

            await ctx.send(
                "✅ تم تعطيل نظام الترحيب."
            )
            return

        if action in ("روم", "قناة"):
            if channel is None:
                await ctx.send(
                    "❌ حدد الروم، مثال: `!ترحيب روم #welcome`"
                )
                return

            await db.set_channel(
                ctx.guild.id,
                "welcome",
                channel.id,
            )

            await ctx.send(
                f"✅ تم تحديد روم الترحيب: {channel.mention}"
            )
            return

        settings = await self.get_settings(
            ctx.guild
        )

        if not settings:
            await ctx.send(
                "❌ تعذر الحصول على إعدادات الترحيب."
            )
            return

        enabled = settings["welcome_enabled"]
        channel_id = settings["welcome_channel_id"]

        welcome_channel = (
            ctx.guild.get_channel(
                int(channel_id)
            )
            if channel_id
            else None
        )

        embed = discord.Embed(
            title="👋 حالة نظام الترحيب",
            color=discord.Color.green()
            if enabled
            else discord.Color.red(),
        )

        embed.add_field(
            name="الحالة",
            value="🟢 مفعل" if enabled else "🔴 متوقف",
            inline=True,
        )

        embed.add_field(
            name="الروم",
            value=(
                welcome_channel.mention
                if isinstance(
                    welcome_channel,
                    discord.TextChannel,
                )
                else "❌ غير محدد"
            ),
            inline=True,
        )

        await ctx.send(
            embed=embed
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))
