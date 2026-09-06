import discord
from discord import app_commands
from discord.ext import commands


class Utility(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # =====================================================
    # /ping
    # =====================================================

    @app_commands.command(
        name="ping",
        description="Check Zivex response time"
    )
    async def slash_ping(
        self,
        interaction: discord.Interaction
    ):
        latency = round(self.bot.latency * 1000)

        await interaction.response.send_message(
            f"🏓 Pong! `{latency}ms`"
        )

    # !بنق
    @commands.command(name="بنق")
    async def prefix_ping(self, ctx: commands.Context):
        latency = round(self.bot.latency * 1000)

        await ctx.send(
            f"🏓 Pong! `{latency}ms`"
        )

    # =====================================================
    # /bot
    # =====================================================

    @app_commands.command(
        name="bot",
        description="Show information about Zivex"
    )
    async def slash_bot(
        self,
        interaction: discord.Interaction
    ):
        embed = self.create_bot_embed()

        await interaction.response.send_message(
            embed=embed
        )

    # !بوت
    @commands.command(name="بوت")
    async def prefix_bot(self, ctx: commands.Context):
        embed = self.create_bot_embed()

        await ctx.send(
            embed=embed
        )

    def create_bot_embed(self):
        guild_count = len(self.bot.guilds)
        latency = round(self.bot.latency * 1000)

        embed = discord.Embed(
            title="Zivex",
            description=(
                "بوت Discord متعدد الأنظمة "
                "ومخصص لإدارة السيرفرات."
            ),
            color=discord.Color.blurple()
        )

        embed.add_field(
            name="🤖 السيرفرات",
            value=f"`{guild_count}`",
            inline=True
        )

        embed.add_field(
            name="⚡ Ping",
            value=f"`{latency}ms`",
            inline=True
        )

        if self.bot.user:
            embed.set_thumbnail(
                url=self.bot.user.display_avatar.url
            )

        embed.set_footer(
            text="Zivex • Dashboard"
        )

        return embed

    # =====================================================
    # /server
    # =====================================================

    @app_commands.command(
        name="server",
        description="Show information about this server"
    )
    async def slash_server(
        self,
        interaction: discord.Interaction
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ هذا الأمر يعمل داخل السيرفر فقط.",
                ephemeral=True
            )
            return

        embed = self.create_server_embed(
            interaction.guild
        )

        await interaction.response.send_message(
            embed=embed
        )

    # !سيرفر
    @commands.command(name="سيرفر")
    async def prefix_server(self, ctx: commands.Context):
        if ctx.guild is None:
            await ctx.send(
                "❌ هذا الأمر يعمل داخل السيرفر فقط."
            )
            return

        embed = self.create_server_embed(
            ctx.guild
        )

        await ctx.send(
            embed=embed
        )

    def create_server_embed(
        self,
        guild: discord.Guild
    ):
        embed = discord.Embed(
            title=f"معلومات {guild.name}",
            color=discord.Color.blurple()
        )

        embed.add_field(
            name="👥 الأعضاء",
            value=f"`{guild.member_count}`",
            inline=True
        )

        embed.add_field(
            name="🆔 ID",
            value=f"`{guild.id}`",
            inline=True
        )

        embed.add_field(
            name="📁 القنوات",
            value=f"`{len(guild.channels)}`",
            inline=True
        )

        embed.add_field(
            name="🎭 الرتب",
            value=f"`{len(guild.roles)}`",
            inline=True
        )

        if guild.icon:
            embed.set_thumbnail(
                url=guild.icon.url
            )

        embed.set_footer(
            text="Zivex"
        )

        return embed

    # =====================================================
    # /help
    # =====================================================

    @app_commands.command(
        name="help",
        description="Show Zivex commands"
    )
    async def slash_help(
        self,
        interaction: discord.Interaction
    ):
        embed = self.create_help_embed()

        await interaction.response.send_message(
            embed=embed
        )

    # !مساعدة
    @commands.command(name="مساعدة")
    async def prefix_help(self, ctx: commands.Context):
        embed = self.create_help_embed()

        await ctx.send(
            embed=embed
        )

    def create_help_embed(self):
        embed = discord.Embed(
            title="Zivex",
            description="قائمة أوامر Zivex",
            color=discord.Color.blurple()
        )

        embed.add_field(
            name="🛠️ عامة",
            value=(
                "`/ping` • `!بنق`\n"
                "`/bot` • `!بوت`\n"
                "`/server` • `!سيرفر`\n"
                "`/help` • `!مساعدة`"
            ),
            inline=False
        )

        embed.set_footer(
            text="Zivex • Dashboard"
        )

        return embed


async def setup(bot: commands.Bot):
    await bot.add_cog(Utility(bot))
