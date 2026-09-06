import random
import time
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands


CREATOR_ID = 1293157778030071920


class Utility(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.started_at = time.time()

    # =========================================================
    # Helpers
    # =========================================================

    def embed(self, title, description="", color=discord.Color.blurple()):
        return discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.now(timezone.utc),
        )

    def creator_mention(self):
        return f"<@{CREATOR_ID}>"

    # =========================================================
    # /ping - !بنق
    # =========================================================

    @app_commands.command(
        name="ping",
        description="Check Zivex response time",
    )
    async def slash_ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)

        await interaction.response.send_message(
            embed=self.embed(
                "🏓 Pong!",
                f"زمن استجابة Zivex: `{latency}ms`",
            )
        )

    @commands.command(name="بنق")
    async def prefix_ping(self, ctx: commands.Context):
        latency = round(self.bot.latency * 1000)

        await ctx.send(
            embed=self.embed(
                "🏓 Pong!",
                f"زمن استجابة Zivex: `{latency}ms`",
            )
        )

    # =========================================================
    # /bot - !بوت
    # =========================================================

    @app_commands.command(
        name="bot",
        description="Show information about Zivex",
    )
    async def slash_bot(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=self.create_bot_embed()
        )

    @commands.command(name="بوت")
    async def prefix_bot(self, ctx: commands.Context):
        await ctx.send(
            embed=self.create_bot_embed()
        )

    def create_bot_embed(self):
        guild_count = len(self.bot.guilds)
        latency = round(self.bot.latency * 1000)

        embed = self.embed(
            "🤖 Zivex",
            "بوت Discord متعدد الأنظمة ومخصص لإدارة السيرفرات.",
        )

        embed.add_field(
            name="🌐 السيرفرات",
            value=f"`{guild_count}`",
            inline=True,
        )

        embed.add_field(
            name="⚡ Ping",
            value=f"`{latency}ms`",
            inline=True,
        )

        if self.bot.user:
            embed.set_thumbnail(
                url=self.bot.user.display_avatar.url
            )

        embed.set_footer(
            text="Zivex • Dashboard"
        )

        return embed

    # =========================================================
    # /server - !سيرفر
    # =========================================================

    @app_commands.command(
        name="server",
        description="Show information about this server",
    )
    async def slash_server(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ هذا الأمر يعمل داخل السيرفر فقط.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=self.create_server_embed(interaction.guild)
        )

    @commands.command(name="سيرفر")
    async def prefix_server(self, ctx: commands.Context):
        if ctx.guild is None:
            await ctx.send(
                "❌ هذا الأمر يعمل داخل السيرفر فقط."
            )
            return

        await ctx.send(
            embed=self.create_server_embed(ctx.guild)
        )

    def create_server_embed(self, guild: discord.Guild):
        embed = self.embed(
            f"📊 معلومات {guild.name}"
        )

        embed.add_field(
            name="👥 الأعضاء",
            value=f"`{guild.member_count or 0}`",
            inline=True,
        )

        embed.add_field(
            name="🆔 ID",
            value=f"`{guild.id}`",
            inline=True,
        )

        embed.add_field(
            name="📁 القنوات",
            value=f"`{len(guild.channels)}`",
            inline=True,
        )

        embed.add_field(
            name="🎭 الرتب",
            value=f"`{len(guild.roles)}`",
            inline=True,
        )

        if guild.owner:
            embed.add_field(
                name="👑 المالك",
                value=guild.owner.mention,
                inline=True,
            )

        if guild.icon:
            embed.set_thumbnail(
                url=guild.icon.url
            )

        return embed

    # =========================================================
    # /user - !عضو
    # =========================================================

    @app_commands.command(
        name="user",
        description="Show user information",
    )
    @app_commands.describe(member="The member to inspect")
    async def slash_user(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ):
        member = member or interaction.user

        await interaction.response.send_message(
            embed=self.create_user_embed(member)
        )

    @commands.command(name="عضو")
    async def prefix_user(
        self,
        ctx: commands.Context,
        member: discord.Member | None = None,
    ):
        member = member or ctx.author

        await ctx.send(
            embed=self.create_user_embed(member)
        )

    def create_user_embed(self, member: discord.Member):
        embed = self.embed(
            f"👤 معلومات {member.display_name}"
        )

        embed.set_thumbnail(
            url=member.display_avatar.url
        )

        embed.add_field(
            name="👤 المستخدم",
            value=member.mention,
            inline=True,
        )

        embed.add_field(
            name="🆔 ID",
            value=f"`{member.id}`",
            inline=True,
        )

        embed.add_field(
            name="🤖 Bot",
            value="نعم" if member.bot else "لا",
            inline=True,
        )

        embed.add_field(
            name="🎭 الرتب",
            value=f"`{max(len(member.roles) - 1, 0)}`",
            inline=True,
        )

        embed.add_field(
            name="📅 انضم للسيرفر",
            value=discord.utils.format_dt(
                member.joined_at,
                style="F",
            ) if member.joined_at else "غير معروف",
            inline=False,
        )

        embed.set_footer(
            text=f"Zivex • {member}"
        )

        return embed

    # =========================================================
    # /avatar - !افتار
    # =========================================================

    @app_commands.command(
        name="avatar",
        description="Show a user's avatar",
    )
    @app_commands.describe(member="The member")
    async def slash_avatar(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ):
        member = member or interaction.user

        embed = self.embed(
            "🖼️ Avatar",
            f"افتار {member.mention}",
        )
        embed.set_image(
            url=member.display_avatar.url
        )

        await interaction.response.send_message(
            embed=embed
        )

    @commands.command(name="افتار")
    async def prefix_avatar(
        self,
        ctx: commands.Context,
        member: discord.Member | None = None,
    ):
        member = member or ctx.author

        embed = self.embed(
            "🖼️ Avatar",
            f"افتار {member.mention}",
        )
        embed.set_image(
            url=member.display_avatar.url
        )

        await ctx.send(embed=embed)

    # =========================================================
    # /banner - !بنر
    # =========================================================

    @app_commands.command(
        name="banner",
        description="Show a user's banner",
    )
    @app_commands.describe(member="The member")
    async def slash_banner(
        self,
        interaction: discord.Interaction,
        member: discord.User | None = None,
    ):
        member = member or interaction.user

        user = await self.bot.fetch_user(member.id)

        if not user.banner:
            await interaction.response.send_message(
                "❌ هذا المستخدم لا يملك بنر.",
                ephemeral=True,
            )
            return

        embed = self.embed(
            "🎨 Banner",
            f"بنر {user.mention}",
        )
        embed.set_image(
            url=user.banner.url
        )

        await interaction.response.send_message(
            embed=embed
        )

    @commands.command(name="بنر")
    async def prefix_banner(
        self,
        ctx: commands.Context,
        member: discord.Member | None = None,
    ):
        member = member or ctx.author

        user = await self.bot.fetch_user(member.id)

        if not user.banner:
            await ctx.send(
                "❌ هذا المستخدم لا يملك بنر."
            )
            return

        embed = self.embed(
            "🎨 Banner",
            f"بنر {user.mention}",
        )
        embed.set_image(
            url=user.banner.url
        )

        await ctx.send(embed=embed)

    # =========================================================
    # /id - !ايدي
    # =========================================================

    @app_commands.command(
        name="id",
        description="Show a user's ID",
    )
    @app_commands.describe(member="The member")
    async def slash_id(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ):
        member = member or interaction.user

        await interaction.response.send_message(
            f"🆔 ID الخاص بـ {member.mention}: `{member.id}`"
        )

    @commands.command(name="ايدي")
    async def prefix_id(
        self,
        ctx: commands.Context,
        member: discord.Member | None = None,
    ):
        member = member or ctx.author

        await ctx.send(
            f"🆔 ID الخاص بـ {member.mention}: `{member.id}`"
        )

    # =========================================================
    # /role - !رتبة
    # =========================================================

    @app_commands.command(
        name="role",
        description="Show role information",
    )
    @app_commands.describe(role="The role")
    async def slash_role(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
    ):
        await interaction.response.send_message(
            embed=self.create_role_embed(role)
        )

    @commands.command(name="رتبة")
    async def prefix_role(
        self,
        ctx: commands.Context,
        role: discord.Role,
    ):
        await ctx.send(
            embed=self.create_role_embed(role)
        )

    def create_role_embed(self, role: discord.Role):
        embed = self.embed(
            f"🎭 معلومات رتبة {role.name}"
        )

        embed.add_field(
            name="🆔 ID",
            value=f"`{role.id}`",
            inline=True,
        )

        embed.add_field(
            name="👥 الأعضاء",
            value=f"`{len(role.members)}`",
            inline=True,
        )

        embed.add_field(
            name="🎨 اللون",
            value=f"`{role.color}`",
            inline=True,
        )

        embed.add_field(
            name="🔝 Position",
            value=f"`{role.position}`",
            inline=True,
        )

        embed.add_field(
            name="🔒 Managed",
            value="نعم" if role.managed else "لا",
            inline=True,
        )

        return embed

    # =========================================================
    # /channel - !روم
    # =========================================================

    @app_commands.command(
        name="channel",
        description="Show channel information",
    )
    @app_commands.describe(channel="The channel")
    async def slash_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.abc.GuildChannel,
    ):
        await interaction.response.send_message(
            embed=self.create_channel_embed(channel)
        )

    @commands.command(name="روم")
    async def prefix_channel(
        self,
        ctx: commands.Context,
        channel: discord.abc.GuildChannel,
    ):
        await ctx.send(
            embed=self.create_channel_embed(channel)
        )

    def create_channel_embed(
        self,
        channel: discord.abc.GuildChannel,
    ):
        embed = self.embed(
            f"📁 معلومات {channel.name}"
        )

        embed.add_field(
            name="🆔 ID",
            value=f"`{channel.id}`",
            inline=True,
        )

        embed.add_field(
            name="📌 النوع",
            value=f"`{channel.type}`",
            inline=True,
        )

        embed.add_field(
            name="📂 Category",
            value=(
                channel.category.mention
                if channel.category
                else "بدون تصنيف"
            ),
            inline=True,
        )

        return embed

    # =========================================================
    # /membercount - !عدد
    # =========================================================

    @app_commands.command(
        name="membercount",
        description="Show server member count",
    )
    async def slash_membercount(
        self,
        interaction: discord.Interaction,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ هذا الأمر يعمل داخل السيرفر فقط.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"👥 عدد أعضاء السيرفر: `{interaction.guild.member_count or 0}`"
        )

    @commands.command(name="عدد")
    async def prefix_membercount(
        self,
        ctx: commands.Context,
    ):
        if ctx.guild is None:
            await ctx.send(
                "❌ هذا الأمر يعمل داخل السيرفر فقط."
            )
            return

        await ctx.send(
            f"👥 عدد أعضاء السيرفر: `{ctx.guild.member_count or 0}`"
        )

    # =========================================================
    # /servericon - !ايقونة
    # =========================================================

    @app_commands.command(
        name="servericon",
        description="Show server icon",
    )
    async def slash_servericon(
        self,
        interaction: discord.Interaction,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ هذا الأمر يعمل داخل السيرفر فقط.",
                ephemeral=True,
            )
            return

        if not interaction.guild.icon:
            await interaction.response.send_message(
                "❌ السيرفر لا يملك أيقونة.",
                ephemeral=True,
            )
            return

        embed = self.embed(
            "🖼️ Server Icon",
            interaction.guild.name,
        )
        embed.set_image(
            url=interaction.guild.icon.url
        )

        await interaction.response.send_message(
            embed=embed
        )

    @commands.command(name="ايقونة")
    async def prefix_servericon(
        self,
        ctx: commands.Context,
    ):
        if ctx.guild is None:
            await ctx.send(
                "❌ هذا الأمر يعمل داخل السيرفر فقط."
            )
            return

        if not ctx.guild.icon:
            await ctx.send(
                "❌ السيرفر لا يملك أيقونة."
            )
            return

        embed = self.embed(
            "🖼️ Server Icon",
            ctx.guild.name,
        )
        embed.set_image(
            url=ctx.guild.icon.url
        )

        await ctx.send(embed=embed)

    # =========================================================
    # /uptime - !تشغيل
    # =========================================================

    @app_commands.command(
        name="uptime",
        description="Show Zivex uptime",
    )
    async def slash_uptime(
        self,
        interaction: discord.Interaction,
    ):
        await interaction.response.send_message(
            f"⏱️ وقت تشغيل Zivex: `{self.get_uptime()}`"
        )

    @commands.command(name="تشغيل")
    async def prefix_uptime(
        self,
        ctx: commands.Context,
    ):
        await ctx.send(
            f"⏱️ وقت تشغيل Zivex: `{self.get_uptime()}`"
        )

    def get_uptime(self):
        seconds = int(time.time() - self.started_at)

        days, seconds = divmod(seconds, 86400)
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)

        parts = []

        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")

        parts.append(f"{seconds}s")

        return " ".join(parts)

    # =========================================================
    # /about - !عنالبوت
    # =========================================================

    @app_commands.command(
        name="about",
        description="Show information about Zivex",
    )
    async def slash_about(
        self,
        interaction: discord.Interaction,
    ):
        await interaction.response.send_message(
            embed=self.create_about_embed()
        )

    @commands.command(name="عنالبوت")
    async def prefix_about(
        self,
        ctx: commands.Context,
    ):
        await ctx.send(
            embed=self.create_about_embed()
        )

    def create_about_embed(self):
        embed = self.embed(
            "✨ عن Zivex",
            (
                "Zivex هو بوت Discord متعدد الأنظمة "
                "ومصمم لإدارة السيرفرات وتوفير لوحة تحكم احترافية."
            ),
        )

        embed.add_field(
            name="👨‍💻 الصانع",
            value=self.creator_mention(),
            inline=True,
        )

        embed.add_field(
            name="🐍 اللغة",
            value="Python",
            inline=True,
        )

        embed.add_field(
            name="📡 Library",
            value="discord.py",
            inline=True,
        )

        if self.bot.user:
            embed.set_thumbnail(
                url=self.bot.user.display_avatar.url
            )

        embed.set_footer(
            text="Zivex • Professional Discord Bot"
        )

        return embed

    # =========================================================
    # /creator - !صانع
    # =========================================================

    @app_commands.command(
        name="creator",
        description="Show who created Zivex",
    )
    async def slash_creator(
        self,
        interaction: discord.Interaction,
    ):
        embed = self.embed(
            "👨‍💻 صانع Zivex",
            f"تم إنشاء Zivex بواسطة {self.creator_mention()}",
        )

        await interaction.response.send_message(
            embed=embed
        )

    @commands.command(name="صانع")
    async def prefix_creator(
        self,
        ctx: commands.Context,
    ):
        embed = self.embed(
            "👨‍💻 صانع Zivex",
            f"تم إنشاء Zivex بواسطة {self.creator_mention()}",
        )

        await ctx.send(
            embed=embed
        )

    # =========================================================
    # /choose - !اختيار
    # =========================================================

    @app_commands.command(
        name="choose",
        description="Choose randomly between options",
    )
    @app_commands.describe(
        options="Options separated with |"
    )
    async def slash_choose(
        self,
        interaction: discord.Interaction,
        options: str,
    ):
        choices = [
            option.strip()
            for option in options.split("|")
            if option.strip()
        ]

        if len(choices) < 2:
            await interaction.response.send_message(
                "❌ اكتب خيارين على الأقل وافصل بينهم بـ `|`.",
                ephemeral=True,
            )
            return

        selected = random.choice(choices)

        await interaction.response.send_message(
            f"🎯 الاختيار العشوائي: **{selected}**"
        )

    @commands.command(name="اختيار")
    async def prefix_choose(
        self,
        ctx: commands.Context,
        *,
        options: str,
    ):
        choices = [
            option.strip()
            for option in options.split("|")
            if option.strip()
        ]

        if len(choices) < 2:
            await ctx.send(
                "❌ اكتب خيارين على الأقل وافصل بينهم بـ `|`."
            )
            return

        selected = random.choice(choices)

        await ctx.send(
            f"🎯 الاختيار العشوائي: **{selected}**"
        )

    # =========================================================
    # /calculate - !احسب
    # =========================================================

    @app_commands.command(
        name="calculate",
        description="Calculate a simple expression",
    )
    @app_commands.describe(
        expression="Example: 10 + 5 * 2"
    )
    async def slash_calculate(
        self,
        interaction: discord.Interaction,
        expression: str,
    ):
        result = self.safe_calculate(expression)

        if result is None:
            await interaction.response.send_message(
                "❌ العملية غير صالحة.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            f"🧮 النتيجة: `{result}`"
        )

    @commands.command(name="احسب")
    async def prefix_calculate(
        self,
        ctx: commands.Context,
        *,
        expression: str,
    ):
        result = self.safe_calculate(expression)

        if result is None:
            await ctx.send(
                "❌ العملية غير صالحة."
            )
            return

        await ctx.send(
            f"🧮 النتيجة: `{result}`"
        )

    @staticmethod
    def safe_calculate(expression: str):
        allowed = set(
            "0123456789+-*/().% "
        )

        if not expression:
            return None

        if len(expression) > 100:
            return None

        if any(char not in allowed for char in expression):
            return None

        try:
            result = eval(
                expression,
                {
                    "__builtins__": None
                },
                {},
            )
        except Exception:
            return None

        if isinstance(result, (int, float)):
            return result

        return None

    # =========================================================
    # /help - !مساعدة
    # =========================================================

    @app_commands.command(
        name="help",
        description="Show Zivex commands",
    )
    async def slash_help(
        self,
        interaction: discord.Interaction,
    ):
        await interaction.response.send_message(
            embed=self.create_help_embed()
        )

    @commands.command(name="مساعدة")
    async def prefix_help(
        self,
        ctx: commands.Context,
    ):
        await ctx.send(
            embed=self.create_help_embed()
        )

    def create_help_embed(self):
        embed = self.embed(
            "📚 Zivex Help",
            "جميع أوامر قسم الأدوات:",
        )

        embed.add_field(
            name="🛠️ عامة",
            value=(
                "`/ping` • `!بنق`\n"
                "`/bot` • `!بوت`\n"
                "`/help` • `!مساعدة`\n"
                "`/about` • `!عنالبوت`\n"
                "`/creator` • `!صانع`\n"
                "`/uptime` • `!تشغيل`"
            ),
            inline=False,
        )

        embed.add_field(
            name="👤 المستخدمين",
            value=(
                "`/user` • `!عضو`\n"
                "`/avatar` • `!افتار`\n"
                "`/banner` • `!بنر`\n"
                "`/id` • `!ايدي`"
            ),
            inline=False,
        )

        embed.add_field(
            name="🏠 السيرفر",
            value=(
                "`/server` • `!سيرفر`\n"
                "`/servericon` • `!ايقونة`\n"
                "`/membercount` • `!عدد`\n"
                "`/role` • `!رتبة`\n"
                "`/channel` • `!روم`"
            ),
            inline=False,
        )

        embed.add_field(
            name="🎯 أدوات",
            value=(
                "`/choose` • `!اختيار`\n"
                "`/calculate` • `!احسب`"
            ),
            inline=False,
        )

        if self.bot.user:
            embed.set_thumbnail(
                url=self.bot.user.display_avatar.url
            )

        embed.set_footer(
            text="Zivex • Dashboard"
        )

        return embed


async def setup(bot: commands.Bot):
    await bot.add_cog(Utility(bot))
