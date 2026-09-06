import discord
from datetime import timedelta
from discord import app_commands
from discord.ext import commands


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # =========================================================
    # Helpers
    # =========================================================

    async def is_owner(self, user):
        try:
            return await self.bot.is_owner(user)
        except Exception:
            return False

    async def has_permission(
        self,
        user: discord.Member,
        permission: str,
    ):
        if await self.is_owner(user):
            return True

        return getattr(
            user.guild_permissions,
            permission,
            False,
        )

    async def check_slash_permission(
        self,
        interaction: discord.Interaction,
        permission: str,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ هذا الأمر يعمل داخل السيرفر فقط.",
                ephemeral=True,
            )
            return False

        if not await self.has_permission(
            interaction.user,
            permission,
        ):
            await interaction.response.send_message(
                "❌ ما عندك صلاحية لاستخدام هذا الأمر.",
                ephemeral=True,
            )
            return False

        return True

    async def check_prefix_permission(
        self,
        ctx: commands.Context,
        permission: str,
    ):
        if ctx.guild is None:
            await ctx.send(
                "❌ هذا الأمر يعمل داخل السيرفر فقط."
            )
            return False

        if not await self.has_permission(
            ctx.author,
            permission,
        ):
            await ctx.send(
                "❌ ما عندك صلاحية لاستخدام هذا الأمر."
            )
            return False

        return True

    async def hierarchy_check(
        self,
        moderator: discord.Member,
        target: discord.Member,
    ):
        if target == moderator:
            return False, "❌ ما تقدر تستخدم الأمر على نفسك."

        if target == moderator.guild.owner:
            return False, "❌ ما تقدر تستخدم الأمر على مالك السيرفر."

        if await self.is_owner(moderator):
            return True, None

        if target.top_role >= moderator.top_role:
            return (
                False,
                "❌ رتبة العضو أعلى من رتبتك أو مساوية لها.",
            )

        bot_member = moderator.guild.me

        if bot_member and target.top_role >= bot_member.top_role:
            return (
                False,
                "❌ رتبة العضو أعلى من رتبة البوت.",
            )

        return True, None

    async def send_log(
        self,
        guild,
        action,
        member=None,
        moderator=None,
        reason=None,
    ):
        logs = self.bot.get_cog("Logs")

        if not logs:
            return

        try:
            await logs.moderation_action(
                guild,
                action,
                member,
                moderator,
                reason,
            )
        except Exception as error:
            print(
                f"⚠️ [MODERATION] Log error: {error}"
            )

    def reason_text(self, reason: str):
        reason = reason.strip()

        if not reason:
            return "بدون سبب"

        return reason[:500]

    # =========================================================
    # KICK - Slash
    # =========================================================

    @app_commands.command(
        name="kick",
        description="طرد عضو من السيرفر",
    )
    @app_commands.describe(
        member="العضو",
        reason="سبب الطرد",
    )
    async def slash_kick(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "بدون سبب",
    ):
        if not await self.check_slash_permission(
            interaction,
            "kick_members",
        ):
            return

        allowed, error = await self.hierarchy_check(
            interaction.user,
            member,
        )

        if not allowed:
            await interaction.response.send_message(
                error,
                ephemeral=True,
            )
            return

        reason = self.reason_text(reason)

        try:
            await member.kick(
                reason=(
                    f"{reason} | بواسطة "
                    f"{interaction.user}"
                )
            )

            embed = discord.Embed(
                title="👢 تم طرد العضو",
                color=discord.Color.orange(),
                timestamp=discord.utils.utcnow(),
            )

            embed.add_field(
                name="👤 العضو",
                value=f"{member.mention}\n`{member}`",
                inline=True,
            )

            embed.add_field(
                name="🛡️ بواسطة",
                value=interaction.user.mention,
                inline=True,
            )

            embed.add_field(
                name="📝 السبب",
                value=reason,
                inline=False,
            )

            await interaction.response.send_message(
                embed=embed
            )

            await self.send_log(
                interaction.guild,
                "طرد",
                member,
                interaction.user,
                reason,
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ ما قدرت أطرد العضو. تأكد من صلاحيات البوت وترتيب الرتب.",
                ephemeral=True,
            )

        except discord.HTTPException:
            await interaction.response.send_message(
                "❌ حدث خطأ أثناء تنفيذ عملية الطرد.",
                ephemeral=True,
            )

    # =========================================================
    # BAN - Slash
    # =========================================================

    @app_commands.command(
        name="ban",
        description="حظر عضو من السيرفر",
    )
    @app_commands.describe(
        member="العضو",
        reason="سبب الحظر",
        delete_days="حذف رسائل العضو من آخر كم يوم",
    )
    async def slash_ban(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "بدون سبب",
        delete_days: app_commands.Range[int, 0, 7] = 0,
    ):
        if not await self.check_slash_permission(
            interaction,
            "ban_members",
        ):
            return

        allowed, error = await self.hierarchy_check(
            interaction.user,
            member,
        )

        if not allowed:
            await interaction.response.send_message(
                error,
                ephemeral=True,
            )
            return

        reason = self.reason_text(reason)

        try:
            await member.ban(
                reason=(
                    f"{reason} | بواسطة "
                    f"{interaction.user}"
                ),
                delete_message_days=delete_days,
            )

            embed = discord.Embed(
                title="🔨 تم حظر العضو",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow(),
            )

            embed.add_field(
                name="👤 العضو",
                value=f"{member.mention}\n`{member}`",
                inline=True,
            )

            embed.add_field(
                name="🛡️ بواسطة",
                value=interaction.user.mention,
                inline=True,
            )

            embed.add_field(
                name="📝 السبب",
                value=reason,
                inline=False,
            )

            await interaction.response.send_message(
                embed=embed
            )

            await self.send_log(
                interaction.guild,
                "حظر",
                member,
                interaction.user,
                reason,
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ ما قدرت أحظر العضو. تأكد من صلاحيات البوت وترتيب الرتب.",
                ephemeral=True,
            )

        except discord.HTTPException:
            await interaction.response.send_message(
                "❌ حدث خطأ أثناء تنفيذ الحظر.",
                ephemeral=True,
            )

    # =========================================================
    # UNBAN - Slash
    # =========================================================

    @app_commands.command(
        name="unban",
        description="فك حظر مستخدم",
    )
    @app_commands.describe(
        user_id="ID المستخدم",
        reason="سبب فك الحظر",
    )
    async def slash_unban(
        self,
        interaction: discord.Interaction,
        user_id: str,
        reason: str = "بدون سبب",
    ):
        if not await self.check_slash_permission(
            interaction,
            "ban_members",
        ):
            return

        try:
            user_id_int = int(user_id)
        except ValueError:
            await interaction.response.send_message(
                "❌ الـ ID غير صحيح.",
                ephemeral=True,
            )
            return

        try:
            user = await self.bot.fetch_user(
                user_id_int
            )

            reason = self.reason_text(reason)

            await interaction.guild.unban(
                user,
                reason=(
                    f"{reason} | بواسطة "
                    f"{interaction.user}"
                ),
            )

            await interaction.response.send_message(
                f"✅ تم فك الحظر عن `{user}`."
            )

            await self.send_log(
                interaction.guild,
                "فك حظر",
                user,
                interaction.user,
                reason,
            )

        except discord.NotFound:
            await interaction.response.send_message(
                "❌ المستخدم غير موجود في قائمة المحظورين.",
                ephemeral=True,
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ ما عندي صلاحية فك الحظر.",
                ephemeral=True,
            )

        except discord.HTTPException:
            await interaction.response.send_message(
                "❌ حدث خطأ أثناء فك الحظر.",
                ephemeral=True,
            )

    # =========================================================
    # CLEAR - Slash
    # =========================================================

    @app_commands.command(
        name="clear",
        description="حذف رسائل من الروم",
    )
    @app_commands.describe(
        amount="عدد الرسائل",
    )
    async def slash_clear(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, 100],
    ):
        if not await self.check_slash_permission(
            interaction,
            "manage_messages",
        ):
            return

        if not isinstance(
            interaction.channel,
            discord.TextChannel,
        ):
            await interaction.response.send_message(
                "❌ هذا الأمر يعمل في الرومات النصية فقط.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True
        )

        try:
            deleted = await interaction.channel.purge(
                limit=amount
            )

            await interaction.followup.send(
                f"🧹 تم حذف **{len(deleted)}** رسالة.",
                ephemeral=True,
            )

            await self.send_log(
                interaction.guild,
                "مسح رسائل",
                None,
                interaction.user,
                f"تم حذف {len(deleted)} رسالة",
            )

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ ما عندي صلاحية حذف الرسائل.",
                ephemeral=True,
            )

        except discord.HTTPException:
            await interaction.followup.send(
                "❌ حدث خطأ أثناء حذف الرسائل.",
                ephemeral=True,
            )

    # =========================================================
    # TIMEOUT - Slash
    # =========================================================

    @app_commands.command(
        name="timeout",
        description="إعطاء عضو تايم أوت",
    )
    @app_commands.describe(
        member="العضو",
        minutes="المدة بالدقائق",
        reason="السبب",
    )
    async def slash_timeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        minutes: app_commands.Range[int, 1, 40320],
        reason: str = "بدون سبب",
    ):
        if not await self.check_slash_permission(
            interaction,
            "moderate_members",
        ):
            return

        allowed, error = await self.hierarchy_check(
            interaction.user,
            member,
        )

        if not allowed:
            await interaction.response.send_message(
                error,
                ephemeral=True,
            )
            return

        reason = self.reason_text(reason)

        try:
            until = (
                discord.utils.utcnow()
                + timedelta(minutes=minutes)
            )

            await member.timeout(
                until,
                reason=(
                    f"{reason} | بواسطة "
                    f"{interaction.user}"
                ),
            )

            await interaction.response.send_message(
                (
                    f"🔇 تم إعطاء {member.mention} "
                    f"تايم أوت لمدة **{minutes} دقيقة**."
                )
            )

            await self.send_log(
                interaction.guild,
                "تايم أوت",
                member,
                interaction.user,
                reason,
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ ما قدرت أعطي العضو تايم أوت.",
                ephemeral=True,
            )

        except discord.HTTPException:
            await interaction.response.send_message(
                "❌ حدث خطأ أثناء إعطاء التايم أوت.",
                ephemeral=True,
            )

    # =========================================================
    # UNTIMEOUT - Slash
    # =========================================================

    @app_commands.command(
        name="untimeout",
        description="إزالة التايم أوت من عضو",
    )
    @app_commands.describe(
        member="العضو",
    )
    async def slash_untimeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ):
        if not await self.check_slash_permission(
            interaction,
            "moderate_members",
        ):
            return

        allowed, error = await self.hierarchy_check(
            interaction.user,
            member,
        )

        if not allowed:
            await interaction.response.send_message(
                error,
                ephemeral=True,
            )
            return

        try:
            await member.timeout(
                None,
                reason=(
                    "إزالة التايم أوت بواسطة "
                    f"{interaction.user}"
                ),
            )

            await interaction.response.send_message(
                f"🔊 تم إزالة التايم أوت عن {member.mention}."
            )

            await self.send_log(
                interaction.guild,
                "إزالة تايم أوت",
                member,
                interaction.user,
                "تمت إزالة التايم أوت",
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ ما قدرت أزيل التايم أوت.",
                ephemeral=True,
            )

        except discord.HTTPException:
            await interaction.response.send_message(
                "❌ حدث خطأ أثناء إزالة التايم أوت.",
                ephemeral=True,
            )

    # =========================================================
    # LOCK - Slash
    # =========================================================

    @app_commands.command(
        name="lock",
        description="قفل الروم الحالي",
    )
    async def slash_lock(
        self,
        interaction: discord.Interaction,
    ):
        if not await self.check_slash_permission(
            interaction,
            "manage_channels",
        ):
            return

        channel = interaction.channel

        if not isinstance(
            channel,
            discord.TextChannel,
        ):
            await interaction.response.send_message(
                "❌ هذا الأمر يعمل في الرومات النصية فقط.",
                ephemeral=True,
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
                reason=(
                    f"قفل الروم بواسطة "
                    f"{interaction.user}"
                ),
            )

            await interaction.response.send_message(
                "🔒 تم قفل الروم."
            )

            await self.send_log(
                interaction.guild,
                "قفل روم",
                None,
                interaction.user,
                channel.mention,
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ ما عندي صلاحية تعديل صلاحيات الروم.",
                ephemeral=True,
            )

        except discord.HTTPException:
            await interaction.response.send_message(
                "❌ حدث خطأ أثناء قفل الروم.",
                ephemeral=True,
            )

    # =========================================================
    # UNLOCK - Slash
    # =========================================================

    @app_commands.command(
        name="unlock",
        description="فتح الروم الحالي",
    )
    async def slash_unlock(
        self,
        interaction: discord.Interaction,
    ):
        if not await self.check_slash_permission(
            interaction,
            "manage_channels",
        ):
            return

        channel = interaction.channel

        if not isinstance(
            channel,
            discord.TextChannel,
        ):
            await interaction.response.send_message(
                "❌ هذا الأمر يعمل في الرومات النصية فقط.",
                ephemeral=True,
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
                reason=(
                    f"فتح الروم بواسطة "
                    f"{interaction.user}"
                ),
            )

            await interaction.response.send_message(
                "🔓 تم فتح الروم."
            )

            await self.send_log(
                interaction.guild,
                "فتح روم",
                None,
                interaction.user,
                channel.mention,
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ ما عندي صلاحية تعديل صلاحيات الروم.",
                ephemeral=True,
            )

        except discord.HTTPException:
            await interaction.response.send_message(
                "❌ حدث خطأ أثناء فتح الروم.",
                ephemeral=True,
            )

    # =========================================================
    # Arabic Prefix Commands
    # =========================================================

    @commands.command(name="طرد")
    async def prefix_kick(
        self,
        ctx,
        member: discord.Member,
        *,
        reason: str = "بدون سبب",
    ):
        if not await self.check_prefix_permission(
            ctx,
            "kick_members",
        ):
            return

        allowed, error = await self.hierarchy_check(
            ctx.author,
            member,
        )

        if not allowed:
            await ctx.send(error)
            return

        reason = self.reason_text(reason)

        try:
            await member.kick(
                reason=(
                    f"{reason} | بواسطة "
                    f"{ctx.author}"
                )
            )

            await ctx.send(
                f"👢 تم طرد {member.mention}."
            )

            await self.send_log(
                ctx.guild,
                "طرد",
                member,
                ctx.author,
                reason,
            )

        except discord.Forbidden:
            await ctx.send(
                "❌ ما قدرت أطرد العضو."
            )

    @commands.command(name="حظر")
    async def prefix_ban(
        self,
        ctx,
        member: discord.Member,
        *,
        reason: str = "بدون سبب",
    ):
        if not await self.check_prefix_permission(
            ctx,
            "ban_members",
        ):
            return

        allowed, error = await self.hierarchy_check(
            ctx.author,
            member,
        )

        if not allowed:
            await ctx.send(error)
            return

        reason = self.reason_text(reason)

        try:
            await member.ban(
                reason=(
                    f"{reason} | بواسطة "
                    f"{ctx.author}"
                )
            )

            await ctx.send(
                f"🔨 تم حظر {member.mention}."
            )

            await self.send_log(
                ctx.guild,
                "حظر",
                member,
                ctx.author,
                reason,
            )

        except discord.Forbidden:
            await ctx.send(
                "❌ ما قدرت أحظر العضو."
            )

    @commands.command(name="فك_الحظر")
    async def prefix_unban(
        self,
        ctx,
        user_id: str,
        *,
        reason: str = "بدون سبب",
    ):
        if not await self.check_prefix_permission(
            ctx,
            "ban_members",
        ):
            return

        try:
            user_id = int(user_id)
        except ValueError:
            await ctx.send(
                "❌ الـ ID غير صحيح."
            )
            return

        try:
            user = await self.bot.fetch_user(
                user_id
            )

            reason = self.reason_text(reason)

            await ctx.guild.unban(
                user,
                reason=(
                    f"{reason} | بواسطة "
                    f"{ctx.author}"
                ),
            )

            await ctx.send(
                f"✅ تم فك الحظر عن `{user}`."
            )

            await self.send_log(
                ctx.guild,
                "فك حظر",
                user,
                ctx.author,
                reason,
            )

        except discord.NotFound:
            await ctx.send(
                "❌ المستخدم غير موجود في قائمة المحظورين."
            )

        except discord.Forbidden:
            await ctx.send(
                "❌ ما عندي صلاحية فك الحظر."
            )

    @commands.command(name="مسح")
    async def prefix_clear(
        self,
        ctx,
        amount: int,
    ):
        if not await self.check_prefix_permission(
            ctx,
            "manage_messages",
        ):
            return

        if amount < 1 or amount > 100:
            await ctx.send(
                "❌ العدد يجب أن يكون بين `1` و `100`."
            )
            return

        if not isinstance(
            ctx.channel,
            discord.TextChannel,
        ):
            return

        try:
            deleted = await ctx.channel.purge(
                limit=amount + 1
            )

            message = await ctx.send(
                f"🧹 تم حذف **{max(0, len(deleted) - 1)}** رسالة."
            )

            await message.delete(
                delay=3
            )

            await self.send_log(
                ctx.guild,
                "مسح رسائل",
                None,
                ctx.author,
                f"تم حذف {max(0, len(deleted) - 1)} رسالة",
            )

        except discord.Forbidden:
            await ctx.send(
                "❌ ما عندي صلاحية حذف الرسائل."
            )

    @commands.command(name="تايم")
    async def prefix_timeout(
        self,
        ctx,
        member: discord.Member,
        minutes: int,
        *,
        reason: str = "بدون سبب",
    ):
        if not await self.check_prefix_permission(
            ctx,
            "moderate_members",
        ):
            return

        if minutes < 1 or minutes > 40320:
            await ctx.send(
                "❌ المدة يجب أن تكون بين `1` و `40320` دقيقة."
            )
            return

        allowed, error = await self.hierarchy_check(
            ctx.author,
            member,
        )

        if not allowed:
            await ctx.send(error)
            return

        reason = self.reason_text(reason)

        try:
            until = (
                discord.utils.utcnow()
                + timedelta(minutes=minutes)
            )

            await member.timeout(
                until,
                reason=(
                    f"{reason} | بواسطة "
                    f"{ctx.author}"
                ),
            )

            await ctx.send(
                (
                    f"🔇 تم إعطاء {member.mention} "
                    f"تايم أوت لمدة **{minutes} دقيقة**."
                )
            )

            await self.send_log(
                ctx.guild,
                "تايم أوت",
                member,
                ctx.author,
                reason,
            )

        except discord.Forbidden:
            await ctx.send(
                "❌ ما قدرت أعطي العضو تايم أوت."
            )

    @commands.command(name="فك_تايم")
    async def prefix_untimeout(
        self,
        ctx,
        member: discord.Member,
    ):
        if not await self.check_prefix_permission(
            ctx,
            "moderate_members",
        ):
            return

        allowed, error = await self.hierarchy_check(
            ctx.author,
            member,
        )

        if not allowed:
            await ctx.send(error)
            return

        try:
            await member.timeout(
                None,
                reason=(
                    "إزالة التايم أوت بواسطة "
                    f"{ctx.author}"
                ),
            )

            await ctx.send(
                f"🔊 تم إزالة التايم أوت عن {member.mention}."
            )

            await self.send_log(
                ctx.guild,
                "إزالة تايم أوت",
                member,
                ctx.author,
                "تمت إزالة التايم أوت",
            )

        except discord.Forbidden:
            await ctx.send(
                "❌ ما قدرت أزيل التايم أوت."
            )

    @commands.command(name="قفل")
    async def prefix_lock(
        self,
        ctx,
    ):
        if not await self.check_prefix_permission(
            ctx,
            "manage_channels",
        ):
            return

        if not isinstance(
            ctx.channel,
            discord.TextChannel,
        ):
            return

        try:
            overwrite = ctx.channel.overwrites_for(
                ctx.guild.default_role
            )

            overwrite.send_messages = False

            await ctx.channel.set_permissions(
                ctx.guild.default_role,
                overwrite=overwrite,
                reason=(
                    f"قفل الروم بواسطة "
                    f"{ctx.author}"
                ),
            )

            await ctx.send(
                "🔒 تم قفل الروم."
            )

            await self.send_log(
                ctx.guild,
                "قفل روم",
                None,
                ctx.author,
                ctx.channel.mention,
            )

        except discord.Forbidden:
            await ctx.send(
                "❌ ما عندي صلاحية تعديل صلاحيات الروم."
            )

    @commands.command(name="فتح")
    async def prefix_unlock(
        self,
        ctx,
    ):
        if not await self.check_prefix_permission(
            ctx,
            "manage_channels",
        ):
            return

        if not isinstance(
            ctx.channel,
            discord.TextChannel,
        ):
            return

        try:
            overwrite = ctx.channel.overwrites_for(
                ctx.guild.default_role
            )

            overwrite.send_messages = None

            await ctx.channel.set_permissions(
                ctx.guild.default_role,
                overwrite=overwrite,
                reason=(
                    f"فتح الروم بواسطة "
                    f"{ctx.author}"
                ),
            )

            await ctx.send(
                "🔓 تم فتح الروم."
            )

            await self.send_log(
                ctx.guild,
                "فتح روم",
                None,
                ctx.author,
                ctx.channel.mention,
            )

        except discord.Forbidden:
            await ctx.send(
                "❌ ما عندي صلاحية تعديل صلاحيات الروم."
            )


# =========================================================
# Setup
# =========================================================

async def setup(bot: commands.Bot):
    await bot.add_cog(
        Moderation(bot)
    )
