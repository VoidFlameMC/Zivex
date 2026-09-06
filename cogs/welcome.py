import discord
from discord import app_commands
from discord.ext import commands

from database import db


class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # =========================================================
    # أدوات النظام
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

    def replace_variables(
        self,
        text: str,
        member: discord.Member,
        inviter=None,
    ):
        if not text:
            return ""

        guild = member.guild

        inviter_text = "غير معروف"

        if inviter:
            inviter_text = getattr(
                inviter,
                "mention",
                getattr(inviter, "name", "غير معروف"),
            )

        replacements = {
            "{user}": member.mention,
            "{username}": member.display_name,
            "{server}": guild.name,
            "{member_count}": str(guild.member_count or 0),
            "{inviter}": inviter_text,
        }

        for key, value in replacements.items():
            text = text.replace(key, str(value))

        return text

    def parse_color(self, value):
        try:
            if not value:
                return discord.Color.blurple()

            value = str(value).strip().replace("#", "")

            if len(value) != 6:
                return discord.Color.blurple()

            return discord.Color(int(value, 16))

        except (ValueError, TypeError):
            return discord.Color.blurple()

    # =========================================================
    # معرفة الداعي
    # =========================================================

    async def find_inviter(self, guild: discord.Guild, member):
        """
        يحاول معرفة الشخص الذي دعا العضو عن طريق Invite Tracking.

        ملاحظة:
        Discord لا يعطي البوت الداعي بشكل مباشر عند دخول العضو،
        لذلك نقارن استخدامات الدعوات قبل/بعد الدخول.
        """

        try:
            invites
