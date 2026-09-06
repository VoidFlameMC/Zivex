import discord
from discord.ext import commands

from database import db


class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.invite_cache: dict[int, dict[str, dict]] = {}

    # =========================================================
    # Helpers
    # =========================================================

    async def get_settings(self, guild: discord.Guild):
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
                    else None
                ),
            )

            return await db.get_guild(guild.id)

        except Exception as error:
            print(
                f"❌ [WELCOME] Database error "
                f"for {guild.id}: {error}"
            )
            return None

    @staticmethod
    def parse_color(value) -> discord.Color:
        if not value:
            return discord.Color.blurple()

        try:
            value = str(value).strip()

            if value.startswith("#"):
                value = value[1:]

            if value.lower().startswith("0x"):
                value = value[2:]

            if len(value) != 6:
                return discord.Color.blurple()

            return discord.Color(int(value, 16))

        except (ValueError, TypeError):
            return discord.Color.blurple()

    @staticmethod
    def replace_variables(
        text: str,
        member: discord.Member,
        inviter=None,
    ) -> str:
        if not text:
            return ""

        inviter_text = "غير معروف"

        if inviter:
            try:
                inviter_text = inviter.mention
            except Exception:
                inviter_text = getattr(
                    inviter,
                    "name",
                    "غير معروف",
                )

        guild = member.guild

        variables = {
            "{user}": member.mention,
            "{username}": member.display_name,
            "{server}": guild.name,
            "{member_count}": str(
                guild.member_count or 0
            ),
            "{inviter}": str(inviter_text),
        }

        for key, value in variables.items():
            text = text.replace(
                key,
                str(value),
            )

        return text

    @staticmethod
    def get_avatar_url(
        member: discord.Member,
    ):
        try:
            return member.display_avatar.url
        except Exception:
            return None

    # =========================================================
    # Invite System
    # =========================================================

    async def cache_invites(
        self,
        guild: discord.Guild,
    ):
        try:
            invites = await guild.invites()

        except discord.Forbidden:
            self.invite_cache[guild.id] = {}
            print(
                f"⚠️ [WELCOME] Cannot access invites "
                f"in guild {guild.id}."
            )
            return

        except discord.HTTPException as error:
            print(
                f"⚠️ [WELCOME] Could not fetch invites "
                f"for {guild.id}: {error}"
            )
            return

        except Exception as error:
            print(
                f"❌ [WELCOME] Invite cache error "
                f"for {guild.id}: {error}"
            )
            return

        cache = {}

        for invite in invites:
            try:
                cache[invite.code] = {
                    "uses": invite.uses or 0,
                    "inviter_id": (
                        invite.inviter.id
                        if invite.inviter
                        else None
                    ),
                    "max_uses": invite.max_uses or 0,
                    "temporary": bool(
                        invite.temporary
                    ),
                }
            except Exception:
                continue

        self.invite_cache[guild.id] = cache

    async def find_inviter(
        self,
        guild: discord.Guild,
    ):
        previous = self.invite_cache.get(
            guild.id,
            {},
        )

        try:
            invites = await guild.invites()

        except discord.Forbidden:
            return None

        except discord.HTTPException as error:
            print(
                f"⚠️ [WELCOME] Invite lookup failed "
                f"for {guild.id}: {error}"
            )
            return None

        except Exception as error:
            print(
                f"❌ [WELCOME] Invite lookup error "
                f"for {guild.id}: {error}"
            )
            return None

        new_cache = {}
        used_invites = []

        for invite in invites:
            try:
                current_uses = invite.uses or 0

                old_data = previous.get(
                    invite.code,
                    {},
                )

                old_uses = old_data.get(
                    "uses",
                    0,
                )

                inviter_id = (
                    invite.inviter.id
                    if invite.inviter
                    else None
                )

                new_cache[invite.code] = {
                    "uses": current_uses,
                    "inviter_id": inviter_id,
                    "max_uses": invite.max_uses or 0,
                    "temporary": bool(
                        invite.temporary
                    ),
                }

                if current_uses > old_uses:
                    used_invites.append(
                        invite
                    )

            except Exception:
                continue

        self.invite_cache[guild.id] = new_cache

        # -----------------------------------------------------
        # Usually only one invite increases.
        # If multiple increased, use the largest increase.
        # -----------------------------------------------------

        if not used_invites:
            return None

        used_invites.sort(
            key=lambda invite: (
                (invite.uses or 0)
                - previous.get(
                    invite.code,
                    {},
                ).get(
                    "uses",
                    0,
                )
            ),
            reverse=True,
        )

        return used_invites[0].inviter

    # =========================================================
    # Logs
    # =========================================================

    async def send_join_log(
        self,
        member: discord.Member,
        inviter=None,
    ):
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
                    "name": "👥 الأعضاء",
                    "value": (
                        f"`{member.guild.member_count or 0}`"
                    ),
                    "inline": True,
                },
            ]

            if inviter:
                try:
                    inviter_value = (
                        f"{inviter.mention}\n"
                        f"`{inviter.id}`"
                    )
                except Exception:
                    inviter_value = (
                        f"`{getattr(inviter, 'id', 'غير معروف')}`"
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
                title="📥 عضو جديد",
                description=(
                    f"انضم {member.mention} "
                    f"إلى السيرفر."
                ),
                color=discord.Color.green(),
                fields=fields,
                user=member,
            )

        except discord.Forbidden:
            print(
                f"⚠️ [WELCOME] Join log permission error "
                f"for {member.guild.id}"
            )

        except discord.HTTPException as error:
            print(
                f"⚠️ [WELCOME] Join log API error "
                f"for {member.guild.id}: {error}"
            )

        except Exception as error:
            print(
                f"⚠️ [WELCOME] Join log failed "
                f"for {member.guild.id}: {error}"
            )

    async def send_leave_log(
        self,
        member: discord.Member,
    ):
        logs = self.bot.get_cog("Logs")

        if logs is None:
            return

        try:
            leave_method = getattr(
                logs,
                "member_leave",
                None,
            )

            if callable(leave_method):
                await leave_method(member)

        except discord.Forbidden:
            print(
                f"⚠️ [WELCOME] Leave log permission error "
                f"for {member.guild.id}"
            )

        except discord.HTTPException as error:
            print(
                f"⚠️ [WELCOME] Leave log API error "
                f"for {member.guild.id}: {error}"
            )

        except Exception as error:
            print(
                f"⚠️ [WELCOME] Leave log failed "
                f"for {member.guild.id}: {error}"
            )

    # =========================================================
    # Events
    # =========================================================

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            await self.cache_invites(guild)

        print(
            f"✅ [WELCOME] Ready for "
            f"{len(self.bot.guilds)} guild(s)."
        )

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
                    else None
                ),
            )

        except Exception as error:
            print(
                f"⚠️ [WELCOME] Guild setup failed "
                f"for {guild.id}: {error}"
            )

        await self.cache_invites(guild)

    @commands.Cog.listener()
    async def on_guild_remove(
        self,
        guild: discord.Guild,
    ):
        self.invite_cache.pop(
            guild.id,
            None,
        )

    @commands.Cog.listener()
    async def on_invite_create(
        self,
        invite: discord.Invite,
    ):
        if invite.guild:
            await self.cache_invites(
                invite.guild
            )

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
        # Find inviter first.
        # -----------------------------------------------------

        inviter = await self.find_inviter(
            guild
        )

        # -----------------------------------------------------
        # Load settings.
        # -----------------------------------------------------

        settings = await self.get_settings(
            guild
        )

        # -----------------------------------------------------
        # Logs remain independent from welcome.
        # -----------------------------------------------------

        if settings is None:
            await self.send_join_log(
                member,
                inviter,
            )
            return

        # -----------------------------------------------------
        # Welcome disabled.
        # Logs still work.
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
        # Get welcome channel.
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
        except (TypeError, ValueError):
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
        # Content.
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
            or (
                "أهلًا وسهلًا {user} "
                "في {server}! 🎉"
            )
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
        # Embed.
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
        # Thumbnail.
        # -----------------------------------------------------

        if bool(
            settings.get(
                "welcome_thumbnail",
                1,
            )
        ):
            avatar_url = self.get_avatar_url(
                member
            )

            if avatar_url:
                try:
                    embed.set_thumbnail(
                        url=avatar_url
                    )
                except Exception:
                    pass

        # -----------------------------------------------------
        # Footer.
        # -----------------------------------------------------

        try:
            if guild.icon:
                embed.set_footer(
                    text=footer,
                    icon_url=guild.icon.url,
                )
            else:
                embed.set_footer(
                    text=footer
                )

        except Exception:
            try:
                embed.set_footer(
                    text=footer
                )
            except Exception:
                pass

        # -----------------------------------------------------
        # Send welcome message.
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
                f"⚠️ [WELCOME] Missing permissions "
                f"in guild {guild.id}."
            )

        except discord.HTTPException as error:
            print(
                f"⚠️ [WELCOME] Discord API error "
                f"in guild {guild.id}: {error}"
            )

        except Exception as error:
            print(
                f"❌ [WELCOME] Send error "
                f"in guild {guild.id}: {error}"
            )

        # -----------------------------------------------------
        # Central Logs.
        # Always execute even if welcome sending fails.
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
        await self.send_leave_log(
            member
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
