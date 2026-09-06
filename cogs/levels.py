import random
import time

import aiosqlite
import discord
from discord.ext import commands

from database import db


class Levels(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # منع إعطاء XP مع كل رسالة بسرعة
        self.xp_cooldowns = {}

    # =========================================================
    # إنشاء جدول المستويات
    # =========================================================

    async def create_levels_table(self):
        async with await db.connect() as connection:
            await connection.execute("""
                CREATE TABLE IF NOT EXISTS user_levels (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    xp INTEGER NOT NULL DEFAULT 0,
                    level INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (guild_id, user_id)
                )
            """)

            await connection.commit()

    # =========================================================
    # جلب بيانات العضو
    # =========================================================

    async def get_user_data(
        self,
        guild_id: int,
        user_id: int
    ):
        async with await db.connect() as connection:
            connection.row_factory = aiosqlite.Row

            cursor = await connection.execute("""
                SELECT guild_id, user_id, xp, level
                FROM user_levels
                WHERE guild_id = ? AND user_id = ?
            """, (guild_id, user_id))

            row = await cursor.fetchone()

            if row:
                return dict(row)

            await connection.execute("""
                INSERT INTO user_levels (
                    guild_id,
                    user_id,
                    xp,
                    level
                )
                VALUES (?, ?, 0, 0)
            """, (guild_id, user_id))

            await connection.commit()

            return {
                "guild_id": guild_id,
                "user_id": user_id,
                "xp": 0,
                "level": 0
            }

    # =========================================================
    # إضافة XP
    # =========================================================

    async def add_xp(
        self,
        guild_id: int,
        user_id: int,
        amount: int
    ):
        data = await self.get_user_data(
            guild_id,
            user_id
        )

        old_xp = data["xp"]
        old_level = data["level"]

        new_xp = old_xp + amount

        # كل 100 XP = لفل
        new_level = new_xp // 100

        async with await db.connect() as connection:
            await connection.execute("""
                UPDATE user_levels
                SET xp = ?, level = ?
                WHERE guild_id = ? AND user_id = ?
            """, (
                new_xp,
                new_level,
                guild_id,
                user_id
            ))

            await connection.commit()

        return {
            "old_xp": old_xp,
            "new_xp": new_xp,
            "old_level": old_level,
            "new_level": new_level
        }

    # =========================================================
    # حدث الرسائل
    # =========================================================

    @commands.Cog.listener()
    async def on_message(
        self,
        message: discord.Message
    ):
        if message.author.bot:
            return

        if message.guild is None:
            return

        # نتأكد أن السيرفر موجود في قاعدة البيانات
        settings = await db.get_guild(
            message.guild.id
        )

        if not settings:
            await db.ensure_guild(
                guild_id=message.guild.id,
                guild_name=message.guild.name,
                guild_icon=(
                    str(message.guild.icon.url)
                    if message.guild.icon
                    else ""
                )
            )

            settings = await db.get_guild(
                message.guild.id
            )

        if not settings:
            return

        # إذا نظام الليفلز مقفل
        if not settings["level_enabled"]:
            return

        # =====================================================
        # Cooldown
        # =====================================================

        cooldown_key = (
            message.guild.id,
            message.author.id
        )

        current_time = time.monotonic()
        last_xp_time = self.xp_cooldowns.get(
            cooldown_key,
            0
        )

        # XP مرة كل 60 ثانية
        if current_time - last_xp_time < 60:
            return

        self.xp_cooldowns[cooldown_key] = current_time

        # =====================================================
        # XP عشوائي
        # =====================================================

        xp_amount = random.randint(15, 25)

        result = await self.add_xp(
            guild_id=message.guild.id,
            user_id=message.author.id,
            amount=xp_amount
        )

        # =====================================================
        # Level Up
        # =====================================================

        if result["new_level"] <= result["old_level"]:
            return

        channel_id = settings["level_channel_id"]

        if not channel_id:
            return

        channel = message.guild.get_channel(
            channel_id
        )

        if not isinstance(
            channel,
            discord.TextChannel
        ):
            return

        level = result["new_level"]

        embed = discord.Embed(
            title="🎉 Level Up!",
            description=(
                f"مبروك {message.author.mention}!\n\n"
                f"وصلت إلى **Level {level}** "
                f"في **{message.guild.name}** 🎊"
            ),
            color=discord.Color.blurple()
        )

        embed.add_field(
            name="⭐ مستواك الجديد",
            value=f"`{level}`",
            inline=True
        )

        embed.add_field(
            name="✨ XP",
            value=f"`{result['new_xp']}`",
            inline=True
        )

        embed.set_thumbnail(
            url=message.author.display_avatar.url
        )

        embed.set_footer(
            text=f"Zivex • {message.guild.name}"
        )

        try:
            await channel.send(
                content=message.author.mention,
                embed=embed
            )
        except discord.Forbidden:
            pass

    # =========================================================
    # أمر /level
    # =========================================================

    @commands.hybrid_command(
        name="level",
        description="عرض مستواك و XP"
    )
    async def level_command(
        self,
        ctx: commands.Context
    ):
        if ctx.guild is None:
            await ctx.send(
                "❌ هذا الأمر يعمل داخل السيرفر فقط."
            )
            return

        settings = await db.get_guild(
            ctx.guild.id
        )

        if not settings:
            await ctx.send(
                "❌ لم يتم إعداد هذا السيرفر بعد."
            )
            return

        if not settings["level_enabled"]:
            await ctx.send(
                "❌ نظام الليفلز غير مفعل في هذا السيرفر."
            )
            return

        data = await self.get_user_data(
            ctx.guild.id,
            ctx.author.id
        )

        level = data["level"]
        xp = data["xp"]

        current_level_xp = level * 100
        next_level_xp = (level + 1) * 100

        progress = xp - current_level_xp
        required = next_level_xp - current_level_xp

        embed = discord.Embed(
            title="📊 معلومات المستوى",
            color=discord.Color.blurple()
        )

        embed.set_author(
            name=ctx.author.display_name,
            icon_url=ctx.author.display_avatar.url
        )

        embed.add_field(
            name="⭐ المستوى",
            value=f"`{level}`",
            inline=True
        )

        embed.add_field(
            name="✨ XP",
            value=f"`{xp}`",
            inline=True
        )

        embed.add_field(
            name="📈 التقدم",
            value=f"`{progress}/{required}` XP",
            inline=True
        )

        embed.set_footer(
            text=f"Zivex • {ctx.guild.name}"
        )

        await ctx.send(embed=embed)

    # =========================================================
    # أمر /leaderboard
    # =========================================================

    @commands.hybrid_command(
        name="leaderboard",
        description="عرض أعلى اللاعبين في XP"
    )
    async def leaderboard_command(
        self,
        ctx: commands.Context
    ):
        if ctx.guild is None:
            await ctx.send(
                "❌ هذا الأمر يعمل داخل السيرفر فقط."
            )
            return

        settings = await db.get_guild(
            ctx.guild.id
        )

        if not settings:
            await ctx.send(
                "❌ لم يتم إعداد هذا السيرفر بعد."
            )
            return

        if not settings["level_enabled"]:
            await ctx.send(
                "❌ نظام الليفلز غير مفعل في هذا السيرفر."
            )
            return

        async with await db.connect() as connection:
            cursor = await connection.execute("""
                SELECT user_id, xp, level
                FROM user_levels
                WHERE guild_id = ?
                ORDER BY xp DESC
                LIMIT 10
            """, (ctx.guild.id,))

            rows = await cursor.fetchall()

        if not rows:
            await ctx.send(
                "🏆 لا يوجد لاعبين في قائمة المتصدرين حتى الآن."
            )
            return

        medals = [
            "🥇",
            "🥈",
            "🥉"
        ]

        lines = []

        for index, row in enumerate(rows, start=1):
            user_id = row[0]
            xp = row[1]
            level = row[2]

            member = ctx.guild.get_member(
                user_id
            )

            if member:
                name = member.display_name
            else:
                name = f"عضو {user_id}"

            if index <= 3:
                rank = medals[index - 1]
            else:
                rank = f"`#{index}`"

            lines.append(
                f"{rank} **{name}** — "
                f"Level `{level}` • XP `{xp}`"
            )

        embed = discord.Embed(
            title="🏆 المتصدرين",
            description="\n".join(lines),
            color=discord.Color.gold()
        )

        embed.set_footer(
            text=f"Zivex • {ctx.guild.name}"
        )

        await ctx.send(embed=embed)

    # =========================================================
    # أمر !ليفل
    # =========================================================

    @commands.command(name="ليفل")
    async def level_prefix(
        self,
        ctx: commands.Context
    ):
        await self.level_command(ctx)

    # =========================================================
    # أمر !مستوى
    # =========================================================

    @commands.command(name="مستوى")
    async def level_prefix_alt(
        self,
        ctx: commands.Context
    ):
        await self.level_command(ctx)

    # =========================================================
    # أمر !ترتيب
    # =========================================================

    @commands.command(name="ترتيب")
    async def leaderboard_prefix(
        self,
        ctx: commands.Context
    ):
        await self.leaderboard_command(ctx)


# =========================================================
# Setup
# =========================================================

async def setup(bot: commands.Bot):
    cog = Levels(bot)

    await cog.create_levels_table()

    await bot.add_cog(cog)
