import discord
from discord.ext import commands

from database import db


class Logs(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # =========================================================
    # Settings
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
    # Get Logs Channel
    # =========================================================

    async def get_logs_channel(
        self,
        guild: discord.Guild,
    ):
        settings = await self.get_settings(guild)

        if not settings:
            return None

        if not settings.get("logs_enabled", 0):
            return None

        channel_id = settings.get(
            "logs_channel_id"
        )

        if not channel_id:
            return None

        try:
            channel_id = int(channel_id)
        except (TypeError, ValueError):
            return None

        channel = guild.get_channel(channel_id)

        if not isinstance(
            channel,
            discord.TextChannel,
        ):
            return None

        return channel

    # =========================================================
    # Send Log
    # =========================================================

    async def send_log(
        self,
        guild: discord.Guild,
        title: str,
        description: str,
        color: discord.Color = discord.Color.blurple(),
        fields: list | None = None,
        user: discord.abc.User | None = None,
    ):
        try:
            channel = await self.get_logs_channel(
                guild
            )

            if channel is None:
                return False

            embed = discord.Embed(
                title=title,
                description=description,
                color=color,
                timestamp=discord.utils.utcnow(),
            )

            if fields:
                for field in fields:
                    if not isinstance(
                        field,
                        dict,
                    ):
                        continue

                    name = field.get(
                        "name",
                        "معلومات",
                    )

                    value = field.get(
                        "value",
                        "-",
                    )

                    inline = field.get(
                        "inline",
                        True,
                    )

                    embed.add_field(
                        name=str(name)[:256],
                        value=str(value)[:1024],
                        inline=bool(inline),
                    )

            if user is not None:
                embed.set_author(
                    name=(
                        getattr(
                            user,
                            "display_name",
                            None,
                        )
                        or getattr(
                            user,
                            "name",
                            "Unknown",
                        )
                    ),
                    icon_url=(
                        user.display_avatar.url
                    ),
                )

            if guild.icon:
                embed.set_footer(
                    text=f"Zivex • {guild.name}",
                    icon_url=guild.icon.url,
                )
            else:
                embed.set_footer(
                    text=f"Zivex • {guild.name}"
                )

            await channel.send(
                embed=embed
            )

            return True

        except discord.Forbidden:
            return False

        except discord.HTTPException as error:
            print(
                f"⚠️ Logs HTTP error "
                f"in {guild.id}: {error}"
            )
            return False

        except Exception as error:
            print(
                f"❌ Logs error "
                f"in {guild.id}: {error}"
            )
            return False

    # =========================================================
    # Member Join
    # =========================================================

    async def member_join(
        self,
        member: discord.Member,
    ):
        await self.send_log(
            guild=member.guild,
            title="📥 عضو دخل السيرفر",
            description=(
                f"دخل {member.mention} إلى السيرفر."
            ),
            color=discord.Color.green(),
            user=member,
            fields=[
                {
                    "name": "👤 العضو",
                    "value": (
                        f"{member.mention}\n"
                        f"`{member.id}`"
                    ),
                },
                {
                    "name": "👥 عدد الأعضاء",
                    "value": (
                        f"`{member.guild.member_count or 0}`"
                    ),
                },
            ],
        )

    # =========================================================
    # Member Leave
    # =========================================================

    async def member_leave(
        self,
        member: discord.Member,
    ):
        await self.send_log(
            guild=member.guild,
            title="📤 عضو خرج من السيرفر",
            description=(
                f"خرج **{member}** من السيرفر."
            ),
            color=discord.Color.red(),
            user=member,
            fields=[
                {
                    "name": "👤 العضو",
                    "value": (
                        f"`{member}`\n"
                        f"`{member.id}`"
                    ),
                },
                {
                    "name": "👥 عدد الأعضاء",
                    "value": (
                        f"`{member.guild.member_count or 0}`"
                    ),
                },
            ],
        )

    # =========================================================
    # Level Up
    # =========================================================

    async def level_up(
        self,
        member: discord.Member,
        level: int,
        xp: int,
    ):
        await self.send_log(
            guild=member.guild,
            title="⭐ Level Up",
            description=(
                f"ارتفع مستوى {member.mention}!"
            ),
            color=discord.Color.gold(),
            user=member,
            fields=[
                {
                    "name": "👤 العضو",
                    "value": member.mention,
                },
                {
                    "name": "⭐ المستوى",
                    "value": f"`{level}`",
                },
                {
                    "name": "✨ XP",
                    "value": f"`{xp}`",
                },
            ],
        )

    # =========================================================
    # Ticket Created
    # =========================================================

    async def ticket_created(
        self,
        member: discord.Member,
        channel: discord.TextChannel,
    ):
        await self.send_log(
            guild=member.guild,
            title="🎫 تم فتح تذكرة",
            description=(
                f"تم فتح تذكرة بواسطة {member.mention}."
            ),
            color=discord.Color.green(),
            user=member,
            fields=[
                {
                    "name": "👤 صاحب التذكرة",
                    "value": member.mention,
                },
                {
                    "name": "🎫 التذكرة",
                    "value": channel.mention,
                },
            ],
        )

    # =========================================================
    # Ticket Closed
    # =========================================================

    async def ticket_closed(
        self,
        guild: discord.Guild,
        channel_name: str,
        user: discord.abc.User | None = None,
    ):
        await self.send_log(
            guild=guild,
            title="🔒 تم إغلاق تذكرة",
            description=(
                f"تم إغلاق التذكرة `{channel_name}`."
            ),
            color=discord.Color.red(),
            user=user,
            fields=[
                {
                    "name": "🎫 التذكرة",
                    "value": f"`{channel_name}`",
                },
            ],
        )

    # =========================================================
    # Application
    # =========================================================

    async def application_received(
        self,
        member: discord.Member,
    ):
        await self.send_log(
            guild=member.guild,
            title="📝 تقديم جديد",
            description=(
                f"تم استلام تقديم جديد من "
                f"{member.mention}."
            ),
            color=discord.Color.blurple(),
            user=member,
            fields=[
                {
                    "name": "👤 المتقدم",
                    "value": member.mention,
                },
            ],
        )

    # =========================================================
    # Moderation
    # =========================================================

    async def moderation_action(
        self,
        guild: discord.Guild,
        action: str,
        member: discord.abc.User,
        moderator: discord.abc.User | None = None,
        reason: str | None = None,
    ):
        colors = {
            "warn": discord.Color.orange(),
            "kick": discord.Color.red(),
            "ban": discord.Color.dark_red(),
            "mute": discord.Color.dark_gray(),
            "unmute": discord.Color.green(),
        }

        titles = {
            "warn": "⚠️ تحذير عضو",
            "kick": "👢 طرد عضو",
            "ban": "🔨 حظر عضو",
            "mute": "🔇 إسكات عضو",
            "unmute": "🔊 إلغاء إسكات عضو",
        }

        action_title = titles.get(
            action,
            "🛡️ إجراء إداري",
        )

        action_color = colors.get(
            action,
            discord.Color.blurple(),
        )

        fields = [
            {
                "name": "👤 العضو",
                "value": (
                    f"{getattr(member, 'mention', member)}\n"
                    f"`{member.id}`"
                ),
            }
        ]

        if moderator:
            fields.append(
                {
                    "name": "👮 المسؤول",
                    "value": (
                        f"{getattr(moderator, 'mention', moderator)}"
                    ),
                }
            )

        if reason:
            fields.append(
                {
                    "name": "📝 السبب",
                    "value": str(reason)[:1024],
                }
            )

        await self.send_log(
            guild=guild,
            title=action_title,
            description=(
                f"تم تنفيذ الإجراء: "
                f"**{action}**"
            ),
            color=action_color,
            fields=fields,
            user=moderator,
        )

    # =========================================================
    # Dashboard Change
    # =========================================================

    async def dashboard_change(
        self,
        guild: discord.Guild,
        setting: str,
        value: str,
        user: discord.abc.User | None = None,
    ):
        await self.send_log(
            guild=guild,
            title="⚙️ تغيير إعدادات",
            description=(
                "تم تعديل إعداد من لوحة التحكم."
            ),
            color=discord.Color.blurple(),
            user=user,
            fields=[
                {
                    "name": "⚙️ الإعداد",
                    "value": f"`{setting}`",
                },
                {
                    "name": "🔧 القيمة الجديدة",
                    "value": str(value)[:1024],
                },
            ],
        )

    # =========================================================
    # Cog Ready
    # =========================================================

    @commands.Cog.listener()
    async def on_ready(self):
        print("✅ Logs system loaded.")


async def setup(
    bot: commands.Bot,
):
    await bot.add_cog(
        Logs(bot)
    )
