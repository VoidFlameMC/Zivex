import discord
from discord.ext import commands

from database import db


class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.invite_cache = {}

    # =========================================================
    # إعدادات السيرفر
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

    # =========================================================
    # المتغيرات
    # =========================================================

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
                getattr(
                    inviter,
                    "name",
                    "غير معروف",
                ),
            )

        replacements = {
            "{user}": member.mention,
            "{username}": member.display_name,
            "{server}": guild.name,
            "{member_count}": str(
                guild.member_count or 0
            ),
            "{inviter}": inviter_text,
        }

        for key, value in replacements.items():
            text = text.replace(
                key,
                str(value),
            )

        return text

    # =========================================================
    # الألوان
    # =========================================================

    def parse_color(self, value):
        try:
            if not value:
                return discord.Color.blurple()

            value = (
                str(value)
                .strip()
                .replace("#", "")
            )

            if len(value) != 6:
                return discord.Color.blurple()

            return discord.Color(
                int(value, 16)
            )

        except (
            ValueError,
            TypeError,
        ):
            return discord.Color.blurple()

    # =========================================================
    # تحديث الدعوات
    # =========================================================

    async def cache_invites(
        self,
        guild: discord.Guild,
    ):
        try:
            invites = await guild.invites()

            self.invite_cache[guild.id] = {
                invite.code: {
                    "uses": invite.uses or 0,
                    "inviter_id": (
                        invite.inviter.id
                        if invite.inviter
                        else None
                    ),
                }
                for invite in invites
            }

        except (
            discord.Forbidden,
            discord.HTTPException,
        ):
            self.invite_cache[guild.id] = {}

    # =========================================================
    # معرفة الداعي
    # =========================================================

    async def find_inviter(
        self,
        guild: discord.Guild,
    ):
        try:
            invites = await guild.invites()

        except (
            discord.Forbidden,
            discord.HTTPException,
        ):
            return None

        old_invites = self.invite_cache.get(
            guild.id,
            {},
        )

        used_invite = None

        for invite in invites:
            old_uses = old_invites.get(
                invite.code,
                {},
            ).get(
                "uses",
                0,
            )

            current_uses = invite.uses or 0

            if current_uses > old_uses:
                used_invite = invite
                break

        # تحديث الكاش بعد المقارنة
        self.invite_cache[guild.id] = {
            invite.code: {
                "uses": invite.uses or 0,
                "inviter_id": (
                    invite.inviter.id
                    if invite.inviter
                    else None
                ),
            }
            for invite in invites
        }

        if not used_invite:
            return None

        return used_invite.inviter

    # =========================================================
    # عند تشغيل البوت
    # =========================================================

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            await self.cache_invites(guild)

    # =========================================================
    # عند دخول السيرفر
    # =========================================================

    @commands.Cog.listener()
    async def on_guild_join(
        self,
        guild: discord.Guild,
    ):
        await self.cache_invites(guild)

    # =========================================================
    # عند إنشاء دعوة
    # =========================================================

    @commands.Cog.listener()
    async def on_invite_create(
        self,
        invite: discord.Invite,
    ):
        await self.cache_invites(
            invite.guild
        )

    # =========================================================
    # عند حذف دعوة
    # =========================================================

    @commands.Cog.listener()
    async def on_invite_delete(
        self,
        invite: discord.Invite,
    ):
        await self.cache_invites(
            invite.guild
        )

    # =========================================================
    # دخول عضو
    # =========================================================

    @commands.Cog.listener()
    async def on_member_join(
        self,
        member: discord.Member,
    ):
        guild = member.guild

        settings = await self.get_settings(
            guild
        )

        if not settings:
            return

        # -----------------------------------------------------
        # محاولة معرفة الداعي
        # -----------------------------------------------------

        inviter = await self.find_inviter(
            guild
        )

        # -----------------------------------------------------
        # نظام الترحيب
        # -----------------------------------------------------

        if settings.get(
            "welcome_enabled",
            0,
        ):

            channel_id = settings.get(
                "welcome_channel_id"
            )

            if channel_id:

                channel = guild.get_channel(
                    int(channel_id)
                )

                if isinstance(
                    channel,
                    discord.TextChannel,
                ):

                    title = (
                        settings.get(
                            "welcome_title"
                        )
                        or "👋 أهلًا بك!"
                    )

                    message = (
                        settings.get(
                            "welcome_message"
                        )
                        or (
                            "أهلًا {user} 👋\n"
                            "نورت **{server}**!\n"
                            "أنت العضو رقم **{member_count}**."
                        )
                    )

                    title = self.replace_variables(
                        title,
                        member,
                        inviter,
                    )

                    message = self.replace_variables(
                        message,
                        member,
                        inviter,
                    )

                    embed = discord.Embed(
                        title=title,
                        description=message,
                        color=self.parse_color(
                            settings.get(
                                "welcome_color"
                            )
                        ),
                        timestamp=discord.utils.utcnow(),
                    )

                    if settings.get(
                        "welcome_thumbnail",
                        1,
                    ):
                        embed.set_thumbnail(
                            url=member.display_avatar.url
                        )

                    footer = (
                        settings.get(
                            "welcome_footer"
                        )
                        or f"Zivex • {guild.name}"
                    )

                    footer = self.replace_variables(
                        footer,
                        member,
                        inviter,
                    )

                    embed.set_footer(
                        text=footer
                    )

                    try:
                        await channel.send(
                            content=member.mention,
                            embed=embed,
                        )

                    except (
                        discord.Forbidden,
                        discord.HTTPException,
                    ):
                        pass

        # -----------------------------------------------------
        # السجلات
        # -----------------------------------------------------

        logs = self.bot.get_cog("Logs")

        if logs:
            try:
                await logs.member_join(
                    member
                )

            except Exception as error:
                print(
                    f"⚠️ Welcome join log error: {error}"
                )

    # =========================================================
    # خروج عضو
    # =========================================================

    @commands.Cog.listener()
    async def on_member_remove(
        self,
        member: discord.Member,
    ):
        logs = self.bot.get_cog("Logs")

        if logs:
            try:
                await logs.member_leave(
                    member
                )

            except Exception as error:
                print(
                    f"⚠️ Welcome leave log error: {error}"
                )

    # =========================================================
    # تنظيف الكاش
    # =========================================================

    @commands.Cog.listener()
    async def on_guild_remove(
        self,
        guild: discord.Guild,
    ):
        self.invite_cache.pop(
            guild.id,
            None,
        )


# =========================================================
# Setup
# =========================================================

async def setup(
    bot: commands.Bot,
):
    await bot.add_cog(
        Welcome(bot)
    )
