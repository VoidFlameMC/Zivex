import discord
from discord.ext import commands

from database import db


class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Invite cache:
        # {
        #     guild_id: {
        #         invite_code: {
        #             "uses": int,
        #             "inviter_id": int | None
        #         }
        #     }
        # }
        self.invite_cache: dict[int, dict] = {}

    # =========================================================
    # Settings
    # =========================================================

    async def get_settings(
        self,
        guild: discord.Guild,
    ):
        try:
            settings = await db.get_guild(guild.id)

            if settings:
                return settings

            await db.ensure_guild(
                guild_id=guild.id,
                guild_name=guild.name,
                guild_icon=(
                    str(guild.icon.url)
                    if guild.icon
                    else ""
                ),
            )

            return await db.get_guild(guild.id)

        except Exception as error:
            print(
                f"❌ Welcome settings error "
                f"({guild.id}): {error}"
            )
            return None

    # =========================================================
    # Variables
    # =========================================================

    def replace_variables(
        self,
        text: str,
        member: discord.Member,
        inviter=None,
    ) -> str:
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
    # Color
    # =========================================================

    def parse_color(
        self,
        value,
    ) -> discord.Color:
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
    # Invite Cache
    # =========================================================

    async def cache_invites(
        self,
        guild: discord.Guild,
    ) -> None:
        try:
            invites = await guild.invites()

        except discord.Forbidden:
            self.invite_cache[guild.id] = {}
            return

        except discord.HTTPException as error:
            print(
                f"⚠️ Failed to fetch invites "
                f"for {guild.id}: {error}"
            )
            return

        except Exception as error:
            print(
                f"❌ Invite cache error "
                f"for {guild.id}: {error}"
            )
            return

        cache = {}

        for invite in invites:
            cache[invite.code] = {
                "uses": invite.uses or 0,
                "inviter_id": (
                    invite.inviter.id
                    if invite.inviter
                    else None
                ),
            }

        self.invite_cache[guild.id] = cache

    # =========================================================
    # Find Inviter
    # =========================================================

    async def find_inviter(
        self,
        guild: discord.Guild,
    ):
        old_cache = self.invite_cache.get(
            guild.id,
            {},
        )

        try:
            invites = await guild.invites()

        except discord.Forbidden:
            return None

        except discord.HTTPException as error:
            print(
                f"⚠️ Invite lookup HTTP error "
                f"for {guild.id}: {error}"
            )
            return None

        except Exception as error:
            print(
                f"❌ Invite lookup error "
                f"for {guild.id}: {error}"
            )
            return None

        new_cache = {}
        used_invite = None

        for invite in invites:
            current_uses = invite.uses or 0

            old_data = old_cache.get(
                invite.code,
                {},
            )

            old_uses = old_data.get(
                "uses",
                0,
            )

            new_cache[invite.code] = {
                "uses": current_uses,
                "inviter_id": (
                    invite.inviter.id
                    if invite.inviter
                    else None
                ),
            }

            if current_uses > old_uses:
                used_invite = invite

        self.invite_cache[guild.id] = new_cache

        if used_invite is None:
            return None

        return used_invite.inviter

    # =========================================================
    # Logs
    # =========================================================

    async def send_join_log(
        self,
        member: discord.Member,
        inviter=None,
    ) -> None:
        logs = self.bot.get_cog("Logs")

        if logs is None:
            return

        try:
            fields = [
                {
                    "name": "👤 العضو",
                    "value": (
                        f"{member.mention}\n"
                        f"`{member.id}`"
                    ),
                    "inline": True,
                },
                {
                    "name": "👥 عدد الأعضاء",
                    "value": (
                        f"`{member.guild.member_count or 0}`"
                    ),
                    "inline": True,
                },
            ]

            if inviter:
                inviter_value = (
                    f"{inviter.mention}\n"
                    f"`{inviter.id}`"
                )
            else:
                inviter_value = "غير معروف"

            fields.append(
                {
                    "name": "📨 الداعي",
                    "value": inviter_value,
                    "inline": True,
                }
            )

            await logs.send_log(
                guild=member.guild,
                title="📥 عضو دخل السيرفر",
                description=(
                    f"دخل {member.mention} "
                    f"إلى السيرفر."
                ),
                color=discord.Color.green(),
                fields=fields,
                user=member,
            )

        except Exception as error:
            print(
                f"⚠️ Join log error "
                f"({member.guild.id}): {error}"
            )

    # =========================================================
    # Bot Ready
    # =========================================================

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            await self.cache_invites(guild)

        print(
            f"✅ Welcome system ready "
            f"for {len(self.bot.guilds)} guild(s)."
        )

    # =========================================================
    # Guild Join
    # =========================================================

    @commands.Cog.listener()
    async def on_guild_join(
        self,
        guild: discord.Guild,
    ):
        try:
            await db.ensure_guild(
                guild_id=guild.id,
                guild_name=guild.name,
                guild_icon=(
                    str(guild.icon.url)
                    if guild.icon
                    else ""
                ),
            )

        except Exception as error:
            print(
                f"⚠️ Guild database error "
                f"({guild.id}): {error}"
            )

        await self.cache_invites(guild)

    # =========================================================
    # Guild Remove
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
    # Invite Create
    # =========================================================

    @commands.Cog.listener()
    async def on_invite_create(
        self,
        invite: discord.Invite,
    ):
        if invite.guild:
            await self.cache_invites(
                invite.guild
            )

    # =========================================================
    # Invite Delete
    # =========================================================

    @commands.Cog.listener()
    async def on_invite_delete(
        self,
        invite: discord.Invite,
    ):
        if invite.guild:
            await self.cache_invites(
                invite.guild
            )

    # =========================================================
    # Member Join
    # =========================================================

    @commands.Cog.listener()
    async def on_member_join(
        self,
        member: discord.Member,
    ):
        guild = member.guild

        # -----------------------------------------------------
        # Find inviter
        # -----------------------------------------------------

        inviter = await self.find_inviter(
            guild
        )

        # -----------------------------------------------------
        # Database settings
        # -----------------------------------------------------

        settings = await self.get_settings(
            guild
        )

        # -----------------------------------------------------
        # Even if database/settings fail,
        # don't crash the bot.
        # -----------------------------------------------------

        if settings is None:
            await self.send_join_log(
                member,
                inviter,
            )
            return

        # -----------------------------------------------------
        # Welcome enabled?
        # -----------------------------------------------------

        if not bool(
            settings.get(
                "welcome_enabled",
                0,
            )
        ):
            await self.send_join_log(
                member,
                inviter,
            )
            return

        # -----------------------------------------------------
        # Welcome channel
        # -----------------------------------------------------

        channel_id = settings.get(
            "welcome_channel_id"
        )

        try:
            channel_id = (
                int(channel_id)
                if channel_id
                else None
            )

        except (
            TypeError,
            ValueError,
        ):
            channel_id = None

        if channel_id is None:
            await self.send_join_log(
                member,
                inviter,
            )
            return

        channel = guild.get_channel(
            channel_id
        )

        if not isinstance(
            channel,
            discord.TextChannel,
        ):
            await self.send_join_log(
                member,
                inviter,
            )
            return

        # -----------------------------------------------------
        # Message
        # -----------------------------------------------------

        title = (
            settings.get(
                "welcome_title"
            )
            or "مرحبًا بك في {server}"
        )

        message = (
            settings.get(
                "welcome_message"
            )
            or "أهلًا وسهلًا {user} في {server}! 🎉"
        )

        footer = (
            settings.get(
                "welcome_footer"
            )
            or "Zivex • {server}"
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

        footer = self.replace_variables(
            footer,
            member,
            inviter,
        )

        # -----------------------------------------------------
        # Embed
        # -----------------------------------------------------

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

        # -----------------------------------------------------
        # Thumbnail
        # -----------------------------------------------------

        if bool(
            settings.get(
                "welcome_thumbnail",
                1,
            )
        ):
            try:
                embed.set_thumbnail(
                    url=member.display_avatar.url
                )
            except Exception:
                pass

        # -----------------------------------------------------
        # Footer
        # -----------------------------------------------------

        if guild.icon:
            try:
                embed.set_footer(
                    text=footer,
                    icon_url=guild.icon.url,
                )
            except Exception:
                embed.set_footer(
                    text=footer
                )
        else:
            embed.set_footer(
                text=footer
            )

        # -----------------------------------------------------
        # Send welcome
        # -----------------------------------------------------

        try:
            await channel.send(
                content=member.mention,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(
                    users=True,
                    roles=False,
                    everyone=False,
                ),
            )

        except discord.Forbidden:
            print(
                f"⚠️ Missing permission to send "
                f"welcome in guild {guild.id}."
            )

        except discord.HTTPException as error:
            print(
                f"⚠️ Welcome HTTP error "
                f"({guild.id}): {error}"
            )

        except Exception as error:
            print(
                f"❌ Welcome send error "
                f"({guild.id}): {error}"
            )

        # -----------------------------------------------------
        # Central Logs
        # -----------------------------------------------------

        await self.send_join_log(
            member,
            inviter,
        )

    # =========================================================
    # Member Leave
    # =========================================================

    @commands.Cog.listener()
    async def on_member_remove(
        self,
        member: discord.Member,
    ):
        logs = self.bot.get_cog("Logs")

        if logs is None:
            return

        try:
            await logs.member_leave(
                member
            )

        except Exception as error:
            print(
                f"⚠️ Leave log error "
                f"({member.guild.id}): {error}"
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
