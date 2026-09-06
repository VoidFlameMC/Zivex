import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands

from database import db


# =========================================================
# Application Database
# =========================================================

class ApplicationDatabase:

    async def setup(self):
        async with await db.connect() as connection:
            await connection.execute(
                """
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            await connection.commit()

    async def create_application(
        self,
        guild_id: int,
        user_id: int,
    ) -> int:
        async with await db.connect() as connection:
            cursor = await connection.execute(
                """
                INSERT INTO applications (
                    guild_id,
                    user_id,
                    message_id,
                    status
                )
                VALUES (?, ?, 0, 'pending')
                """,
                (
                    guild_id,
                    user_id,
                ),
            )

            await connection.commit()

            return cursor.lastrowid

    async def set_message_id(
        self,
        application_id: int,
        message_id: int,
    ):
        async with await db.connect() as connection:
            await connection.execute(
                """
                UPDATE applications
                SET message_id = ?
                WHERE id = ?
                """,
                (
                    message_id,
                    application_id,
                ),
            )

            await connection.commit()

    async def get_application(
        self,
        application_id: int,
    ):
        async with await db.connect() as connection:
            connection.row_factory = aiosqlite.Row

            cursor = await connection.execute(
                """
                SELECT *
                FROM applications
                WHERE id = ?
                """,
                (application_id,),
            )

            row = await cursor.fetchone()

            if not row:
                return None

            return dict(row)

    async def get_pending_for_user(
        self,
        guild_id: int,
        user_id: int,
    ):
        async with await db.connect() as connection:
            cursor = await connection.execute(
                """
                SELECT id
                FROM applications
                WHERE guild_id = ?
                AND user_id = ?
                AND status = 'pending'
                LIMIT 1
                """,
                (
                    guild_id,
                    user_id,
                ),
            )

            row = await cursor.fetchone()

            return row[0] if row else None

    async def set_status(
        self,
        application_id: int,
        status: str,
    ):
        async with await db.connect() as connection:
            await connection.execute(
                """
                UPDATE applications
                SET status = ?
                WHERE id = ?
                """,
                (
                    status,
                    application_id,
                ),
            )

            await connection.commit()

    async def delete_application(
        self,
        application_id: int,
    ):
        async with await db.connect() as connection:
            await connection.execute(
                """
                DELETE FROM applications
                WHERE id = ?
                """,
                (application_id,),
            )

            await connection.commit()

    async def get_pending_applications(self):
        async with await db.connect() as connection:
            connection.row_factory = aiosqlite.Row

            cursor = await connection.execute(
                """
                SELECT *
                FROM applications
                WHERE status = 'pending'
                AND message_id > 0
                """
            )

            rows = await cursor.fetchall()

            return [dict(row) for row in rows]


application_db = ApplicationDatabase()


# =========================================================
# Settings
# =========================================================

async def get_guild_settings(
    guild: discord.Guild,
):
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


# =========================================================
# Helpers
# =========================================================

def replace_variables(
    text: str,
    guild: discord.Guild,
    member: discord.Member | discord.User | None = None,
    application_id: int | None = None,
):
    if not text:
        return ""

    replacements = {
        "{server}": guild.name,
        "{member_count}": str(
            guild.member_count or 0
        ),
    }

    if member:
        replacements.update(
            {
                "{user}": member.mention,
                "{username}": member.display_name,
                "{user_id}": str(member.id),
            }
        )

    if application_id is not None:
        replacements[
            "{application_id}"
        ] = str(application_id)

    for key, value in replacements.items():
        text = text.replace(
            key,
            str(value),
        )

    return text


def parse_color(value):
    try:
        if not value:
            return discord.Color.blurple()

        value = (
            str(value)
            .strip()
            .replace("#", "")
        )

        if value.lower().startswith("0x"):
            value = value[2:]

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


def is_staff(
    member: discord.Member,
):
    return (
        member.guild_permissions.administrator
        or member.guild_permissions.manage_guild
    )


# =========================================================
# Application Review View
# =========================================================

class ApplicationReviewView(
    discord.ui.View
):

    def __init__(
        self,
        cog,
        application_id: int,
    ):
        super().__init__(
            timeout=None
        )

        self.cog = cog
        self.application_id = application_id

    # -----------------------------------------------------
    # Accept
    # -----------------------------------------------------

    @discord.ui.button(
        label="قبول",
        emoji="✅",
        style=discord.ButtonStyle.success,
        custom_id="zivex_application_accept",
    )
    async def accept_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ هذا الزر يعمل داخل السيرفر فقط.",
                ephemeral=True,
            )
            return

        if not isinstance(
            interaction.user,
            discord.Member,
        ):
            await interaction.response.send_message(
                "❌ تعذر التحقق من صلاحياتك.",
                ephemeral=True,
            )
            return

        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ ما عندك صلاحية للتعامل مع التقديمات.",
                ephemeral=True,
            )
            return

        application = (
            await application_db.get_application(
                self.application_id
            )
        )

        if not application:
            await interaction.response.send_message(
                "❌ هذا التقديم غير موجود.",
                ephemeral=True,
            )
            return

        if application["status"] != "pending":
            await interaction.response.send_message(
                "❌ تم التعامل مع هذا التقديم مسبقًا.",
                ephemeral=True,
            )
            return

        await application_db.set_status(
            self.application_id,
            "accepted",
        )

        if interaction.message.embeds:
            embed = (
                interaction.message.embeds[0].copy()
            )
        else:
            embed = discord.Embed(
                title="📝 تقديم"
            )

        embed.color = discord.Color.green()

        embed.add_field(
            name="📌 الحالة",
            value=(
                "✅ **مقبول**\n"
                f"بواسطة {interaction.user.mention}"
            ),
            inline=False,
        )

        try:
            await interaction.response.edit_message(
                embed=embed,
                view=None,
            )
        except discord.HTTPException:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "⚠️ تم قبول التقديم، لكن تعذر تحديث الرسالة.",
                    ephemeral=True,
                )

        await self.cog.notify_applicant(
            interaction.guild,
            application["user_id"],
            accepted=True,
        )

        await self.cog.send_log(
            interaction.guild,
            application,
            interaction.user,
            accepted=True,
        )

    # -----------------------------------------------------
    # Reject
    # -----------------------------------------------------

    @discord.ui.button(
        label="رفض",
        emoji="❌",
        style=discord.ButtonStyle.danger,
        custom_id="zivex_application_reject",
    )
    async def reject_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ هذا الزر يعمل داخل السيرفر فقط.",
                ephemeral=True,
            )
            return

        if not isinstance(
            interaction.user,
            discord.Member,
        ):
            await interaction.response.send_message(
                "❌ تعذر التحقق من صلاحياتك.",
                ephemeral=True,
            )
            return

        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ ما عندك صلاحية للتعامل مع التقديمات.",
                ephemeral=True,
            )
            return

        application = (
            await application_db.get_application(
                self.application_id
            )
        )

        if not application:
            await interaction.response.send_message(
                "❌ هذا التقديم غير موجود.",
                ephemeral=True,
            )
            return

        if application["status"] != "pending":
            await interaction.response.send_message(
                "❌ تم التعامل مع هذا التقديم مسبقًا.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(
            RejectApplicationModal(
                self.cog,
                self.application_id,
                application["user_id"],
                interaction.message,
            )
        )


# =========================================================
# Reject Modal
# =========================================================

class RejectApplicationModal(
    discord.ui.Modal
):

    def __init__(
        self,
        cog,
        application_id: int,
        user_id: int,
        application_message: discord.Message,
    ):
        super().__init__(
            title="رفض التقديم"
        )

        self.cog = cog
        self.application_id = application_id
        self.user_id = user_id
        self.application_message = (
            application_message
        )

        self.reason = discord.ui.TextInput(
            label="سبب الرفض",
            placeholder="اكتب سبب رفض التقديم...",
            required=True,
            min_length=2,
            max_length=500,
            style=discord.TextStyle.paragraph,
        )

        self.add_item(
            self.reason
        )

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ هذا النظام يعمل داخل السيرفر فقط.",
                ephemeral=True,
            )
            return

        if not isinstance(
            interaction.user,
            discord.Member,
        ):
            await interaction.response.send_message(
                "❌ تعذر التحقق من صلاحياتك.",
                ephemeral=True,
            )
            return

        if not is_staff(interaction.user):
            await interaction.response.send_message(
                "❌ ما عندك صلاحية للتعامل مع التقديمات.",
                ephemeral=True,
            )
            return

        application = (
            await application_db.get_application(
                self.application_id
            )
        )

        if not application:
            await interaction.response.send_message(
                "❌ هذا التقديم غير موجود.",
                ephemeral=True,
            )
            return

        if application["status"] != "pending":
            await interaction.response.send_message(
                "❌ تم التعامل مع هذا التقديم مسبقًا.",
                ephemeral=True,
            )
            return

        reason = str(
            self.reason.value
        ).strip()

        await application_db.set_status(
            self.application_id,
            "rejected",
        )

        if self.application_message.embeds:
            embed = (
                self.application_message.embeds[0].copy()
            )
        else:
            embed = discord.Embed(
                title="📝 تقديم"
            )

        embed.color = discord.Color.red()

        embed.add_field(
            name="📌 الحالة",
            value=(
                "❌ **مرفوض**\n"
                f"بواسطة {interaction.user.mention}"
            ),
            inline=False,
        )

        embed.add_field(
            name="📝 سبب الرفض",
            value=reason,
            inline=False,
        )

        try:
            await self.application_message.edit(
                embed=embed,
                view=None,
            )
        except discord.HTTPException:
            pass

        await self.cog.notify_applicant(
            interaction.guild,
            self.user_id,
            accepted=False,
            reason=reason,
        )

        await self.cog.send_log(
            interaction.guild,
            application,
            interaction.user,
            accepted=False,
            reason=reason,
        )

        await interaction.response.send_message(
            "✅ تم رفض التقديم وإرسال إشعار للمتقدم.",
            ephemeral=True,
        )


# =========================================================
# Application Panel
# =========================================================

class ApplicationPanelView(
    discord.ui.View
):

    def __init__(
        self,
        cog,
    ):
        super().__init__(
            timeout=None
        )

        self.cog = cog

    @discord.ui.button(
        label="تقديم",
        emoji="📝",
        style=discord.ButtonStyle.primary,
        custom_id="zivex_application_open",
    )
    async def open_application(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await self.cog.open_application_modal(
            interaction
        )


# =========================================================
# Application Modal
# =========================================================

class ApplicationModal(
    discord.ui.Modal
):

    def __init__(
        self,
        cog,
    ):
        super().__init__(
            title="تقديم Zivex"
        )

        self.cog = cog

        self.server_name = discord.ui.TextInput(
            label="اسمك في السيرفر",
            placeholder="اكتب اسمك في السيرفر...",
            required=True,
            min_length=2,
            max_length=100,
            style=discord.TextStyle.short,
        )

        self.experience = discord.ui.TextInput(
            label="خبرتك",
            placeholder="اذكر خبرتك السابقة...",
            required=True,
            min_length=2,
            max_length=1000,
            style=discord.TextStyle.paragraph,
        )

        self.reason = discord.ui.TextInput(
            label="سبب التقديم",
            placeholder="ليش حاب تنضم للفريق؟",
            required=True,
            min_length=2,
            max_length=1000,
            style=discord.TextStyle.paragraph,
        )

        self.why_you = discord.ui.TextInput(
            label="ليش نختارك؟",
            placeholder="اذكر الأشياء اللي تميزك...",
            required=True,
            min_length=2,
            max_length=1000,
            style=discord.TextStyle.paragraph,
        )

        self.extra = discord.ui.TextInput(
            label="معلومات إضافية",
            placeholder="أي شيء إضافي تبي تضيفه...",
            required=False,
            max_length=1000,
            style=discord.TextStyle.paragraph,
        )

        self.add_item(
            self.server_name
        )
        self.add_item(
            self.experience
        )
        self.add_item(
            self.reason
        )
        self.add_item(
            self.why_you
        )
        self.add_item(
            self.extra
        )

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ):
        await self.cog.submit_application(
            interaction,
            {
                "server_name": str(
                    self.server_name.value
                ),
                "experience": str(
                    self.experience.value
                ),
                "reason": str(
                    self.reason.value
                ),
                "why_you": str(
                    self.why_you.value
                ),
                "extra": str(
                    self.extra.value
                ),
            },
        )


# =========================================================
# Applications Cog
# =========================================================

class Applications(
    commands.Cog
):

    def __init__(
        self,
        bot: commands.Bot,
    ):
        self.bot = bot

    # =====================================================
    # Database
    # =====================================================

    async def setup_database(self):
        await application_db.setup()

    # =====================================================
    # Restore Views
    # =====================================================

    async def restore_pending_views(self):
        applications = (
            await application_db.get_pending_applications()
        )

        restored = 0

        for application in applications:
            try:
                view = ApplicationReviewView(
                    self,
                    application["id"],
                )

                self.bot.add_view(
                    view,
                    message_id=application["message_id"],
                )

                restored += 1

            except Exception as error:
                print(
                    "⚠️ Failed to restore application "
                    f"#{application['id']}: "
                    f"{type(error).__name__}: {error}"
                )

        if restored:
            print(
                f"✅ Restored {restored} pending application views."
            )

    # =====================================================
    # Application Channel
    # =====================================================

    async def get_application_channel(
        self,
        guild: discord.Guild,
    ):
        settings = await get_guild_settings(
            guild
        )

        if not settings:
            return None

        if not settings.get(
            "applications_enabled",
            0,
        ):
            return None

        channel_id = settings.get(
            "applications_channel_id"
        )

        if not channel_id:
            return None

        try:
            channel = guild.get_channel(
                int(channel_id)
            )
        except (
            ValueError,
            TypeError,
        ):
            return None

        if isinstance(
            channel,
            discord.TextChannel,
        ):
            return channel

        return None

    # =====================================================
    # Open Modal
    # =====================================================

    async def open_application_modal(
        self,
        interaction: discord.Interaction,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ هذا النظام يعمل داخل السيرفر فقط.",
                ephemeral=True,
            )
            return

        settings = await get_guild_settings(
            interaction.guild
        )

        if not settings:
            await interaction.response.send_message(
                "❌ تعذر تحميل إعدادات السيرفر.",
                ephemeral=True,
            )
            return

        if not settings.get(
            "applications_enabled",
            0,
        ):
            await interaction.response.send_message(
                "❌ نظام التقديمات غير مفعل في هذا السيرفر.",
                ephemeral=True,
            )
            return

        channel = await self.get_application_channel(
            interaction.guild
        )

        if channel is None:
            await interaction.response.send_message(
                "❌ لم يتم تحديد روم التقديمات من الـDashboard.",
                ephemeral=True,
            )
            return

        existing = (
            await application_db.get_pending_for_user(
                interaction.guild.id,
                interaction.user.id,
            )
        )

        if existing:
            await interaction.response.send_message(
                "❌ عندك تقديم قيد المراجعة بالفعل.\n"
                "يرجى انتظار رد الإدارة.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(
            ApplicationModal(self)
        )

    # =====================================================
    # Submit Application
    # =====================================================

    async def submit_application(
        self,
        interaction: discord.Interaction,
        answers: dict,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ هذا النظام يعمل داخل السيرفر فقط.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        member = interaction.user

        if not isinstance(
            member,
            discord.Member,
        ):
            await interaction.response.send_message(
                "❌ تعذر التحقق من العضو.",
                ephemeral=True,
            )
            return

        settings = await get_guild_settings(
            guild
        )

        if not settings:
            await interaction.response.send_message(
                "❌ تعذر تحميل إعدادات السيرفر.",
                ephemeral=True,
            )
            return

        if not settings.get(
            "applications_enabled",
            0,
        ):
            await interaction.response.send_message(
                "❌ نظام التقديمات غير مفعل.",
                ephemeral=True,
            )
            return

        channel = await self.get_application_channel(
            guild
        )

        if channel is None:
            await interaction.response.send_message(
                "❌ لم يتم تحديد روم التقديمات.",
                ephemeral=True,
            )
            return

        existing = (
            await application_db.get_pending_for_user(
                guild.id,
                member.id,
            )
        )

        if existing:
            await interaction.response.send_message(
                "❌ عندك تقديم قيد المراجعة بالفعل.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True
        )

        application_id = (
            await application_db.create_application(
                guild.id,
                member.id,
            )
        )

        title = (
            settings.get(
                "application_title"
            )
            or "📝 تقديم جديد"
        )

        message = (
            settings.get(
                "application_message"
            )
            or (
                "تم استلام تقديم جديد من {user}\n"
                "**رقم التقديم:** "
                "`#{application_id}`"
            )
        )

        title = replace_variables(
            title,
            guild,
            member,
            application_id,
        )

        message = replace_variables(
            message,
            guild,
            member,
            application_id,
        )

        embed = discord.Embed(
            title=title,
            description=message,
            color=parse_color(
                settings.get(
                    "application_color"
                )
            ),
            timestamp=discord.utils.utcnow(),
        )

        embed.add_field(
            name="👤 المتقدم",
            value=(
                f"{member.mention}\n"
                f"`{member}`\n"
                f"ID: `{member.id}`"
            ),
            inline=False,
        )

        embed.add_field(
            name="🎮 الاسم في السيرفر",
            value=answers["server_name"],
            inline=False,
        )

        embed.add_field(
            name="⭐ الخبرة",
            value=answers["experience"],
            inline=False,
        )

        embed.add_field(
            name="🎯 سبب التقديم",
            value=answers["reason"],
            inline=False,
        )

        embed.add_field(
            name="💡 ليش نختارك؟",
            value=answers["why_you"],
            inline=False,
        )

        if answers["extra"]:
            embed.add_field(
                name="📌 معلومات إضافية",
                value=answers["extra"],
                inline=False,
            )

        embed.add_field(
            name="📌 الحالة",
            value="⏳ **قيد المراجعة**",
            inline=False,
        )

        thumbnail = settings.get(
            "application_thumbnail"
        )

        if thumbnail:
            try:
                embed.set_thumbnail(
                    url=thumbnail
                )
            except Exception:
                pass
        elif guild.icon:
            embed.set_thumbnail(
                url=guild.icon.url
            )

        embed.set_footer(
            text=(
                settings.get(
                    "application_footer"
                )
                or f"Zivex • {guild.name}"
            )
        )

        view = ApplicationReviewView(
            self,
            application_id,
        )

        try:
            message_obj = await channel.send(
                content=member.mention,
                embed=embed,
                view=view,
                allowed_mentions=discord.AllowedMentions(
                    users=True,
                    roles=False,
                    everyone=False,
                ),
            )

        except discord.Forbidden:
            await application_db.delete_application(
                application_id
            )

            await interaction.followup.send(
                "❌ ما قدرت أرسل التقديم في الروم المحدد.\n"
                "تأكد من صلاحيات البوت.",
                ephemeral=True,
            )
            return

        except discord.HTTPException as error:
            await application_db.delete_application(
                application_id
            )

            print(
                f"⚠️ Application send error: {error}"
            )

            await interaction.followup.send(
                "❌ حدث خطأ أثناء إرسال التقديم.",
                ephemeral=True,
            )
            return

        await application_db.set_message_id(
            application_id,
            message_obj.id,
        )

        success_message = (
            settings.get(
                "application_success_message"
            )
            or (
                "✅ تم إرسال تقديمك بنجاح!\n"
                "يرجى انتظار رد الإدارة."
            )
        )

        success_message = replace_variables(
            success_message,
            guild,
            member,
            application_id,
        )

        await interaction.followup.send(
            success_message,
            ephemeral=True,
        )

        logs = self.bot.get_cog(
            "Logs"
        )

        if logs:
            try:
                await logs.send_log(
                    guild,
                    "📝 تقديم جديد",
                    (
                        f"تم إرسال تقديم جديد "
                        f"`#{application_id}`."
                    ),
                    color=parse_color(
                        settings.get(
                            "application_color"
                        )
                    ),
                    fields=[
                        {
                            "name": "👤 المتقدم",
                            "value": member.mention,
                            "inline": True,
                        },
                        {
                            "name": "📍 روم التقديمات",
                            "value": channel.mention,
                            "inline": True,
                        },
                        {
                            "name": "📌 الحالة",
                            "value": "⏳ قيد المراجعة",
                            "inline": True,
                        },
                    ],
                    user=member,
                )
            except Exception as error:
                print(
                    f"⚠️ Application log error: {error}"
                )

    # =====================================================
    # Notify Applicant
    # =====================================================

    async def notify_applicant(
        self,
        guild: discord.Guild,
        user_id: int,
        accepted: bool,
        reason: str = "",
    ):
        try:
            user = await self.bot.fetch_user(
                user_id
            )
        except (
            discord.NotFound,
            discord.HTTPException,
        ):
            return

        settings = await get_guild_settings(
            guild
        )

        member = guild.get_member(
            user_id
        )

        if accepted:
            message = (
                settings.get(
                    "application_accept_message"
                )
                or (
                    "🎉 تم قبول تقديمك في "
                    "**{server}**."
                )
            )

            description = replace_variables(
                message,
                guild,
                member,
            )

            embed = discord.Embed(
                title="🎉 تم قبول تقديمك",
                description=description,
                color=discord.Color.green(),
            )

        else:
            message = (
                settings.get(
                    "application_reject_message"
                )
                or (
                    "❌ تم رفض تقديمك في "
                    "**{server}**."
                )
            )

            description = replace_variables(
                message,
                guild,
                member,
            )

            embed = discord.Embed(
                title="❌ تم رفض تقديمك",
                description=description,
                color=discord.Color.red(),
            )

            if reason:
                embed.add_field(
                    name="📝 سبب الرفض",
                    value=reason,
                    inline=False,
                )

        if guild.icon:
            embed.set_thumbnail(
                url=guild.icon.url
            )

        embed.set_footer(
            text=f"Zivex • {guild.name}"
        )

        try:
            await user.send(
                embed=embed
            )
        except (
            discord.Forbidden,
            discord.HTTPException,
        ):
            pass

    # =====================================================
    # Logs
    # =====================================================

    async def send_log(
        self,
        guild: discord.Guild,
        application,
        moderator: discord.Member,
        accepted: bool,
        reason: str = "",
    ):
        logs = self.bot.get_cog(
            "Logs"
        )

        if not logs:
            return

        try:
            if accepted:
                title = "✅ تم قبول تقديم"

                description = (
                    f"تم قبول التقديم "
                    f"`#{application['id']}`."
                )

                color = discord.Color.green()

            else:
                title = "❌ تم رفض تقديم"

                description = (
                    f"تم رفض التقديم "
                    f"`#{application['id']}`."
                )

                color = discord.Color.red()

            fields = [
                {
                    "name": "👤 المتقدم",
                    "value": (
                        f"<@{application['user_id']}>"
                    ),
                    "inline": True,
                },
                {
                    "name": "👮 المسؤول",
                    "value": moderator.mention,
                    "inline": True,
                },
            ]

            if reason:
                fields.append(
                    {
                        "name": "📝 السبب",
                        "value": reason,
                        "inline": False,
                    }
                )

            await logs.send_log(
                guild,
                title,
                description,
                color=color,
                fields=fields,
                user=moderator,
            )

        except Exception as error:
            print(
                f"⚠️ Application log error: {error}"
            )

    # =====================================================
    # Panel Embed
    # =====================================================

    def create_panel_embed(
        self,
        guild: discord.Guild,
        settings,
    ):
        title = (
            settings.get(
                "application_title"
            )
            or "📝 التقديمات"
        )

        message = (
            settings.get(
                "application_message"
            )
            or (
                "حاب تنضم إلى فريق الإدارة؟\n\n"
                "اضغط على زر **تقديم** بالأسفل "
                "وعبّئ النموذج بالمعلومات المطلوبة."
            )
        )

        embed = discord.Embed(
            title=title,
            description=message,
            color=parse_color(
                settings.get(
                    "application_color"
                )
            ),
        )

        thumbnail = settings.get(
            "application_thumbnail"
        )

        if thumbnail:
            try:
                embed.set_thumbnail(
                    url=thumbnail
                )
            except Exception:
                pass

        elif guild.icon:
            embed.set_thumbnail(
                url=guild.icon.url
            )

        embed.set_footer(
            text=(
                settings.get(
                    "application_footer"
                )
                or f"Zivex • {guild.name}"
            )
        )

        return embed

    # =====================================================
    # Slash /application
    # =====================================================

    @app_commands.command(
        name="application",
        description="إرسال لوحة التقديمات",
    )
    @app_commands.default_permissions(
        manage_guild=True
    )
    async def slash_application(
        self,
        interaction: discord.Interaction,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ هذا الأمر يعمل داخل السيرفر فقط.",
                ephemeral=True,
            )
            return

        if not isinstance(
            interaction.user,
            discord.Member,
        ):
            await interaction.response.send_message(
                "❌ تعذر التحقق من صلاحياتك.",
                ephemeral=True,
            )
            return

        if not is_staff(
            interaction.user
        ):
            await interaction.response.send_message(
                "❌ تحتاج صلاحية إدارة السيرفر.",
                ephemeral=True,
            )
            return

        settings = await get_guild_settings(
            interaction.guild
        )

        if not settings:
            await interaction.response.send_message(
                "❌ تعذر تحميل إعدادات السيرفر.",
                ephemeral=True,
            )
            return

        if not settings.get(
            "applications_enabled",
            0,
        ):
            await interaction.response.send_message(
                "❌ نظام التقديمات غير مفعل من الموقع.",
                ephemeral=True,
            )
            return

        if not settings.get(
            "applications_channel_id"
        ):
            await interaction.response.send_message(
                "❌ حدد روم التقديمات من الـDashboard أولًا.",
                ephemeral=True,
            )
            return

        embed = self.create_panel_embed(
            interaction.guild,
            settings,
        )

        await interaction.response.send_message(
            embed=embed,
            view=ApplicationPanelView(self),
        )

    # =====================================================
    # Prefix !تقديم
    # =====================================================

    @commands.command(
        name="تقديم"
    )
    @commands.guild_only()
    async def prefix_application(
        self,
        ctx: commands.Context,
    ):
        if not isinstance(
            ctx.author,
            discord.Member,
        ):
            return

        if not is_staff(
            ctx.author
        ):
            await ctx.send(
                "❌ تحتاج صلاحية إدارة السيرفر."
            )
            return

        settings = await get_guild_settings(
            ctx.guild
        )

        if not settings:
            await ctx.send(
                "❌ تعذر تحميل إعدادات السيرفر."
            )
            return

        if not settings.get(
            "applications_enabled",
            0,
        ):
            await ctx.send(
                "❌ نظام التقديمات غير مفعل من الموقع."
            )
            return

        if not settings.get(
            "applications_channel_id"
        ):
            await ctx.send(
                "❌ حدد روم التقديمات من الـDashboard أولًا."
            )
            return

        embed = self.create_panel_embed(
            ctx.guild,
            settings,
        )

        await ctx.send(
            embed=embed,
            view=ApplicationPanelView(self),
        )


# =========================================================
# Setup
# =========================================================

async def setup(
    bot: commands.Bot,
):
    cog = Applications(bot)

    await cog.setup_database()

    bot.add_view(
        ApplicationPanelView(cog)
    )

    await cog.restore_pending_views()

    await bot.add_cog(cog)
