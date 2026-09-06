import discord
from discord import app_commands
from discord.ext import commands

from config import BOT_NAME


class Owner(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # =====================================================
    # التحقق من مالك البوت
    # =====================================================

    async def check_owner(
        self,
        interaction: discord.Interaction
    ) -> bool:
        if await self.bot.is_owner(interaction.user):
            return True

        await interaction.response.send_message(
            "❌ هذا الأمر خاص بمالك بوت Zivex فقط.",
            ephemeral=True
        )
        return False

    async def check_prefix_owner(
        self,
        ctx: commands.Context
    ) -> bool:
        if await self.bot.is_owner(ctx.author):
            return True

        await ctx.send(
            "❌ هذا الأمر خاص بمالك بوت Zivex فقط."
        )
        return False

    # =====================================================
    # /owner
    # =====================================================

    @app_commands.command(
        name="owner",
        description="عرض معلومات مالك Zivex"
    )
    async def slash_owner(
        self,
        interaction: discord.Interaction
    ):
        if not await self.check_owner(interaction):
            return

        owner = interaction.user

        embed = discord.Embed(
            title="👑 Zivex Owner",
            description=(
                f"مالك بوت **{BOT_NAME}** هو:\n"
                f"{owner.mention}"
            ),
            color=discord.Color.gold()
        )

        embed.set_thumbnail(
            url=owner.display_avatar.url
        )

        embed.add_field(
            name="👤 الاسم",
            value=f"`{owner}`",
            inline=True
        )

        embed.add_field(
            name="🆔 ID",
            value=f"`{owner.id}`",
            inline=True
        )

        embed.set_footer(
            text=f"{BOT_NAME} • Bot Owner"
        )

        await interaction.response.send_message(
            embed=embed
        )

    # =====================================================
    # !مالك
    # =====================================================

    @commands.command(name="مالك")
    async def prefix_owner(
        self,
        ctx: commands.Context
    ):
        if not await self.check_prefix_owner(ctx):
            return

        owner = ctx.author

        embed = discord.Embed(
            title="👑 Zivex Owner",
            description=(
                f"مالك بوت **{BOT_NAME}** هو:\n"
                f"{owner.mention}"
            ),
            color=discord.Color.gold()
        )

        embed.set_thumbnail(
            url=owner.display_avatar.url
        )

        embed.add_field(
            name="👤 الاسم",
            value=f"`{owner}`",
            inline=True
        )

        embed.add_field(
            name="🆔 ID",
            value=f"`{owner.id}`",
            inline=True
        )

        embed.set_footer(
            text=f"{BOT_NAME} • Bot Owner"
        )

        await ctx.send(
            embed=embed
        )

    # =====================================================
    # /servers
    # =====================================================

    @app_commands.command(
        name="servers",
        description="عرض السيرفرات التي يوجد فيها Zivex"
    )
    async def slash_servers(
        self,
        interaction: discord.Interaction
    ):
        if not await self.check_owner(interaction):
            return

        guilds = sorted(
            self.bot.guilds,
            key=lambda guild: guild.name.lower()
        )

        if not guilds:
            description = "لا يوجد سيرفرات حاليًا."
        else:
            lines = []

            for index, guild in enumerate(
                guilds[:25],
                start=1
            ):
                lines.append(
                    f"`{index}.` **{guild.name}**\n"
                    f"└ 🆔 `{guild.id}` • "
                    f"👥 `{guild.member_count or 0}` عضو"
                )

            description = "\n\n".join(lines)

        embed = discord.Embed(
            title="🌐 سيرفرات Zivex",
            description=description,
            color=discord.Color.blurple()
        )

        embed.add_field(
            name="📊 إجمالي السيرفرات",
            value=f"`{len(guilds)}`",
            inline=True
        )

        if self.bot.user:
            embed.set_thumbnail(
                url=self.bot.user.display_avatar.url
            )

        embed.set_footer(
            text=f"{BOT_NAME} • Bot Owner"
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    # =====================================================
    # !سيرفرات
    # =====================================================

    @commands.command(name="سيرفرات")
    async def prefix_servers(
        self,
        ctx: commands.Context
    ):
        if not await self.check_prefix_owner(ctx):
            return

        guilds = sorted(
            self.bot.guilds,
            key=lambda guild: guild.name.lower()
        )

        if not guilds:
            description = "لا يوجد سيرفرات حاليًا."
        else:
            lines = []

            for index, guild in enumerate(
                guilds[:25],
                start=1
            ):
                lines.append(
                    f"`{index}.` **{guild.name}**\n"
                    f"└ 🆔 `{guild.id}` • "
                    f"👥 `{guild.member_count or 0}` عضو"
                )

            description = "\n\n".join(lines)

        embed = discord.Embed(
            title="🌐 سيرفرات Zivex",
            description=description,
            color=discord.Color.blurple()
        )

        embed.add_field(
            name="📊 إجمالي السيرفرات",
            value=f"`{len(guilds)}`",
            inline=True
        )

        embed.set_footer(
            text=f"{BOT_NAME} • Bot Owner"
        )

        await ctx.send(
            embed=embed
        )

    # =====================================================
    # /leave
    # =====================================================

    @app_commands.command(
        name="leave",
        description="إخراج Zivex من سيرفر"
    )
    @app_commands.describe(
        guild_id="ID السيرفر"
    )
    async def slash_leave(
        self,
        interaction: discord.Interaction,
        guild_id: str
    ):
        if not await self.check_owner(interaction):
            return

        try:
            guild_id_int = int(guild_id)
        except ValueError:
            await interaction.response.send_message(
                "❌ ID السيرفر غير صحيح.",
                ephemeral=True
            )
            return

        guild = self.bot.get_guild(guild_id_int)

        if guild is None:
            await interaction.response.send_message(
                "❌ ما لقيت السيرفر أو البوت غير موجود فيه.",
                ephemeral=True
            )
            return

        guild_name = guild.name

        try:
            await guild.leave()

            await interaction.response.send_message(
                f"✅ تم إخراج **{guild_name}** من Zivex."
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ ما قدرت أخرج من السيرفر.",
                ephemeral=True
            )

        except discord.HTTPException:
            await interaction.response.send_message(
                "❌ حدث خطأ أثناء محاولة الخروج من السيرفر.",
                ephemeral=True
            )

    # =====================================================
    # !خروج
    # =====================================================

    @commands.command(name="خروج")
    async def prefix_leave(
        self,
        ctx: commands.Context,
        guild_id: str
    ):
        if not await self.check_prefix_owner(ctx):
            return

        try:
            guild_id_int = int(guild_id)
        except ValueError:
            await ctx.send(
                "❌ ID السيرفر غير صحيح."
            )
            return

        guild = self.bot.get_guild(guild_id_int)

        if guild is None:
            await ctx.send(
                "❌ ما لقيت السيرفر أو البوت غير موجود فيه."
            )
            return

        guild_name = guild.name

        try:
            await guild.leave()

            await ctx.send(
                f"✅ تم إخراج **{guild_name}** من Zivex."
            )

        except discord.Forbidden:
            await ctx.send(
                "❌ ما قدرت أخرج من السيرفر."
            )

        except discord.HTTPException:
            await ctx.send(
                "❌ حدث خطأ أثناء محاولة الخروج من السيرفر."
            )

    # =====================================================
    # /botstats
    # =====================================================

    @app_commands.command(
        name="botstats",
        description="عرض إحصائيات Zivex"
    )
    async def slash_botstats(
        self,
        interaction: discord.Interaction
    ):
        if not await self.check_owner(interaction):
            return

        total_members = sum(
            guild.member_count or 0
            for guild in self.bot.guilds
        )

        embed = discord.Embed(
            title="📊 إحصائيات Zivex",
            color=discord.Color.blurple()
        )

        embed.add_field(
            name="🌐 السيرفرات",
            value=f"`{len(self.bot.guilds)}`",
            inline=True
        )

        embed.add_field(
            name="👥 الأعضاء",
            value=f"`{total_members}`",
            inline=True
        )

        embed.add_field(
            name="⚡ Ping",
            value=f"`{round(self.bot.latency * 1000)}ms`",
            inline=True
        )

        if self.bot.user:
            embed.add_field(
                name="🤖 البوت",
                value=f"`{self.bot.user}`",
                inline=True
            )

            embed.add_field(
                name="🆔 Bot ID",
                value=f"`{self.bot.user.id}`",
                inline=True
            )

            embed.set_thumbnail(
                url=self.bot.user.display_avatar.url
            )

        embed.set_footer(
            text=f"{BOT_NAME} • Bot Owner"
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    # =====================================================
    # !احصائيات
    # =====================================================

    @commands.command(name="احصائيات")
    async def prefix_botstats(
        self,
        ctx: commands.Context
    ):
        if not await self.check_prefix_owner(ctx):
            return

        total_members = sum(
            guild.member_count or 0
            for guild in self.bot.guilds
        )

        embed = discord.Embed(
            title="📊 إحصائيات Zivex",
            color=discord.Color.blurple()
        )

        embed.add_field(
            name="🌐 السيرفرات",
            value=f"`{len(self.bot.guilds)}`",
            inline=True
        )

        embed.add_field(
            name="👥 الأعضاء",
            value=f"`{total_members}`",
            inline=True
        )

        embed.add_field(
            name="⚡ Ping",
            value=f"`{round(self.bot.latency * 1000)}ms`",
            inline=True
        )

        if self.bot.user:
            embed.add_field(
                name="🤖 البوت",
                value=f"`{self.bot.user}`",
                inline=True
            )

            embed.add_field(
                name="🆔 Bot ID",
                value=f"`{self.bot.user.id}`",
                inline=True
            )

        embed.set_footer(
            text=f"{BOT_NAME} • Bot Owner"
        )

        await ctx.send(
            embed=embed
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Owner(bot))
