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
        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            content="⏳ جاري تصفير جميع المستويات...",
            view=self,
        )

        count = await self.cog.reset_all_users(
            interaction.guild
        )

        await interaction.edit_original_response(
            content=f"✅ تم تصفير مستويات **{count}** عضو.",
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
        self.table_ready = False

    # =========================================================
    # Database
    # =========================================================

    async def ensure_table(self):
        if self.table_ready:
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
        self.table_ready = True

    async def get_settings(self, guild):
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
                f"❌ [LEVELS] Database error "
                f"for {guild.id}: {error}"
            )
            return None

    async def get_user_data(
        self,
        guild_id: int,
        user_id: int,
    ):
        await self.ensure_table()

        cursor = await db.execute(
            """
            SELECT xp, level
            FROM user_levels
            WHERE guild_id = ?
            AND user_id = ?
            """,
            (guild_id, user_id),
        )

        row = await cursor.fetchone()

        if row is None:
            await db.execute(
                """
                INSERT INTO user_levels
                (guild_id, user_id, xp, level)
                VALUES (?, ?, 0, 0)
                """,
                (guild_id, user_id),
            )

            await db.commit()

            return 0, 0

        return int(row[0]), int(row[1])

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
            INSERT INTO user_levels
            (guild_id, user_id, xp, level)
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

    # =========================================================
    # Helpers
    # =========================================================

    @staticmethod
    def parse_color(value):
        if not value:
            return discord.Color.blurple()

        try:
            value = str(value).strip()
            value = value.replace("#", "")

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
        level: int,
        xp: int,
    ):
        variables = {
            "{user}": member.mention,
            "{username}": member.display_name,
            "{server}": member.guild.name,
            "{member_count}": str(
                member.guild.member_count or 0
            ),
            "{level}": str(level),
            "{xp}": str(xp),
        }

        for key, value in variables.items():
            text = text.replace(
                key,
                str(value),
            )

        return text

    def xp_per_level(self, settings):
        try:
            value = int(
                settings.get(
                    "level_xp_per_level",
                    100,
                )
            )
        except (TypeError, ValueError):
            value = 100

        return max(
            1,
            min(value, 1_000_000),
        )

    # =========================================================
    # XP
    # =========================================================

    async def add_xp(
        self,
        member: discord.Member,
        amount: int,
        announce=True,
    ):
        settings = await self.get_settings(
            member.guild
        )

        if not settings:
            return 0, 0, False

        old_xp, old_level = await self.get_user_data(
            member.guild.id,
            member.id,
        )

        required = self.xp_per_level(
            settings
        )

        new_xp = max(
            0,
            old_xp + amount,
        )

        new_level = new_xp // required

        leveled_up = new_level > old_level

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
    ):
        settings = await self.get_settings(
            member.guild
        )

        required = self.xp_per_level(
            settings
        )

        xp, _ = await self.get_user_data(
            member.guild.id,
            member.id,
        )

        new_xp = max(
            0,
            xp - amount,
        )

        new_level = new_xp // required

        await self.set_user_data(
            member.guild.id,
            member.id,
            new_xp,
            new_level,
        )

        return new_xp, new_level

    # =========================================================
    # Level Up
    # =========================================================

    async def send_level_up(
        self,
        member,
        level,
        xp,
        settings,
    ):
        title = (
            settings.get("level_title")
            or "🎉 مستوى جديد!"
        )

        message = (
            settings.get("level_message")
            or (
                "مبروك {user}! وصلت إلى "
                "المستوى **{level}**."
            )
        )

        footer = (
            settings.get("level_footer")
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
                settings.get("level_color")
            ),
            timestamp=discord.utils.utcnow(),
        )

        if bool(
            settings.get(
                "level_thumbnail",
                1,
            )
        ):
            embed.set_thumbnail(
                url=member.display_avatar.url
            )

        if member.guild.icon:
            embed.set_footer(
                text=footer,
                icon_url=member.guild.icon.url,
            )
        else:
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

        except Exception as error:
            print(
                f"⚠️ [LEVELS] Level-up message error: "
                f"{error}"
            )

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

    # =========================================================
    # Message XP
    # =========================================================

    @commands.Cog.listener()
    async def on_message(
        self,
        message: discord.Message,
    ):
        if (
            message.author.bot
            or message.webhook_id
            or not message.guild
        ):
            return

        if not isinstance(
            message.author,
            discord.Member,
        ):
            return

        settings = await self.get_settings(
            message.guild
        )

        if not settings:
            return

        if not bool(
            settings.get(
                "level_enabled",
                0,
            )
        ):
            return

        cooldown = settings.get(
            "level_cooldown",
            60,
        )

        try:
            cooldown = max(
                1,
                min(int(cooldown), 86400),
            )
        except (TypeError, ValueError):
            cooldown = 60

        key = (
            message.guild.id,
            message.author.id,
        )

        now = time.monotonic()

        if (
            now - self.cooldowns.get(
                key,
                0,
            )
            < cooldown
        ):
            return

        self.cooldowns[key] = now

        try:
            xp_min = int(
                settings.get(
                    "level_xp_min",
                    15,
                )
            )

            xp_max = int(
                settings.get(
                    "level_xp_max",
                    25,
                )
            )
        except (TypeError, ValueError):
            xp_min = 15
            xp_max = 25

        xp_min = max(
            1,
            min(xp_min, 10000),
        )

        xp_max = max(
            1,
            min(xp_max, 10000),
        )

        if xp_min > xp_max:
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
    # Permission
    # =========================================================

    async def is_manager(
        self,
        user,
    ):
        if await self.bot.is_owner(user):
            return True

        return (
            isinstance(user, discord.Member)
            and user.guild_permissions.manage_guild
        )

    async def check_manager(
        self,
        ctx,
    ):
        if await self.is_manager(
            ctx.author
        ):
            return True

        await ctx.send(
            "❌ تحتاج صلاحية **إدارة السيرفر**."
        )

        return False

    # =========================================================
    # Rank
    # =========================================================

    async def get_rank(
        self,
        guild_id,
        user_id,
    ):
        await self.ensure_table()

        cursor = await db.execute(
            """
            SELECT COUNT(*)
            FROM user_levels
            WHERE guild_id = ?
            AND xp > (
                SELECT COALESCE(xp, 0)
                FROM user_levels
                WHERE guild_id = ?
                AND user_id = ?
            )
            """,
            (
                guild_id,
                guild_id,
                user_id,
            ),
        )

        row = await cursor.fetchone()

        return (
            int(row[0]) + 1
            if row
            else 1
        )

    async def get_leaderboard(
        self,
        guild_id,
        limit=10,
    ):
        await self.ensure_table()

        cursor = await db.execute(
            """
            SELECT user_id, xp, level
            FROM user_levels
            WHERE guild_id = ?
            ORDER BY xp DESC, level DESC, user_id ASC
            LIMIT ?
            """,
            (
                guild_id,
                max(1, min(limit, 100)),
            ),
        )

        return await cursor.fetchall()

    # =========================================================
    # Arabic Prefix Commands
    # =========================================================

    @commands.group(
        name="ليفل",
        invoke_without_command=True,
    )
    async def level_group(
        self,
        ctx,
        member: Optional[discord.Member] = None,
    ):
        if not ctx.guild:
            return

        member = member or ctx.author

        xp, level = await self.get_user_data(
            ctx.guild.id,
            member.id,
        )

        rank = await self.get_rank(
            ctx.guild.id,
            member.id,
        )

        await ctx.send(
            (
                f"📊 **معلومات المستوى**\n"
                f"👤 العضو: {member.mention}\n"
                f"⭐ المستوى: `{level}`\n"
                f"✨ XP: `{xp:,}`\n"
                f"🏆 الترتيب: `#{rank}`"
            )
        )

    @level_group.command(
        name="اضافة"
    )
    async def level_add(
        self,
        ctx,
        member: discord.Member,
        amount: int,
    ):
        if not await self.check_manager(ctx):
            return

        if amount <= 0:
            await ctx.send(
                "❌ اكتب مقدار XP أكبر من صفر."
            )
            return

        if amount > 10_000_000:
            await ctx.send(
                "❌ الحد الأقصى `10,000,000 XP`."
            )
            return

        xp, level, _ = await self.add_xp(
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
        name="حذف"
    )
    async def level_remove(
        self,
        ctx,
        member: discord.Member,
        amount: int,
    ):
        if not await self.check_manager(ctx):
            return

        if amount <= 0:
            await ctx.send(
                "❌ اكتب مقدار XP أكبر من صفر."
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
        name="رتبة"
    )
    async def level_rank(
        self,
        ctx,
        member: Optional[discord.Member] = None,
    ):
        member = member or ctx.author

        xp, level = await self.get_user_data(
            ctx.guild.id,
            member.id,
        )

        rank = await self.get_rank(
            ctx.guild.id,
            member.id,
        )

        await ctx.send(
            (
                f"🏆 **ترتيب {member.display_name}**\n"
                f"الترتيب: `#{rank}`\n"
                f"المستوى: `{level}`\n"
                f"XP: `{xp:,}`"
            )
        )

    @level_group.command(
        name="تصفير"
    )
    async def level_reset(
        self,
        ctx,
        member: Optional[discord.Member] = None,
    ):
        if not await self.check_manager(ctx):
            return

        # !ليفل تصفير @everyone
        if member is None:
            view = LevelResetConfirmView(
                self,
                ctx.author.id,
            )

            await ctx.send(
                (
                    "⚠️ **تأكيد تصفير الجميع**\n\n"
                    "سيتم تصفير XP والمستوى لجميع "
                    "الأعضاء المسجلين في نظام الليفل.\n"
                    "لا يمكن التراجع عن العملية."
                ),
                view=view,
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

    # =========================================================
    # Leaderboard Prefix
    # =========================================================

    @commands.command(
        name="ترتيب"
    )
    async def leaderboard(
        self,
        ctx,
    ):
        if not ctx.guild:
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
            1,
        ):
            user_id = int(row[0])
            xp = int(row[1])
            level = int(row[2])

            member = ctx.guild.get_member(
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
            title="🏆 ترتيب المستويات",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )

        await ctx.send(
            embed=embed
        )

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
        interaction,
        member: Optional[discord.Member] = None,
    ):
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ هذا الأمر داخل السيرفر فقط.",
                ephemeral=True,
            )
            return

        member = member or interaction.user

        xp, level = await self.get_user_data(
            interaction.guild.id,
            member.id,
        )

        rank = await self.get_rank(
            interaction.guild.id,
            member.id,
        )

        await interaction.response.send_message(
            (
                f"📊 **معلومات المستوى**\n"
                f"👤 العضو: {member.mention}\n"
                f"⭐ المستوى: `{level}`\n"
                f"✨ XP: `{xp:,}`\n"
                f"🏆 الترتيب: `#{rank}`"
            )
        )

    @discord.app_commands.command(
        name="leaderboard",
        description="عرض ترتيب المستويات",
    )
    @discord.app_commands.describe(
        limit="عدد الأعضاء",
    )
    async def slash_leaderboard(
        self,
        interaction,
        limit: int = 10,
    ):
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ هذا الأمر داخل السيرفر فقط.",
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
            1,
        ):
            user_id = int(row[0])
            xp = int(row[1])
            level = int(row[2])

            member = interaction.guild.get_member(
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
        interaction,
        member: discord.Member,
        amount: int,
    ):
        if not await self.is_manager(
            interaction.user
        ):
            await interaction.response.send_message(
                "❌ تحتاج صلاحية إدارة السيرفر.",
                ephemeral=True,
            )
            return

        if amount <= 0:
            await interaction.response.send_message(
                "❌ يجب أن يكون XP أكبر من صفر.",
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
        interaction,
        member: discord.Member,
        amount: int,
    ):
        if not await self.is_manager(
            interaction.user
        ):
            await interaction.response.send_message(
                "❌ تحتاج صلاحية إدارة السيرفر.",
                ephemeral=True,
            )
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
        interaction,
        member: discord.Member,
    ):
        if not await self.is_manager(
            interaction.user
        ):
            await interaction.response.send_message(
                "❌ تحتاج صلاحية إدارة السيرفر.",
                ephemeral=True,
            )
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
        interaction,
        member: Optional[discord.Member] = None,
    ):
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ هذا الأمر داخل السيرفر فقط.",
                ephemeral=True,
            )
            return

        member = member or interaction.user

        xp, level = await self.get_user_data(
            interaction.guild.id,
            member.id,
        )

        rank = await self.get_rank(
            interaction.guild.id,
            member.id,
        )

        await interaction.response.send_message(
            (
                f"🏆 **ترتيب {member.display_name}**\n"
                f"الترتيب: `#{rank}`\n"
                f"المستوى: `{level}`\n"
                f"XP: `{xp:,}`"
            )
        )

    # =========================================================
    # Reset All
    # =========================================================

    async def reset_all_users(
        self,
        guild: discord.Guild,
    ):
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

        count = (
            int(row[0])
            if row
            else 0
        )

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
    # Guild Cleanup
    # =========================================================

    @commands.Cog.listener()
    async def on_guild_remove(
        self,
        guild,
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

async def setup(bot: commands.Bot):
    await bot.add_cog(
        Levels(bot)
    )
