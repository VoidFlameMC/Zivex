import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands

from database import db


# =========================================================
# قاعدة بيانات التقديمات
# =========================================================

class ApplicationDatabase:
    async def setup(self):
        async with await db.connect() as connection:
            await connection.execute("""
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
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
                (guild_id, user_id),
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
                (message_id, application_id),
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

            if row is None:
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
                (guild_id, user_id),
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
                (status, application_id),
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
# إعدادات السيرفر
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
    member: discord.Member,
):
    if not text:
        return ""

    replacements = {
        "{user}": member.mention,
        "{username}": member.display_name,
        "{server}": member.guild.name,
        "{member_count}": str(
            member.guild.member_count or 0
        ),
    }

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

        value = str(value).strip().replace(
            "#",
            "",
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
# View مراجعة التقديم
# =========================================================

class ApplicationReviewView(discord.ui.View):
    def __init__(
        self,
        cog,
        application_id: int,
        user_id: int,
    ):
        super().__init__(timeout=None)

        self.cog = cog
        self.application_id = application_id
        self.user_id = user_id

        accept_button = discord.ui.Button(
            label="قبول",
            emoji="✅",
            style=discord.ButtonStyle.success,
            custom_id=(
                f"zivex_application_accept_{application_id}"
            ),
        )

        reject_button = discord.ui.Button(
            label="رفض",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            custom_id=(
                f"zivex_application_reject_{application_id}"
            ),
        )

        accept_button.callback = self.accept_application
        reject_button.callback = self.reject_application

        self.add_item(accept_button)
        self.add_item(reject_button)

    async def check_staff(
        self,
        interaction: discord.Interaction,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ هذا الزر يعمل داخل السيرفر فقط.",
                ephemeral=True,
            )
            return False

        member = interaction.user

        if not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "❌ تعذر التحقق من صلاحياتك.",
                ephemeral=True,
            )
            return False

        if not (
            member.guild_permissions.administrator
            or member.guild_permissions.manage_guild
        ):
            await interaction.response.send_message(
                "❌ ما عندك صلاحية للتعامل مع التقديمات.",
                ephemeral=True,
            )
            return False

        return True

    # -----------------------------------------------------
    # قبول
    # -----------------------------------------------------

    async def accept_application(
        self,
        interaction: discord.Interaction,
    ):
        if not await self.check_staff(interaction):
            return

        application = await application_db.get_application(
            self.application_id
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
            embed = interaction.message.embeds[0].copy()
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

        logs = self.cog.bot.get_cog("Logs")

        if logs:
            try:
                await logs.application_received(
                    interaction.guild.get_member(
                        application["user_id"]
                    )
                    or await self.cog.bot.fetch_user(
                        application["user_id"]
                    )
                )
            except Exception:
                pass

            try:
                await logs.send_log(
                    interaction.guild,
                    "✅ تم قبول تقديم",
                    (
                        f"تم قبول التقديم "
                        f"`#{self.application_id}`."
                    ),
                    color=discord.Color.green(),
                    fields=[
                        {
                            "name": "👤 المتقدم",
                            "value": (
                                f"<@{application['user_id']}>"
                            ),
                            "inline": True,
                        },
                        {
                            "name": "👮 المسؤول",
                            "value": interaction.user.mention,
                            "inline": True,
                        },
                    ],
                    user=interaction.user,
                )
            except Exception as error:
                print(
                    f"⚠️ Application accept log error: {error}"
                )

    # -----------------------------------------------------
    # رفض
    # -----------------------------------------------------

    async def reject_application(
        self,
        interaction: discord.Interaction,
    ):
        if not await self.check_staff(interaction):
            return

        application = await application_db.get_application(
            self.application_id
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

        modal = RejectApplicationModal(
            self.cog,
            self.application_id,
            application["user_id"],
            interaction.message,
        )

        await interaction.response.send_modal(
            modal
        )


# =========================================================
# Modal الرفض
# =========================================================

class RejectApplicationModal(discord.ui.Modal):
    def __init__(
        self,
        cog,
        application_id: int,
        user_id: int,
        message: discord.Message,
    ):
        super().__init__(
            title="رفض التقديم"
        )

        self.cog = cog
        self.application_id = application_id
        self.user_id = user_id
        self.application_message = message

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
        application = await application_db.get_application(
            self.application_id
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
            "rejected",
        )

        reason = str(
            self.reason.value
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

        logs = self.cog.bot.get_cog("Logs")

        if logs:
            try:
                await logs.send_log(
                    interaction.guild,
                    "❌ تم رفض تقديم",
                    (
                        f"تم رفض التقديم "
                        f"`#{self.application_id}`."
                    ),
                    color=discord.Color.red(),
                    fields=[
                        {
                            "name": "👤 المتقدم",
                            "value": (
                                f"<@{self.user_id}>"
                            ),
                            "inline": True,
                        },
                        {
                            "name": "👮 المسؤول",
                            "value": interaction.user.mention,
                            "inline": True,
                        },
                        {
                            "name": "📝 السبب",
                            "value": reason,
                            "inline": False,
                        },
                    ],
                    user=interaction.user,
                )
            except Exception as error:
                print(
                    f"⚠️ Application reject log error: {error}"
                )

        await interaction.response.send_message(
            "✅ تم رفض التقديم وإرسال إشعار للمتقدم.",
            ephemeral=True,
        )


# =========================================================
# لوحة التقديمات
# =========================================================

class ApplicationPanelView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)

        self.cog = cog

        button = discord.ui.Button(
            label="تقديم",
            emoji="📝",
            style=discord.ButtonStyle.primary,
            custom_id="zivex_application_open",
        )

        button.callback = self.open_application

        self.add_item(button)

    async def open_application(
        self,
        interaction: discord.Interaction,
    ):
        await self.cog.open_application_modal(
            interaction
        )


# =========================================================
# نموذج التقديم
# =========================================================

class ApplicationModal(discord.ui.Modal):
    def __init__(self, cog):
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

        self.add_item(self.server_name)
        self.add_item(self.experience)
        self.add_item(self.reason)
        self.add_item(self.why_you)
        self.add_item(self.extra)

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

class Applications(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # =====================================================
    # Database
    # =====================================================

    async def setup_database(self):
        await application_db.setup()

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
                    application["user_id"],
                )

                self.bot.add_view(
                    view,
                    message_id=application["message_id"],
                )

                restored += 1

            except Exception as error:
                print(
                    "⚠️ Failed to restore application view "
                    f"#{application['id']}: "
                    f"{type(error).__name__}: {error}"
                )

        if restored:
            print(
                f"✅ Restored {restored} pending application views."
            )

    # =====================================================
    # قناة التقديمات
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
            TypeError,
            ValueError,
        ):
            return None

        if isinstance(
            channel,
            discord.TextChannel,
        ):
            return channel

        return None

    # =====================================================
    # فتح النموذج
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
                "❌ عندك تقديم قيد المراجعة بالفعل. "
                "يرجى انتظار رد الإدارة.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(
            ApplicationModal(self)
        )

    # =====================================================
    # إرسال التقديم
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
                "**رقم التقديم:** `#{application_id}`"
            )
        )

        title = replace_variables(
            title,
            member,
        )

        message = replace_variables(
            message,
            member,
        )

        message = message.replace(
            "{application_id}",
            str(application_id),
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
            member.id,
        )

        try:
            message_obj = await channel.send(
                content=member.mention,
                embed=embed,
                view=view,
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
            member,
        )

        success_message = success_message.replace(
            "{application_id}",
            str(application_id),
        )

        await interaction.followup.send(
            success_message,
            ephemeral=True,
        )

        # -------------------------------------------------
        # Logs
        # -------------------------------------------------

        logs = self.bot.get_cog("Logs")

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
    # إشعار المتقدم
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

        if accepted:
            message = (
                settings.get(
                    "application_accept_message"
                )
                or (
                    "🎉 تم قبول تقديمك في **{server}**."
                )
            )

            embed = discord.Embed(
                title="🎉 تم قبول تقديمك",
                description=replace_variables(
                    message,
                    guild.get_member(user_id)
                    or discord.Object(id=user_id),
                ),
                color=discord.Color.green(),
            )

        else:
            message = (
                settings.get(
                    "application_reject_message"
                )
                or (
                    "❌ تم رفض تقديمك في **{server}**."
                )
            )

            member = guild.get_member(
                user_id
            )

            if member:
                description = replace_variables(
                    message,
                    member,
                )
            else:
                description = message.replace(
                    "{server}",
                    guild.name,
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
    # إنشاء لوحة التقديم
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
    # /application
    # =====================================================

    @app_commands.command(
        name="application",
        description="إرسال لوحة التقديمات",
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

        if not (
            interaction.user.guild_permissions.administrator
            or interaction.user.guild_permissions.manage_guild
        ):
            await interaction.response.send_message(
                "❌ تحتاج صلاحية إدارة السيرفر.",
                ephemeral=True,
            )
            return

        settings = await get_guild_settings(
            interaction.guild
        )

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
    # !تقديم
    # =====================================================

    @commands.command(
        name="تقديم"
    )
    @commands.guild_only()
    async def prefix_application(
        self,
        ctx: commands.Context,
    ):
        if not (
            ctx.author.guild_permissions.administrator
            or ctx.author.guild_permissions.manage_guild
        ):
            await ctx.send(
                "❌ تحتاج صلاحية إدارة السيرفر."
            )
            return

        settings = await get_guild_settings(
            ctx.guild
        )

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

    # =====================================================
    # معالجة أخطاء Slash
    # =====================================================

    @slash_application.error
    async def slash_application_error(
        self,
        interaction: discord.Interaction,
        error,
    ):
        if isinstance(
            error,
            app_commands.errors.MissingPermissions,
        ):
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ تحتاج صلاحية إدارة السيرفر.",
                    ephemeral=True,
                )
            return

        print(
            f"❌ Application slash error: {error}"
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
