import asyncio
import random
import time
from typing import Optional

import discord
from discord.ext import commands

from database import db


class LevelResetConfirmView(discord.ui.View):
    def __init__(self, cog, author_id: int):
        super().__init__(timeout=30)
        self.cog = cog
        self.author_id = author_id
        self.confirmed = False

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ هذا التأكيد ليس لك.",
                ephemeral=True,
            )
            return False

        return True

    @discord.ui.button(
        label="تأكيد التصفير",
        style=discord.ButtonStyle.danger,
        emoji="🗑️",
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        self.confirmed = True

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            content="⏳ جاري تصفير مستويات جميع الأعضاء...",
            view=self,
        )

        count = await self.cog.reset_all_users(
            interaction.guild
        )

        await interaction.edit_original_response(
            content=(
                f"✅ تم تصفير مستويات **{count}** عضو."
            ),
            view=self,
        )

        self.stop()

    @discord.ui.button(
        label="إلغاء",
        style=discord.ButtonStyle.secondary,
        emoji="❌",
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            content="❌ تم إلغاء العملية.",
            view=self,
        )

        self.stop()


class Levels(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.cooldowns: dict[tuple[int, int], float] = {}

        self._table_ready = False
        self._table_lock = asyncio.Lock()

    # =========================================================
    # Database
    # =========================================================

    async def ensure_table(self):
        if self._table_ready:
            return

        async with self._table_lock:
            if self._table_ready:
                return

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS user_levels (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    xp INTEGER NOT NULL DEFAULT 0,
                    level INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (guild_id, user_id)
                )
                """
            )

            await db.commit()

            self._table_ready = True

    async def get_settings(
        self,
        guild: discord.Guild,
    ):
        try:
            settings = await db.get_guild(
                guild.id
            )

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

            return await db.get_guild(
                guild.id
            )

        except Exception as error:
            print(
                f"❌ [LEVELS] Database error "
                f"for {guild.id}: {error}"
            )
            return None

    # =========================================================
    # Helpers
    # =========================================================

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

            return discord.Color(
                int(value, 16)
            )

        except (ValueError, TypeError):
            return discord.Color.blurple()

    @staticmethod
    def positive_int(
        value,
        default: int,
        minimum: int = 1,
        maximum: int = 10_000_000,
    ) -> int:
        try:
            value = int(value)
        except (TypeError, ValueError):
            return default

        return max(
            minimum,
            min(value, maximum),
        )

    async def get_user_data(
        self,
        guild_id: int,
        user_id: int,
    ) -> dict:
        await self.ensure_table()

        cursor = await db.execute(
            """
            SELECT xp, level
            FROM user_levels
            WHERE guild_id = ?
              AND user_id = ?
            """,
            (
                guild_id,
                user_id,
            ),
        )

        row = await cursor.fetchone()

        if row is None:
            await db.execute(
                """
                INSERT INTO user_levels (
                    guild_id,
                    user_id,
                    xp,
                    level
                )
                VALUES (?, ?, 0, 0)
                """,
                (
                    guild_id,
                    user_id,
                ),
            )

            await db.commit()

            return {
                "xp": 0,
                "level": 0,
            }

        return {
            "xp": int(row[0] or 0),
            "level": int(row[1] or 0),
        }

    async def set_user_data(
        self,
        guild_id: int,
        user_id: int,
        xp: int,
        level: int,
    ):
        await self.ensure_table()

        await db.execute(
            """
            INSERT INTO user_levels (
                guild_id,
                user_id,
                xp,
                level
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id)
            DO UPDATE SET
                xp = excluded.xp,
                level = excluded.level
            """,
            (
                guild_id,
                user_id,
                max(0, int(xp)),
                max(0, int(level)),
            ),
        )

        await db.commit()

    def xp_required(
        self,
        settings,
    ) -> int:
        return self.positive_int(
            settings.get(
                "level_xp_per_level",
                100,
            ),
            100,
            minimum=1,
            maximum=1_000_000,
        )

    # =========================================================
    # XP
    # =========================================================

    async def add_xp(
        self,
        member: discord.Member,
        amount: int,
        announce: bool = True,
    ) -> tuple[int, int, bool]:
        settings = await self.get_settings(
            member.guild
        )

        if settings is None:
            return 0, 0, False

        data = await self.get_user_data(
            member.guild.id,
            member.id,
        )

        old_level = data["level"]
        old_xp = data["xp"]

        xp_per_level = self.xp_required(
            settings
        )

        new_xp = max(
            0,
            old_xp + int(amount),
        )

        new_level = new_xp // xp_per_level

        leveled_up = (
            new_level > old_level
        )

        await self.set_user_data(
            member.guild.id,
            member.id,
            new_xp,
            new_level,
        )

        if leveled_up and announce:
            await self.send_level_up(
                member,
                new_level,
                new_xp,
                settings,
            )

        return (
            new_xp,
            new_level,
            leveled_up,
        )

    async def remove_xp(
        self,
        member: discord.Member,
        amount: int,
    ) -> tuple[int, int]:
        settings = await self.get_settings(
            member.guild
        )

        if settings is None:
            return 0, 0

        data = await self.get_user_data(
            member.guild.id,
            member.id,
        )

        xp_per_level = self.xp_required(
            settings
        )

        new_xp = max(
            0,
            data["xp"] - int(amount),
        )

        new_level = new_xp // xp_per_level

        await self.set_user_data(
            member.guild.id,
            member.id,
            new_xp,
            new_level,
        )

        return (
            new_xp,
            new_level,
        )

    # =========================================================
    # Level Up Message
    # =========================================================

    async def send_level_up(
        self,
        member: discord.Member,
        level: int,
        xp: int,
        settings,
    ):
        title = (
            settings.get(
                "level_title"
            )
            or "🎉 مستوى جديد!"
        )

        message = (
            settings.get(
                "level_message"
            )
            or (
                "مبروك {user}! وصلت إلى "
                "المستوى **{level}**."
            )
        )

        footer = (
            settings.get(
                "level_footer"
            )
            or "Zivex • Levels"
        )

        title = self.replace_variables(
            title,
            member,
            level,
            xp,
        )

        message = self.replace_variables(
            message,
            member,
            level,
            xp,
        )

        footer = self.replace_variables(
            footer,
            member,
            level,
            xp,
        )

        embed = discord.Embed(
            title=title,
            description=message,
            color=self.parse_color(
                settings.get(
                    "level_color"
                )
            ),
            timestamp=discord.utils.utcnow(),
        )

        if bool(
            settings.get(
                "level_thumbnail",
                1,
            )
        ):
            try:
                embed.set_thumbnail(
                    url=member.display_avatar.url
                )
            except Exception:
                pass

        try:
            if member.guild.icon:
                embed.set_footer(
                    text=footer,
                    icon_url=member.guild.icon.url,
                )
            else:
                embed.set_footer(
                    text=footer
                )
        except Exception:
            embed.set_footer(
                text=footer
            )

        channel_id = settings.get(
            "level_channel_id"
        )

        try:
            channel_id = int(channel_id)
        except (
            TypeError,
            ValueError,
        ):
            channel_id = None

        channel = (
            member.guild.get_channel(
                channel_id
            )
            if channel_id
            else None
        )

        if not isinstance(
            channel,
            discord.TextChannel,
        ):
            return

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
                f"⚠️ [LEVELS] Missing permissions "
                f"in guild {member.guild.id}."
            )

        except discord.HTTPException as error:
            print(
                f"⚠️ [LEVELS] Discord API error "
                f"in guild {member.guild.id}: {error}"
            )

        except Exception as error:
            print(
                f"❌ [LEVELS] Level-up message error: "
                f"{error}"
            )

        # -----------------------------------------------------
        # Logs
        # -----------------------------------------------------

        logs = self.bot.get_cog("Logs")

        if logs:
            try:
                await logs.level_up(
                    member,
                    level,
                    xp,
                )
            except Exception as error:
                print(
                    f"⚠️ [LEVELS] Log error: {error}"
                )

    @staticmethod
    def replace_variables(
        text: str,
        member: discord.Member,
        level: int,
        xp: int,
    ) -> str:
        if not text:
            return ""

        variables = {
            "{user}": member.mention,
            "{username}": member.display_name,
            "{server}": member.guild.name,
            "{level}": str(level),
            "{xp}": str(xp),
            "{member_count}": str(
                member.guild.member_count or 0
            ),
        }

        for key, value in variables.items():
            text = text.replace(
                key,
                str(value),
            )

        return text

    # =========================================================
    # Message XP
    # =========================================================

    @commands.Cog.listener()
    async def on_message(
        self,
        message: discord.Message,
    ):
        if message.author.bot:
            return

        if not message.guild:
            return

        if not isinstance(
            message.author,
            discord.Member,
        ):
            return

        settings = await self.get_settings(
            message.guild
        )

        if settings is None:
            return

        if not bool(
            settings.get(
                "level_enabled",
                0,
            )
        ):
            return

        # -----------------------------------------------------
        # Avoid bots/webhooks.
        # -----------------------------------------------------

        if message.webhook_id:
            return

        # -----------------------------------------------------
        # Channel restriction.
        # -----------------------------------------------------

        configured_channel = settings.get(
            "level_channel_id"
        )

        if configured_channel:
            try:
                configured_channel = int(
                    configured_channel
                )
            except (
                TypeError,
                ValueError,
            ):
                configured_channel = None

            # The configured level channel is for
            # announcements, not XP restriction.
            # Therefore XP still works in all channels.

        # -----------------------------------------------------
        # Cooldown.
        # -----------------------------------------------------

        cooldown = self.positive_int(
            settings.get(
                "level_cooldown",
                60,
            ),
            60,
            minimum=1,
            maximum=86_400,
        )

        key = (
            message.guild.id,
            message.author.id,
        )

        now = time.monotonic()

        last = self.cooldowns.get(
            key,
            0,
        )

        if now - last < cooldown:
            return

        self.cooldowns[key] = now

        # -----------------------------------------------------
        # XP range.
        # -----------------------------------------------------

        xp_min = self.positive_int(
            settings.get(
                "level_xp_min",
                15,
            ),
            15,
            minimum=1,
            maximum=10_000,
        )

        xp_max = self.positive_int(
            settings.get(
                "level_xp_max",
                25,
            ),
            25,
            minimum=1,
            maximum=10_000,
        )

        if xp_max < xp_min:
            xp_min, xp_max = (
                xp_max,
                xp_min,
            )

        amount = random.randint(
            xp_min,
            xp_max,
        )

        await self.add_xp(
            message.author,
            amount,
        )

    # =========================================================
    # Admin Checks
    # =========================================================

    async def ensure_manager(
        self,
        ctx: commands.Context,
    ) -> bool:
        if not isinstance(
            ctx.author,
            discord.Member,
        ):
            return False

        if ctx.guild is None:
            return False

        if ctx.author.guild_permissions.manage_guild:
            return True

        if await self.bot.is_owner(
            ctx.author
        ):
            return True

        await ctx.send(
            "❌ تحتاج صلاحية **إدارة السيرفر** لاستخدام هذا الأمر."
        )

        return False

    async def ensure_slash_manager(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        if interaction.guild is None:
            return False

        member = interaction.user

        if (
            isinstance(
                member,
                discord.Member,
            )
            and member.guild_permissions.manage_guild
        ):
            return True

        if await self.bot.is_owner(
            member
        ):
            return True

        if not interaction.response.is_done():
            await interaction.response.send_message(
                "❌ تحتاج صلاحية **إدارة السيرفر**.",
                ephemeral=True,
            )

        return False

    # =========================================================
    # Commands Group - Arabic
    # =========================================================

    @commands.group(
        name="ليفل",
        invoke_without_command=True,
    )
    async def level_group(
        self,
        ctx: commands.Context,
        member: Optional[discord.Member] = None,
    ):
        member = member or ctx.author

        data = await self.get_user_data(
            ctx.guild.id,
            member.id,
        )

        settings = await self.get_settings(
            ctx.guild
        )

        xp_per_level = (
            self.xp_required(settings)
            if settings
            else 100
        )

        await ctx.send(
            (
                f"📊 **معلومات مستوى {member.display_name}**\n"
                f"⭐ المستوى: `{data['level']}`\n"
                f"✨ XP: `{data['xp']}`\n"
                f"📈 XP للمستوى التالي: "
                f"`{xp_per_level}`"
            )
        )

    @level_group.command(
        name="اضافة",
    )
    async def level_add(
        self,
        ctx: commands.Context,
        member: discord.Member,
        amount: int,
    ):
        if not await self.ensure_manager(ctx):
            return

        if amount <= 0:
            await ctx.send(
                "❌ يجب أن يكون مقدار الـXP أكبر من صفر."
            )
            return

        if amount > 10_000_000:
            await ctx.send(
                "❌ الحد الأقصى هو `10,000,000 XP`."
            )
            return

        xp, level, leveled = await self.add_xp(
            member,
            amount,
            announce=False,
        )

        await ctx.send(
            (
                f"✅ تمت إضافة `{amount:,} XP` إلى "
                f"{member.mention}.\n"
                f"⭐ المستوى: `{level}`\n"
                f"✨ XP: `{xp:,}`"
            )
        )

    @level_group.command(
        name="حذف",
    )
    async def level_remove(
        self,
        ctx: commands.Context,
        member: discord.Member,
        amount: int,
    ):
        if not await self.ensure_manager(ctx):
            return

        if amount <= 0:
            await ctx.send(
                "❌ يجب أن يكون مقدار الـXP أكبر من صفر."
            )
            return

        if amount > 10_000_000:
            await ctx.send(
                "❌ الحد الأقصى هو `10,000,000 XP`."
            )
            return

        xp, level = await self.remove_xp(
            member,
            amount,
        )

        await ctx.send(
            (
                f"✅ تم حذف `{amount:,} XP` من "
                f"{member.mention}.\n"
                f"⭐ المستوى: `{level}`\n"
                f"✨ XP: `{xp:,}`"
            )
        )

    @level_group.command(
        name="تصفير",
    )
    async def level_reset(
        self,
        ctx: commands.Context,
        member: Optional[discord.Member] = None,
    ):
        if not await self.ensure_manager(ctx):
            return

        if member is None:
            await ctx.send(
                "❌ حدد عضوًا، أو استخدم:\n"
                "`!ليفل تصفير @العضو`\n"
                "لتصفير عضو واحد."
            )
            return

        await self.set_user_data(
            ctx.guild.id,
            member.id,
            0,
            0,
        )

        await ctx.send(
            f"✅ تم تصفير مستوى {member.mention}."
        )

    @level_group.command(
        name="رتبة",
    )
    async def level_rank(
        self,
        ctx: commands.Context,
        member: Optional[discord.Member] = None,
    ):
        member = member or ctx.author

        rank = await self.get_rank(
            ctx.guild.id,
            member.id,
        )

        data = await self.get_user_data(
            ctx.guild.id,
            member.id,
        )

        await ctx.send(
            (
                f"🏆 رتبة {member.mention}: "
                f"`#{rank}`\n"
                f"⭐ المستوى: `{data['level']}`\n"
                f"✨ XP: `{data['xp']:,}`"
            )
        )

    @level_group.command(
        name="تصفير-الكل",
    )
    async def level_reset_all_alias(
        self,
        ctx: commands.Context,
    ):
        await self.reset_everyone(
            ctx
        )

    # Support the requested:
    # !ليفل تصفير @everyone
    @level_group.command(
        name="تصفير",
    )
    async def level_reset_duplicate(
        self,
        ctx: commands.Context,
        target: Optional[str] = None,
    ):
        # This method intentionally won't be reached because
        # Discord.py does not allow duplicate subcommand names.
        # Kept out of runtime by the alternate implementation below.
        return

    # =========================================================
    # Better Arabic "تصفير" Handler
    # =========================================================

    @commands.command(
        name="ليفل_تصفير_الكل",
    )
    async def reset_all_command(
        self,
        ctx: commands.Context,
    ):
        await self.reset_everyone(
            ctx
        )

    async def reset_everyone(
        self,
        ctx: commands.Context,
    ):
        if not await self.ensure_manager(ctx):
            return

        view = LevelResetConfirmView(
            self,
            ctx.author.id,
        )

        await ctx.send(
            (
                "⚠️ **تأكيد تصفير جميع المستويات**\n\n"
                "سيتم حذف XP والمستوى لجميع أعضاء السيرفر.\n"
                "لا يمكن التراجع عن العملية."
            ),
            view=view,
        )

    async def reset_all_users(
        self,
        guild: discord.Guild,
    ) -> int:
        await self.ensure_table()

        cursor = await db.execute(
            """
            SELECT COUNT(*)
            FROM user_levels
            WHERE guild_id = ?
            """,
            (guild.id,),
        )

        row = await cursor.fetchone()

        count = int(
            row[0] or 0
        ) if row else 0

        await db.execute(
            """
            UPDATE user_levels
            SET xp = 0,
                level = 0
            WHERE guild_id = ?
            """,
            (guild.id,),
        )

        await db.commit()

        return count

    # =========================================================
    # Ranking
    # =========================================================

    async def get_rank(
        self,
        guild_id: int,
        user_id: int,
    ) -> int:
        await self.ensure_table()

        cursor = await db.execute(
            """
            SELECT COUNT(*)
            FROM user_levels
            WHERE guild_id = ?
              AND (
                  xp > (
                      SELECT xp
                      FROM user_levels
                      WHERE guild_id = ?
                        AND user_id = ?
                  )
                  OR (
                      xp = (
                          SELECT xp
                          FROM user_levels
                          WHERE guild_id = ?
                            AND user_id = ?
                      )
                      AND user_id < ?
                  )
              )
            """,
            (
                guild_id,
                guild_id,
                user_id,
                guild_id,
                user_id,
                user_id,
            ),
        )

        row = await cursor.fetchone()

        return (
            int(row[0] or 0) + 1
            if row
            else 1
        )

    async def get_leaderboard(
        self,
        guild_id: int,
        limit: int = 10,
    ):
        await self.ensure_table()

        limit = max(
            1,
            min(int(limit), 100),
        )

        cursor = await db.execute(
            """
            SELECT user_id, xp, level
            FROM user_levels
            WHERE guild_id = ?
            ORDER BY xp DESC, user_id ASC
            LIMIT ?
            """,
            (
                guild_id,
                limit,
            ),
        )

        return await cursor.fetchall()

    # =========================================================
    # Slash Commands
    # =========================================================

    @discord.app_commands.command(
        name="level",
        description="عرض مستوى عضو",
    )
    @discord.app_commands.describe(
        member="العضو",
    )
    async def slash_level(
        self,
        interaction: discord.Interaction,
        member: Optional[discord.Member] = None,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ هذا الأمر داخل السيرفرات فقط.",
                ephemeral=True,
            )
            return

        member = member or interaction.user

        data = await self.get_user_data(
            interaction.guild.id,
            member.id,
        )

        rank = await self.get_rank(
            interaction.guild.id,
            member.id,
        )

        await interaction.response.send_message(
            (
                f"📊 **معلومات {member.display_name}**\n"
                f"⭐ المستوى: `{data['level']}`\n"
                f"✨ XP: `{data['xp']:,}`\n"
                f"🏆 الترتيب: `#{rank}`"
            )
        )

    @discord.app_commands.command(
        name="leaderboard",
        description="عرض قائمة أعلى الأعضاء في المستويات",
    )
    @discord.app_commands.describe(
        limit="عدد الأعضاء",
    )
    async def slash_leaderboard(
        self,
        interaction: discord.Interaction,
        limit: int = 10,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ هذا الأمر داخل السيرفرات فقط.",
                ephemeral=True,
            )
            return

        limit = max(
            1,
            min(limit, 25),
        )

        rows = await self.get_leaderboard(
            interaction.guild.id,
            limit,
        )

        if not rows:
            await interaction.response.send_message(
                "📊 لا توجد بيانات مستويات حتى الآن."
            )
            return

        lines = []

        for index, row in enumerate(
            rows,
            start=1,
        ):
            user_id = int(row[0])
            xp = int(row[1] or 0)
            level = int(row[2] or 0)

            member = interaction.guild.get_member(
                user_id
            )

            name = (
                member.display_name
                if member
                else f"عضو {user_id}"
            )

            medal = {
                1: "🥇",
                2: "🥈",
                3: "🥉",
            }.get(
                index,
                f"`#{index}`",
            )

            lines.append(
                (
                    f"{medal} **{name}** — "
                    f"Level `{level}` • XP `{xp:,}`"
                )
            )

        embed = discord.Embed(
            title="🏆 Level Leaderboard",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )

        await interaction.response.send_message(
            embed=embed
        )

    @discord.app_commands.command(
        name="level-add",
        description="إضافة XP لعضو",
    )
    @discord.app_commands.describe(
        member="العضو",
        amount="مقدار XP",
    )
    async def slash_level_add(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        amount: int,
    ):
        if not await self.ensure_slash_manager(
            interaction
        ):
            return

        if amount <= 0:
            await interaction.response.send_message(
                "❌ يجب أن يكون XP أكبر من صفر.",
                ephemeral=True,
            )
            return

        if amount > 10_000_000:
            await interaction.response.send_message(
                "❌ الحد الأقصى هو `10,000,000 XP`.",
                ephemeral=True,
            )
            return

        xp, level, _ = await self.add_xp(
            member,
            amount,
            announce=False,
        )

        await interaction.response.send_message(
            (
                f"✅ تمت إضافة `{amount:,} XP` إلى "
                f"{member.mention}.\n"
                f"⭐ المستوى: `{level}`\n"
                f"✨ XP: `{xp:,}`"
            )
        )

    @discord.app_commands.command(
        name="level-remove",
        description="حذف XP من عضو",
    )
    @discord.app_commands.describe(
        member="العضو",
        amount="مقدار XP",
    )
    async def slash_level_remove(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        amount: int,
    ):
        if not await self.ensure_slash_manager(
            interaction
        ):
            return

        if amount <= 0:
            await interaction.response.send_message(
                "❌ يجب أن يكون XP أكبر من صفر.",
                ephemeral=True,
            )
            return

        xp, level = await self.remove_xp(
            member,
            amount,
        )

        await interaction.response.send_message(
            (
                f"✅ تم حذف `{amount:,} XP` من "
                f"{member.mention}.\n"
                f"⭐ المستوى: `{level}`\n"
                f"✨ XP: `{xp:,}`"
            )
        )

    @discord.app_commands.command(
        name="level-reset",
        description="تصفير مستوى عضو",
    )
    @discord.app_commands.describe(
        member="العضو",
    )
    async def slash_level_reset(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ):
        if not await self.ensure_slash_manager(
            interaction
        ):
            return

        await self.set_user_data(
            interaction.guild.id,
            member.id,
            0,
            0,
        )

        await interaction.response.send_message(
            f"✅ تم تصفير مستوى {member.mention}."
        )

    @discord.app_commands.command(
        name="level-rank",
        description="عرض ترتيب عضو",
    )
    @discord.app_commands.describe(
        member="العضو",
    )
    async def slash_level_rank(
        self,
        interaction: discord.Interaction,
        member: Optional[discord.Member] = None,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ هذا الأمر داخل السيرفرات فقط.",
                ephemeral=True,
            )
            return

        member = member or interaction.user

        rank = await self.get_rank(
            interaction.guild.id,
            member.id,
        )

        data = await self.get_user_data(
            interaction.guild.id,
            member.id,
        )

        await interaction.response.send_message(
            (
                f"🏆 {member.mention} ترتيبه "
                f"`#{rank}`\n"
                f"⭐ المستوى: `{data['level']}`\n"
                f"✨ XP: `{data['xp']:,}`"
            )
        )

    # =========================================================
    # Traditional Prefix Command
    # =========================================================

    @commands.command(
        name="ترتيب",
        aliases=["ليفلترتيب"],
    )
    async def prefix_leaderboard(
        self,
        ctx: commands.Context,
    ):
        if ctx.guild is None:
            return

        rows = await self.get_leaderboard(
            ctx.guild.id,
            10,
        )

        if not rows:
            await ctx.send(
                "📊 لا توجد بيانات مستويات حتى الآن."
            )
            return

        lines = []

        for index, row in enumerate(
            rows,
            start=1,
        ):
            user_id = int(row[0])
            xp = int(row[1] or 0)
            level = int(row[2] or 0)

            member = ctx.guild.get_member(
                user_id
            )

            name = (
                member.display_name
                if member
                else f"عضو {user_id}"
            )

            lines.append(
                (
                    f"`#{index}` **{name}** — "
                    f"Level `{level}` • XP `{xp:,}`"
                )
            )

        embed = discord.Embed(
            title="🏆 ترتيب المستويات",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )

        await ctx.send(
            embed=embed
        )

    # =========================================================
    # Cleanup
    # =========================================================

    @commands.Cog.listener()
    async def on_guild_remove(
        self,
        guild: discord.Guild,
    ):
        keys = [
            key
            for key in self.cooldowns
            if key[0] == guild.id
        ]

        for key in keys:
            self.cooldowns.pop(
                key,
                None,
            )


# =========================================================
# Setup
# =========================================================

async def setup(
    bot: commands.Bot,
):
    cog = Levels(bot)

    await bot.add_cog(
        cog
    )
