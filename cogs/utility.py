import discord
from discord import app_commands
from discord.ext import commands


class Utility(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # =========================================================
    # Helpers
    # =========================================================

    @staticmethod
    def create_embed(title: str, description: str = ""):
        return discord.Embed(
            title=title,
            description=description,
            color=discord.Color.blurple(),
        )

    # =========================================================
    # /ping
    # !بنق
    # =========================================================

    @app_commands.command(
        name="ping",
        description="Check Zivex response time",
    )
    async def slash_ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)

        await interaction.response.send_message(
            f"🏓 Pong! `{latency}ms`"
        )

    @commands.command(name="بنق")
    async def prefix_ping(self, ctx: commands.Context):
        latency = round(self.bot.latency * 1000)

        await ctx.send(
            f"🏓 Pong! `{latency}ms`"
        )

    # =========================================================
    # /bot
    # !بوت
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

        embed = self.create_embed(
            title="🤖 Zivex",
            description=(
                "بوت Discord متعدد الأنظمة "
                "ومخصص لإدارة السيرفرات."
            ),
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
    # /server
    # !سيرفر
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
        embed = self.create_embed(
            title=f"📊 معلومات {guild.name}"
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

        if guild.icon:
            embed.set_thumbnail(
                url=guild.icon.url
            )

        embed.set_footer(
            text="Zivex"
        )

        return embed

    # =========================================================
    # /help
    # !مساعدة
    # =========================================================

    @app_commands.command(
        name="help",
        description="Show Zivex commands",
    )
    async def slash_help(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=self.create_help_embed()
        )

    @commands.command(name="مساعدة")
    async def prefix_help(self, ctx: commands.Context):
        await ctx.send(
            embed=self.create_help_embed()
        )

    def create_help_embed(self):
        embed = self.create_embed(
            title="📚 Zivex",
            description="قائمة أوامر Zivex",
        )

        embed.add_field(
            name="🛠️ الأوامر العامة",
            value=(
                "`/ping` • `!بنق`\n"
                "`/bot` • `!بوت`\n"
                "`/server` • `!سيرفر`\n"
                "`/help` • `!مساعدة`"
            ),
            inline=False,
        )

        embed.set_footer(
            text="Zivex • Dashboard"
        )

        return embed


async def setup(bot: commands.Bot):
    await bot.add_cog(Utility(bot))
