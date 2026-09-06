import discord
from datetime import timedelta
from discord import app_commands
from discord.ext import commands


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # =========================================================
    # التحقق من السيرفر
    # =========================================================

    async def check_guild(
        self,
        interaction: discord.Interaction
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ هذا الأمر يعمل داخل السيرفر فقط.",
                ephemeral=True
            )
            return False

        return True

    # =========================================================
    # التحقق من الصلاحيات
    # =========================================================

    async def check_permission(
        self,
        interaction: discord.Interaction,
        permission: str
    ):
        if not await self.check_guild(interaction):
            return False

        permissions = interaction.user.guild_permissions

        if not getattr(permissions, permission, False):
            await interaction.response.send_message(
                "❌ ما عندك صلاحية لاستخدام هذا الأمر.",
                ephemeral=True
            )
            return False

        return True

    # =========================================================
    # KICK
    # =========================================================

    @app_commands.command(
        name="kick",
        description="طرد عضو من السيرفر"
    )
    @app_commands.describe(
        member="العضو الذي تريد طرده",
        reason="سبب الطرد"
    )
    async def slash_kick(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "بدون سبب"
    ):
        if not await self.check_permission(
            interaction,
            "kick_members"
        ):
            return

        if member == interaction.user:
            await interaction.response.send_message(
                "❌ ما تقدر تطرد نفسك.",
                ephemeral=True
            )
            return

        if member == interaction.guild.owner:
            await interaction.response.send_message(
                "❌ ما تقدر تطرد مالك السيرفر.",
                ephemeral=True
            )
            return

        if (
            interaction.user != interaction.guild.owner
            and member.top_role >= interaction.user.top_role
        ):
            await interaction.response.send_message(
                "❌ رتبة العضو أعلى من رتبتك أو مساوية لها.",
                ephemeral=True
            )
            return

        bot_member = interaction.guild.me

        if bot_member and member.top_role >= bot_member.top_role:
            await interaction.response.send_message(
                "❌ ما أقدر أطرد هذا العضو بسبب ترتيب الرتب.",
                ephemeral=True
            )
            return

        try:
            await member.kick(
                reason=f"{reason} | بواسطة {interaction.user}"
            )

            embed = discord.Embed(
                title="👢 تم طرد العضو",
                color=discord.Color.orange()
            )

            embed.add_field(
                name="👤 العضو",
                value=f"{member.mention}\n`{member}`",
                inline=True
            )

            embed.add_field(
                name="🛡️ بواسطة",
                value=interaction.user.mention,
                inline=True
            )

            embed.add_field(
                name="📝 السبب",
                value=reason,
                inline=False
            )

            await interaction.response.send_message(
                embed=embed
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ ما قدرت أطرد العضو. تأكد من صلاحيات البوت وترتيب الرتب.",
                ephemeral=True
            )

    # =========================================================
    # BAN
    # =========================================================

    @app_commands.command(
        name="ban",
        description="حظر عضو من السيرفر"
    )
    @app_commands.describe(
        member="العضو الذي تريد حظره",
        reason="سبب الحظر"
    )
    async def slash_ban(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "بدون سبب"
    ):
        if not await self.check_permission(
            interaction,
            "ban_members"
        ):
            return

        if member == interaction.user:
            await interaction.response.send_message(
                "❌ ما تقدر تحظر نفسك.",
                ephemeral=True
            )
            return

        if member == interaction.guild.owner:
            await interaction.response.send_message(
                "❌ ما تقدر تحظر مالك السيرفر.",
                ephemeral=True
            )
            return

        if (
            interaction.user != interaction.guild.owner
            and member.top_role >= interaction.user.top_role
        ):
            await interaction.response.send_message(
                "❌ رتبة العضو أعلى من رتبتك أو مساوية لها.",
                ephemeral=True
            )
            return

        bot_member = interaction.guild.me

        if bot_member and member.top_role >= bot_member.top_role:
            await interaction.response.send_message(
                "❌ ما أقدر أحظر هذا العضو بسبب ترتيب الرتب.",
                ephemeral=True
            )
            return

        try:
            await member.ban(
                reason=f"{reason} | بواسطة {interaction.user}"
            )

            embed = discord.Embed(
                title="🔨 تم حظر العضو",
                color=discord.Color.red()
            )

            embed.add_field(
                name="👤 العضو",
                value=f"{member.mention}\n`{member}`",
                inline=True
            )

            embed.add_field(
                name="🛡️ بواسطة",
                value=interaction.user.mention,
                inline=True
            )

            embed.add_field(
                name="📝 السبب",
                value=reason,
                inline=False
            )

            await interaction.response.send_message(
                embed=embed
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ ما قدرت أحظر العضو. تأكد من صلاحيات البوت وترتيب الرتب.",
                ephemeral=True
            )

    # =========================================================
    # UNBAN
    # =========================================================

    @app_commands.command(
        name="unban",
        description="إلغاء حظر عضو"
    )
    @app_commands.describe(
        user_id="ID العضو المحظور",
        reason="سبب فك الحظر"
    )
    async def slash_unban(
        self,
        interaction: discord.Interaction,
        user_id: str,
        reason: str = "بدون سبب"
    ):
        if not await self.check_permission(
            interaction,
            "ban_members"
        ):
            return

        try:
            user_id_int = int(user_id)
        except ValueError:
            await interaction.response.send_message(
                "❌ الـID غير صحيح.",
                ephemeral=True
            )
            return

        try:
            user = await self.bot.fetch_user(
                user_id_int
            )

            await interaction.guild.unban(
                user,
                reason=f"{reason} | بواسطة {interaction.user}"
            )

            await interaction.response.send_message(
                f"✅ تم فك الحظر عن {user.mention}."
            )

        except discord.NotFound:
            await interaction.response.send_message(
                "❌ هذا العضو غير موجود في قائمة المحظورين.",
                ephemeral=True
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ ما عندي صلاحية فك الحظر.",
                ephemeral=True
            )

    # =========================================================
    # CLEAR
    # =========================================================

    @app_commands.command(
        name="clear",
        description="حذف عدد من الرسائل"
    )
    @app_commands.describe(
        amount="عدد الرسائل المراد حذفها"
    )
    async def slash_clear(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, 100]
    ):
        if not await self.check_permission(
            interaction,
            "manage_messages"
        ):
            return

        channel = interaction.channel

        if not isinstance(
            channel,
            discord.TextChannel
        ):
            await interaction.response.send_message(
                "❌ هذا الأمر يعمل في الرومات النصية فقط.",
                ephemeral=True
            )
            return

        await interaction.response.defer(
            ephemeral=True
        )

        try:
            deleted = await channel.purge(
                limit=amount
            )

            await interaction.followup.send(
                f"🧹 تم حذف **{len(deleted)}** رسالة.",
                ephemeral=True
            )

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ ما عندي صلاحية حذف الرسائل.",
                ephemeral=True
            )

    # =========================================================
    # TIMEOUT
    # =========================================================

    @app_commands.command(
        name="timeout",
        description="إعطاء عضو تايم أوت"
    )
    @app_commands.describe(
        member="العضو",
        minutes="مدة التايم أوت بالدقائق",
        reason="السبب"
    )
    async def slash_timeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        minutes: app_commands.Range[int, 1, 40320],
        reason: str = "بدون سبب"
    ):
        if not await self.check_permission(
            interaction,
            "moderate_members"
        ):
            return

        if member == interaction.user:
            await interaction.response.send_message(
                "❌ ما تقدر تعطي نفسك تايم أوت.",
                ephemeral=True
            )
            return

        if member == interaction.guild.owner:
            await interaction.response.send_message(
                "❌ ما تقدر تعطي مالك السيرفر تايم أوت.",
                ephemeral=True
            )
            return

        if (
            interaction.user != interaction.guild.owner
            and member.top_role >= interaction.user.top_role
        ):
            await interaction.response.send_message(
                "❌ رتبة العضو أعلى من رتبتك أو مساوية لها.",
                ephemeral=True
            )
            return

        bot_member = interaction.guild.me

        if bot_member and member.top_role >= bot_member.top_role:
            await interaction.response.send_message(
                "❌ ما أقدر أعطي هذا العضو تايم أوت بسبب ترتيب الرتب.",
                ephemeral=True
            )
            return

        duration = discord.utils.utcnow() + timedelta(
            minutes=minutes
        )

        try:
            await member.timeout(
                duration,
                reason=f"{reason} | بواسطة {interaction.user}"
            )

            await interaction.response.send_message(
                f"🔇 تم إعطاء {member.mention} تايم أوت لمدة **{minutes} دقيقة**."
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ ما قدرت أعطي العضو تايم أوت.",
                ephemeral=True
            )

    # =========================================================
    # UNTIMEOUT
    # =========================================================

    @app_commands.command(
        name="untimeout",
        description="إزالة التايم أوت من عضو"
    )
    @app_commands.describe(
        member="العضو"
    )
    async def slash_untimeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member
    ):
        if not await self.check_permission(
            interaction,
            "moderate_members"
        ):
            return

        try:
            await member.timeout(
                None,
                reason=f"إزالة التايم أوت بواسطة {interaction.user}"
            )

            await interaction.response.send_message(
                f"🔊 تم إزالة التايم أوت عن {member.mention}."
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ ما قدرت أزيل التايم أوت.",
                ephemeral=True
            )

    # =========================================================
    # LOCK
    # =========================================================

    @app_commands.command(
        name="lock",
        description="قفل الروم الحالي"
    )
    async def slash_lock(
        self,
        interaction: discord.Interaction
    ):
        if not await self.check_permission(
            interaction,
            "manage_channels"
        ):
            return

        channel = interaction.channel

        if not isinstance(
            channel,
            discord.TextChannel
        ):
            await interaction.response.send_message(
                "❌ هذا الأمر يعمل في الرومات النصية فقط.",
                ephemeral=True
            )
            return

        try:
            overwrite = channel.overwrites_for(
                interaction.guild.default_role
            )

            overwrite.send_messages = False

            await channel.set_permissions(
                interaction.guild.default_role,
                overwrite=overwrite,
                reason=f"قفل الروم بواسطة {interaction.user}"
            )

            await interaction.response.send_message(
                "🔒 تم قفل الروم."
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ ما عندي صلاحية تعديل صلاحيات الروم.",
                ephemeral=True
            )

    # =========================================================
    # UNLOCK
    # =========================================================

    @app_commands.command(
        name="unlock",
        description="فتح الروم الحالي"
    )
    async def slash_unlock(
        self,
        interaction: discord.Interaction
    ):
        if not await self.check_permission(
            interaction,
            "manage_channels"
        ):
            return

        channel = interaction.channel

        if not isinstance(
            channel,
            discord.TextChannel
        ):
            await interaction.response.send_message(
                "❌ هذا الأمر يعمل في الرومات النصية فقط.",
                ephemeral=True
            )
            return

        try:
            overwrite = channel.overwrites_for(
                interaction.guild.default_role
            )

            overwrite.send_messages = None

            await channel.set_permissions(
                interaction.guild.default_role,
                overwrite=overwrite,
                reason=f"فتح الروم بواسطة {interaction.user}"
            )

            await interaction.response.send_message(
                "🔓 تم فتح الروم."
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ ما عندي صلاحية تعديل صلاحيات الروم.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
