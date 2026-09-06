import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime


OWNER_ID = 1293157778030071920


class Owner(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # =========================================================
    # Owner Check
    # =========================================================

    async def is_bot_owner(self, user: discord.User) -> bool:
        try:
            return await self.bot.is_owner(user)
        except Exception:
            return user.id == OWNER_ID

    async def owner_only(
        self,
        ctx: commands.Context,
    ) -> bool:
        if await self.is_bot_owner(ctx.author):
            return True

        await ctx.send(
            "❌ هذا الأمر خاص بصاحب البوت فقط.",
            delete_after=5,
        )
        return False

    # =========================================================
    # Prefix: معلومات البوت
    # =========================================================

    @commands.command(name="معلومات البوت")
    async def bot_info(
        self,
        ctx: commands.Context,
    ):
        if not await self.owner_only(ctx):
            return

        guilds = len(self.bot.guilds)
        users = sum(
            guild.member_count or 0
            for guild in self.bot.guilds
        )

        embed = discord.Embed(
            title="🤖 معلومات Zivex",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )

        embed.add_field(
            name="🖥️ السيرفرات",
            value=f"`{guilds}`",
            inline=True,
        )

        embed.add_field(
            name="👥 الأعضاء",
            value=f"`{users:,}`",
            inline=True,
        )

        embed.add_field(
            name="📡 Ping",
            value=f"`{round(self.bot.latency * 1000)}ms`",
            inline=True,
        )

        embed.add_field(
            name="🐍 Python",
            value="`3.x`",
            inline=True,
        )

        embed.add_field(
            name="⚙️ Discord.py",
            value=f"`{discord.__version__}`",
            inline=True,
        )

        embed.add_field(
            name="🆔 Owner",
            value=f"<@{OWNER_ID}>",
            inline=True,
        )

        if self.bot.user:
            embed.set_thumbnail(
                url=self.bot.user.display_avatar.url
            )

        embed.set_footer(
            text="Zivex • Owner System"
        )

        await ctx.send(embed=embed)

    # =========================================================
    # Prefix: حالة البوت
    # =========================================================

    @commands.command(name="حالة البوت")
    async def bot_status(
        self,
        ctx: commands.Context,
    ):
        if not await self.owner_only(ctx):
            return

        latency = round(
            self.bot.latency * 1000
        )

        embed = discord.Embed(
            title="📡 حالة البوت",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )

        embed.add_field(
            name="الحالة",
            value="🟢 متصل",
            inline=True,
        )

        embed.add_field(
            name="Ping",
            value=f"`{latency}ms`",
            inline=True,
        )

        embed.add_field(
            name="Shard",
            value="`1`",
            inline=True,
        )

        await ctx.send(embed=embed)

    # =========================================================
    # Prefix: إعادة تشغيل الـCogs
    # =========================================================

    @commands.command(name="تحديث")
    async def reload_all(
        self,
        ctx: commands.Context,
    ):
        if not await self.owner_only(ctx):
            return

        message = await ctx.send(
            "🔄 جاري تحديث أنظمة البوت..."
        )

        extensions = [
            "cogs.utility",
            "cogs.welcome",
            "cogs.levels",
            "cogs.moderation",
            "cogs.tickets",
            "cogs.applications",
            "cogs.owner",
            "cogs.logs",
        ]

        failed = []

        for extension in extensions:
            try:
                if extension == "cogs.owner":
                    continue

                if extension in self.bot.extensions:
                    await self.bot.reload_extension(
                        extension
                    )
                else:
                    await self.bot.load_extension(
                        extension
                    )

            except Exception as error:
                failed.append(
                    f"`{extension}` — `{type(error).__name__}`"
                )

        if failed:
            embed = discord.Embed(
                title="⚠️ تم التحديث مع وجود أخطاء",
                description=(
                    "بعض الأنظمة لم يتم تحديثها:\n\n"
                    + "\n".join(failed)
                ),
                color=discord.Color.orange(),
            )
        else:
            embed = discord.Embed(
                title="✅ تم التحديث",
                description=(
                    "تم تحديث أنظمة Zivex بنجاح."
                ),
                color=discord.Color.green(),
            )

        await message.edit(
            content=None,
            embed=embed,
        )

    # =========================================================
    # Prefix: سيرفرات البوت
    # =========================================================

    @commands.command(name="السيرفرات")
    async def guilds_list(
        self,
        ctx: commands.Context,
    ):
        if not await self.owner_only(ctx):
            return

        guilds = sorted(
            self.bot.guilds,
            key=lambda guild: (
                guild.member_count or 0
            ),
            reverse=True,
        )

        if not guilds:
            await ctx.send(
                "❌ البوت غير موجود في أي سيرفر."
            )
            return

        lines = []

        for index, guild in enumerate(
            guilds[:20],
            start=1,
        ):
            lines.append(
                f"**{index}.** {guild.name} "
                f"`{guild.id}` — "
                f"`{guild.member_count or 0}` عضو"
            )

        embed = discord.Embed(
            title=(
                f"🖥️ سيرفرات Zivex "
                f"({len(guilds)})"
            ),
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )

        await ctx.send(embed=embed)

    # =========================================================
    # Prefix: مغادرة سيرفر
    # =========================================================

    @commands.command(name="غادر")
    async def leave_guild(
        self,
        ctx: commands.Context,
        guild_id: int,
    ):
        if not await self.owner_only(ctx):
            return

        guild = self.bot.get_guild(
            guild_id
        )

        if not guild:
            await ctx.send(
                "❌ ما لقيت السيرفر بهذا الـID."
            )
            return

        guild_name = guild.name

        try:
            await guild.leave()

            await ctx.send(
                f"✅ غادرت السيرفر **{guild_name}**."
            )

        except discord.HTTPException:
            await ctx.send(
                "❌ حدث خطأ أثناء مغادرة السيرفر."
            )

    # =========================================================
    # Prefix: انضمام لسيرفر
    # =========================================================

    @commands.command(name="معلومات سيرفر")
    async def server_info(
        self,
        ctx: commands.Context,
        guild_id: int,
    ):
        if not await self.owner_only(ctx):
            return

        guild = self.bot.get_guild(
            guild_id
        )

        if not guild:
            await ctx.send(
                "❌ البوت غير موجود في هذا السيرفر."
            )
            return

        embed = discord.Embed(
            title=f"🖥️ {guild.name}",
            color=discord.Color.blurple(),
        )

        embed.add_field(
            name="🆔 ID",
            value=f"`{guild.id}`",
            inline=False,
        )

        embed.add_field(
            name="👥 الأعضاء",
            value=f"`{guild.member_count or 0}`",
            inline=True,
        )

        embed.add_field(
            name="💬 الرومات",
            value=f"`{len(guild.channels)}`",
            inline=True,
        )

        embed.add_field(
            name="🎭 الرتب",
            value=f"`{len(guild.roles)}`",
            inline=True,
        )

        embed.add_field(
            name="👑 المالك",
            value=f"<@{guild.owner_id}>",
            inline=False,
        )

        if guild.icon:
            embed.set_thumbnail(
                url=guild.icon.url
            )

        await ctx.send(embed=embed)

    # =========================================================
    # Slash: Bot Info
    # =========================================================

    @app_commands.command(
        name="bot-info",
        description="عرض معلومات البوت",
    )
    async def slash_bot_info(
        self,
        interaction: discord.Interaction,
    ):
        if not await self.is_bot_owner(
            interaction.user
        ):
            await interaction.response.send_message(
                "❌ هذا الأمر خاص بصاحب البوت فقط.",
                ephemeral=True,
            )
            return

        guilds = len(self.bot.guilds)
        users = sum(
            guild.member_count or 0
            for guild in self.bot.guilds
        )

        embed = discord.Embed(
            title="🤖 معلومات Zivex",
            color=discord.Color.blurple(),
            timestamp=discord.utils.utcnow(),
        )

        embed.add_field(
            name="🖥️ السيرفرات",
            value=f"`{guilds}`",
            inline=True,
        )

        embed.add_field(
            name="👥 الأعضاء",
            value=f"`{users:,}`",
            inline=True,
        )

        embed.add_field(
            name="📡 Ping",
            value=f"`{round(self.bot.latency * 1000)}ms`",
            inline=True,
        )

        if self.bot.user:
            embed.set_thumbnail(
                url=self.bot.user.display_avatar.url
            )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    # =========================================================
    # Slash: Bot Status
    # =========================================================

    @app_commands.command(
        name="bot-status",
        description="عرض حالة البوت",
    )
    async def slash_bot_status(
        self,
        interaction: discord.Interaction,
    ):
        if not await self.is_bot_owner(
            interaction.user
        ):
            await interaction.response.send_message(
                "❌ هذا الأمر خاص بصاحب البوت فقط.",
                ephemeral=True,
            )
            return

        latency = round(
            self.bot.latency * 1000
        )

        embed = discord.Embed(
            title="📡 حالة Zivex",
            color=discord.Color.green(),
        )

        embed.add_field(
            name="الحالة",
            value="🟢 متصل",
            inline=True,
        )

        embed.add_field(
            name="Ping",
            value=f"`{latency}ms`",
            inline=True,
        )

        embed.add_field(
            name="السيرفرات",
            value=f"`{len(self.bot.guilds)}`",
            inline=True,
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    # =========================================================
    # Slash: Guilds
    # =========================================================

    @app_commands.command(
        name="guilds",
        description="عرض سيرفرات البوت",
    )
    async def slash_guilds(
        self,
        interaction: discord.Interaction,
    ):
        if not await self.is_bot_owner(
            interaction.user
        ):
            await interaction.response.send_message(
                "❌ هذا الأمر خاص بصاحب البوت فقط.",
                ephemeral=True,
            )
            return

        guilds = sorted(
            self.bot.guilds,
            key=lambda guild: (
                guild.member_count or 0
            ),
            reverse=True,
        )

        lines = []

        for index, guild in enumerate(
            guilds[:20],
            start=1,
        ):
            lines.append(
                f"**{index}.** {guild.name} "
                f"`{guild.id}` — "
                f"`{guild.member_count or 0}` عضو"
            )

        embed = discord.Embed(
            title=f"🖥️ سيرفرات Zivex ({len(guilds)})",
            description=(
                "\n".join(lines)
                if lines
                else "لا توجد سيرفرات."
            ),
            color=discord.Color.blurple(),
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
        )

    # =========================================================
    # Slash: Leave Guild
    # =========================================================

    @app_commands.command(
        name="leave-guild",
        description="إخراج البوت من سيرفر",
    )
    @app_commands.describe(
        guild_id="ID السيرفر",
    )
    async def slash_leave_guild(
        self,
        interaction: discord.Interaction,
        guild_id: str,
    ):
        if not await self.is_bot_owner(
            interaction.user
        ):
            await interaction.response.send_message(
                "❌ هذا الأمر خاص بصاحب البوت فقط.",
                ephemeral=True,
            )
            return

        try:
            guild_id_int = int(
                guild_id
            )
        except ValueError:
            await interaction.response.send_message(
                "❌ الـID غير صحيح.",
                ephemeral=True,
            )
            return

        guild = self.bot.get_guild(
            guild_id_int
        )

        if not guild:
            await interaction.response.send_message(
                "❌ البوت غير موجود في هذا السيرفر.",
                ephemeral=True,
            )
            return

        guild_name = guild.name

        try:
            await guild.leave()

            await interaction.response.send_message(
                f"✅ غادرت **{guild_name}**.",
                ephemeral=True,
            )

        except discord.HTTPException:
            await interaction.response.send_message(
                "❌ حدث خطأ أثناء مغادرة السيرفر.",
                ephemeral=True,
            )


# =========================================================
# Setup
# =========================================================

async def setup(
    bot: commands.Bot,
):
    await bot.add_cog(
        Owner(bot)
    )
