import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands

from database import db


# =========================================================
# Zivex Applications System
# =========================================================

APPLICATIONS_TABLE = "applications"


class ApplicationDatabase:
    """قاعدة بيانات خاصة بطلبات التقديم."""

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
        user_id: int
    ) -> int:
        async with await db.connect() as connection:
            cursor = await connection.execute("""
                INSERT INTO applications (
                    guild_id,
                    user_id,
                    message_id,
                    status
                )
                VALUES (?, ?, 0, 'pending')
            """, (guild_id, user_id))

            await connection.commit()

            return cursor.lastrowid

    async def set_message_id(
        self,
        application_id: int,
        message_id: int
    ):
        async with await db.connect() as connection:
            await connection.execute("""
                UPDATE applications
                SET message_id = ?
                WHERE id = ?
            """, (message_id, application_id))

            await connection.commit()

    async def get_application(
        self,
        application_id: int
    ):
        async with await db.connect() as connection:
            connection.row_factory = aiosqlite.Row

            cursor = await connection.execute("""
                SELECT *
                FROM applications
                WHERE id = ?
            """, (application_id,))

            row = await cursor.fetchone()

            if row is None:
                return None

            return dict(row)

    async def get_pending_for_user(
        self,
        guild_id: int,
        user_id: int
    ):
        async with await db.connect() as connection:
            cursor = await connection.execute("""
                SELECT id
                FROM applications
                WHERE guild_id = ?
                AND user_id = ?
                AND status = 'pending'
                LIMIT 1
            """, (guild_id, user_id))

            row = await cursor.fetchone()

            return row[0] if row else None

    async def set_status(
        self,
        application_id: int,
        status: str
    ):
        async with await db.connect() as connection:
            await connection.execute("""
                UPDATE applications
                SET status = ?
                WHERE id = ?
            """, (status, application_id))

            await connection.commit()

    async def delete_application(
        self,
        application_id: int
    ):
        async with await db.connect() as connection:
            await connection.execute("""
                DELETE FROM applications
                WHERE id = ?
            """, (application_id,))

            await connection.commit()

    async def get_pending_applications(self):
        async with await db.connect() as connection:
            connection.row_factory = aiosqlite.Row

            cursor = await connection.execute("""
                SELECT *
                FROM applications
                WHERE status = 'pending'
                AND message_id > 0
            """)

            rows = await cursor.fetchall()

            return [dict(row) for row in rows]


application_db = ApplicationDatabase()


# =========================================================
# Helpers
# =========================================================

async def get_guild_settings(guild: discord.Guild):
    settings = await db.get_guild(guild.id)

    if settings:
        return settings

    await db.ensure_guild(
        guild_id=guild.id,
        guild_name=guild.name,
        guild_icon=str(guild.icon.url)
        if guild.icon
        else ""
    )

    return await db.get_guild(guild.id)


def application_status_text(status: str):
    statuses = {
        "pending": "⏳ قيد المراجعة",
        "accepted": "✅ مقبول",
        "rejected": "❌ مرفوض"
    }

    return statuses.get(status, "❔ غير معروف")


# =========================================================
# Application Review View
# =========================================================

class ApplicationReviewView(discord.ui.View):
    def __init__(
        self,
        cog,
        application_id: int,
        user_id: int
    ):
        super().__init__(timeout=None)

        self.cog = cog
        self.application_id = application_id
        self.user_id = user_id

        accept_button = discord.ui.Button(
            label="قبول",
            emoji="✅",
            style=discord.ButtonStyle.success,
            custom_id=f"zivex_application_accept_{application_id}"
        )

        reject_button = discord.ui.Button(
            label="رفض",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            custom_id=f"zivex_application_reject_{application_id}"
        )

        accept_button.callback = self.accept_application
        reject_button.callback = self.reject_application

        self.add_item(accept_button)
        self.add_item(reject_button)

    async def check_staff(
        self,
        interaction: discord.Interaction
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ هذا الزر يعمل داخل السيرفر فقط.",
                ephemeral=True
            )
            return False

        member = interaction.user

        if not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "❌ تعذر التحقق من صلاحياتك.",
                ephemeral=True
            )
            return False

        if not (
            member.guild_permissions.administrator
            or member.guild_permissions.manage_guild
        ):
            await interaction.response.send_message(
                "❌ ما عندك صلاحية للتعامل مع التقديمات.",
                ephemeral=True
            )
            return False

        return True

    async def accept_application(
        self,
        interaction: discord.Interaction
    ):
        if not await self.check_staff(interaction):
            return

        application = await application_db.get_application(
            self.application_id
        )

        if not application:
            await interaction.response.send_message(
                "❌ هذا التقديم غير موجود.",
                ephemeral=True
            )
            return

        if application["status"] != "pending":
            await interaction.response.send_message(
                "❌ تم التعامل مع هذا التقديم مسبقًا.",
                ephemeral=True
            )
            return

        await application_db.set_status(
            self.application_id,
            "accepted"
        )

        embed = interaction.message.embeds[0].copy()

        embed.color = discord.Color.green()

        embed.add_field(
            name="📌 الحالة",
            value=(
                "✅ **مقبول**\n"
                f"بواسطة {interaction.user.mention}"
            ),
            inline=False
        )

        await interaction.response.edit_message(
            embed=embed,
            view=None
        )

        await self.cog.notify_applicant(
            interaction.guild,
            application["user_id"],
            accepted=True
        )

        await self.cog.send_log(
            interaction.guild,
            (
                f"✅ تم قبول التقديم `#{self.application_id}` "
                f"بواسطة {interaction.user.mention}."
            )
        )

    async def reject_application(
        self,
        interaction: discord.Interaction
    ):
        if not await self.check_staff(interaction):
            return

        application = await application_db.get_application(
            self.application_id
        )

        if not application:
            await interaction.response.send_message(
                "❌ هذا التقديم غير موجود.",
                ephemeral=True
            )
            return

        if application["status"] != "pending":
            await interaction.response.send_message(
                "❌ تم التعامل مع هذا التقديم مسبقًا.",
                ephemeral=True
            )
            return

        modal = RejectApplicationModal(
            self.cog,
            self.application_id,
            application["user_id"],
            interaction.message
        )

        await interaction.response.send_modal(modal)


# =========================================================
# Reject Modal
# =========================================================

class RejectApplicationModal(discord.ui.Modal):
    def __init__(
        self,
        cog,
        application_id: int,
        user_id: int,
        message: discord.Message
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
            style=discord.TextStyle.paragraph
        )

        self.add_item(self.reason)

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):
        application = await application_db.get_application(
            self.application_id
        )

        if not application:
            await interaction.response.send_message(
                "❌ هذا التقديم غير موجود.",
                ephemeral=True
            )
            return

        if application["status"] != "pending":
            await interaction.response.send_message(
                "❌ تم التعامل مع هذا التقديم مسبقًا.",
                ephemeral=True
            )
            return

        await application_db.set_status(
            self.application_id,
            "rejected"
        )

        reason = str(self.reason.value)

        if self.application_message.embeds:
            embed = self.application_message.embeds[0].copy()
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
            inline=False
        )

        embed.add_field(
            name="📝 سبب الرفض",
            value=reason,
            inline=False
        )

        try:
            await self.application_message.edit(
                embed=embed,
                view=None
            )
        except discord.HTTPException:
            pass

        await self.cog.notify_applicant(
            interaction.guild,
            self.user_id,
            accepted=False,
            reason=reason
        )

        await self.cog.send_log(
            interaction.guild,
            (
                f"❌ تم رفض التقديم `#{self.application_id}` "
                f"بواسطة {interaction.user.mention}."
            )
        )

        await interaction.response.send_message(
            "✅ تم رفض التقديم وإرسال إشعار للمتقدم.",
            ephemeral=True
        )


# =========================================================
# Application Panel
# =========================================================

class ApplicationPanelView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

        button = discord.ui.Button(
            label="تقديم",
            emoji="📝",
            style=discord.ButtonStyle.primary,
            custom_id="zivex_application_open"
        )

        button.callback = self.open_application

        self.add_item(button)

    async def open_application(
        self,
        interaction: discord.Interaction
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ هذا النظام يعمل داخل السيرفر فقط.",
                ephemeral=True
            )
            return

        await self.cog.open_application_modal(
            interaction
        )


# =========================================================
# Application Modal
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
            style=discord.TextStyle.short
        )

        self.experience = discord.ui.TextInput(
            label="خبرتك",
            placeholder="اذكر خبرتك السابقة...",
            required=True,
            min_length=2,
            max_length=1000,
            style=discord.TextStyle.paragraph
        )

        self.reason = discord.ui.TextInput(
            label="سبب التقديم",
            placeholder="ليش حاب تنضم للفريق؟",
            required=True,
            min_length=2,
            max_length=1000,
            style=discord.TextStyle.paragraph
        )

        self.why_you = discord.ui.TextInput(
            label="ليش نختارك؟",
            placeholder="اذكر الأشياء اللي تميزك...",
            required=True,
            min_length=2,
            max_length=1000,
            style=discord.TextStyle.paragraph
        )

        self.extra = discord.ui.TextInput(
            label="معلومات إضافية",
            placeholder="أي شيء إضافي تبي تضيفه...",
            required=False,
            max_length=1000,
            style=discord.TextStyle.paragraph
        )

        self.add_item(self.server_name)
        self.add_item(self.experience)
        self.add_item(self.reason)
        self.add_item(self.why_you)
        self.add_item(self.extra)

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):
        await self.cog.submit_application(
            interaction,
            {
                "server_name": str(self.server_name.value),
                "experience": str(self.experience.value),
                "reason": str(self.reason.value),
                "why_you": str(self.why_you.value),
                "extra": str(self.extra.value)
            }
        )


# =========================================================
# Applications Cog
# =========================================================

class Applications(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # -----------------------------------------------------
    # Database
    # -----------------------------------------------------

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
                    application["user_id"]
                )

                self.bot.add_view(
                    view,
                    message_id=application["message_id"]
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

    # -----------------------------------------------------
    # Helpers
    # -----------------------------------------------------

    async def get_application_channel(
        self,
        guild: discord.Guild
    ):
        settings = await get_guild_settings(guild)

        if not settings:
            return None

        if not settings["applications_enabled"]:
            return None

        channel_id = settings["applications_channel_id"]

        if not channel_id:
            return None

        channel = guild.get_channel(channel_id)

        if isinstance(channel, discord.TextChannel):
            return channel

        return None

    async def open_application_modal(
        self,
        interaction: discord.Interaction
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ هذا النظام يعمل داخل السيرفر فقط.",
                ephemeral=True
            )
            return

        settings = await get_guild_settings(
            interaction.guild
        )

        if not settings:
            await interaction.response.send_message(
                "❌ تعذر تحميل إعدادات السيرفر.",
                ephemeral=True
            )
            return

        if not settings["applications_enabled"]:
            await interaction.response.send_message(
                "❌ نظام التقديمات غير مفعل في هذا السيرفر.",
                ephemeral=True
            )
            return

        channel_id = settings["applications_channel_id"]

        if not channel_id:
            await interaction.response.send_message(
                "❌ الإدارة لم تحدد روم التقديمات من الموقع بعد.",
                ephemeral=True
            )
            return

        channel = interaction.guild.get_channel(channel_id)

        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "❌ روم التقديمات المحدد من الموقع غير موجود أو غير صالح.",
                ephemeral=True
            )
            return

        existing = await application_db.get_pending_for_user(
            interaction.guild.id,
            interaction.user.id
        )

        if existing:
            await interaction.response.send_message(
                "❌ عندك تقديم قيد المراجعة بالفعل. يرجى انتظار رد الإدارة.",
                ephemeral=True
            )
            return

        await interaction.response.send_modal(
            ApplicationModal(self)
        )

    async def submit_application(
        self,
        interaction: discord.Interaction,
        answers: dict
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ هذا النظام يعمل داخل السيرفر فقط.",
                ephemeral=True
            )
            return

        guild = interaction.guild
        member = interaction.user

        settings = await get_guild_settings(guild)

        if not settings:
            await interaction.response.send_message(
                "❌ تعذر تحميل إعدادات السيرفر.",
                ephemeral=True
            )
            return

        if not settings["applications_enabled"]:
            await interaction.response.send_message(
                "❌ نظام التقديمات غير مفعل.",
                ephemeral=True
            )
            return

        channel_id = settings["applications_channel_id"]

        if not channel_id:
            await interaction.response.send_message(
                "❌ لم يتم تحديد روم التقديمات من الموقع.",
                ephemeral=True
            )
            return

        channel = guild.get_channel(channel_id)

        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "❌ روم التقديمات المحدد من الموقع غير موجود.",
                ephemeral=True
            )
            return

        existing = await application_db.get_pending_for_user(
            guild.id,
            member.id
        )

        if existing:
            await interaction.response.send_message(
                "❌ عندك تقديم قيد المراجعة بالفعل.",
                ephemeral=True
            )
            return

        await interaction.response.defer(
            ephemeral=True
        )

        application_id = await application_db.create_application(
            guild.id,
            member.id
        )

        embed = discord.Embed(
            title="📝 تقديم جديد",
            description=(
                f"تم استلام تقديم جديد من {member.mention}\n"
                f"**رقم التقديم:** `#{application_id}`"
            ),
            color=discord.Color.blurple()
        )

        embed.add_field(
            name="👤 المتقدم",
            value=(
                f"{member.mention}\n"
                f"`{member}`\n"
                f"ID: `{member.id}`"
            ),
            inline=False
        )

        embed.add_field(
            name="🎮 الاسم في السيرفر",
            value=answers["server_name"],
            inline=False
        )

        embed.add_field(
            name="⭐ الخبرة",
            value=answers["experience"],
            inline=False
        )

        embed.add_field(
            name="🎯 سبب التقديم",
            value=answers["reason"],
            inline=False
        )

        embed.add_field(
            name="💡 ليش نختارك؟",
            value=answers["why_you"],
            inline=False
        )

        if answers["extra"]:
            embed.add_field(
                name="📌 معلومات إضافية",
                value=answers["extra"],
                inline=False
            )

        embed.add_field(
            name="📌 الحالة",
            value="⏳ **قيد المراجعة**",
            inline=False
        )

        if guild.icon:
            embed.set_thumbnail(
                url=guild.icon.url
            )

        embed.set_footer(
            text=f"Zivex • {guild.name}"
        )

        view = ApplicationReviewView(
            self,
            application_id,
            member.id
        )

        try:
            message = await channel.send(
                content=member.mention,
                embed=embed,
                view=view
            )

        except discord.Forbidden:
            await application_db.delete_application(
                application_id
            )

            await interaction.followup.send(
                (
                    "❌ ما قدرت أرسل التقديم في الروم المحدد.\n"
                    "تأكد أن البوت عنده صلاحية **View Channel** و "
                    "**Send Messages** و **Embed Links**."
                ),
                ephemeral=True
            )
            return

        except discord.HTTPException:
            await application_db.delete_application(
                application_id
            )

            await interaction.followup.send(
                "❌ حدث خطأ أثناء إرسال التقديم. حاول مرة ثانية.",
                ephemeral=True
            )
            return

        await application_db.set_message_id(
            application_id,
            message.id
        )

        await interaction.followup.send(
            (
                "✅ **تم إرسال تقديمك بنجاح!**\n"
                "يرجى انتظار رد الإدارة."
            ),
            ephemeral=True
        )

        await self.send_log(
            guild,
            (
                f"📝 تم إرسال تقديم جديد `#{application_id}` "
                f"من {member.mention} إلى {channel.mention}."
            )
        )

    async def notify_applicant(
        self,
        guild: discord.Guild,
        user_id: int,
        accepted: bool,
        reason: str = ""
    ):
        try:
            user = await self.bot.fetch_user(user_id)
        except (discord.NotFound, discord.HTTPException):
            return

        if accepted:
            embed = discord.Embed(
                title="🎉 تم قبول تقديمك",
                description=(
                    f"تم قبول تقديمك في **{guild.name}**.\n"
                    "تواصل مع الإدارة لمعرفة الخطوات القادمة."
                ),
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="❌ تم رفض تقديمك",
                description=(
                    f"تم رفض تقديمك في **{guild.name}**."
                ),
                color=discord.Color.red()
            )

            if reason:
                embed.add_field(
                    name="📝 السبب",
                    value=reason,
                    inline=False
                )

        if guild.icon:
            embed.set_thumbnail(
                url=guild.icon.url
            )

        embed.set_footer(
            text=f"Zivex • {guild.name}"
        )

        try:
            await user.send(embed=embed)
        except discord.Forbidden:
            pass
        except discord.HTTPException:
            pass

    async def send_log(
        self,
        guild: discord.Guild,
        message: str
    ):
        settings = await db.get_guild(guild.id)

        if not settings:
            return

        if not settings["logs_enabled"]:
            return

        channel_id = settings["logs_channel_id"]

        if not channel_id:
            return

        channel = guild.get_channel(channel_id)

        if not isinstance(channel, discord.TextChannel):
            return

        try:
            await channel.send(message)
        except discord.Forbidden:
            pass

    # -----------------------------------------------------
    # Application Panel
    # -----------------------------------------------------

    def create_panel_embed(
        self,
        guild: discord.Guild
    ):
        embed = discord.Embed(
            title="📝 التقديمات",
            description=(
                "حاب تنضم إلى فريق الإدارة؟\n\n"
                "اضغط على زر **تقديم** بالأسفل وعبّئ النموذج "
                "بكل المعلومات المطلوبة.\n\n"
                "بعد الإرسال، سيتم إرسال طلبك للإدارة "
                "في روم التقديمات المحدد من الموقع.\n\n"
                "⏳ **يرجى انتظار رد الإدارة بعد التقديم.**"
            ),
            color=discord.Color.blurple()
        )

        if guild.icon:
            embed.set_thumbnail(
                url=guild.icon.url
            )

        embed.set_footer(
            text=f"Zivex • {guild.name}"
        )

        return embed

    @app_commands.command(
        name="application",
        description="إرسال لوحة التقديمات"
    )
    async def slash_application(
        self,
        interaction: discord.Interaction
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ هذا الأمر يعمل داخل السيرفر فقط.",
                ephemeral=True
            )
            return

        if not (
            interaction.user.guild_permissions.administrator
            or interaction.user.guild_permissions.manage_guild
        ):
            await interaction.response.send_message(
                "❌ تحتاج صلاحية إدارة السيرفر.",
                ephemeral=True
            )
            return

        settings = await get_guild_settings(
            interaction.guild
        )

        if not settings["applications_enabled"]:
            await interaction.response.send_message(
                "❌ نظام التقديمات غير مفعل من الموقع.",
                ephemeral=True
            )
            return

        if not settings["applications_channel_id"]:
            await interaction.response.send_message(
                "❌ حدد روم التقديمات من الموقع أولًا.",
                ephemeral=True
            )
            return

        embed = self.create_panel_embed(
            interaction.guild
        )

        await interaction.response.send_message(
            embed=embed,
            view=ApplicationPanelView(self)
        )

    @commands.command(name="تقديم")
    async def prefix_application(
        self,
        ctx: commands.Context
    ):
        if ctx.guild is None:
            await ctx.send(
                "❌ هذا الأمر يعمل داخل السيرفر فقط."
            )
            return

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

        if not settings["applications_enabled"]:
            await ctx.send(
                "❌ نظام التقديمات غير مفعل من الموقع."
            )
            return

        if not settings["applications_channel_id"]:
            await ctx.send(
                "❌ حدد روم التقديمات من الموقع أولًا."
            )
            return

        embed = self.create_panel_embed(
            ctx.guild
        )

        await ctx.send(
            embed=embed,
            view=ApplicationPanelView(self)
        )


# =========================================================
# Setup
# =========================================================

async def setup(bot: commands.Bot):
    cog = Applications(bot)

    await cog.setup_database()

    bot.add_view(
        ApplicationPanelView(cog)
    )

    await cog.restore_pending_views()

    await bot.add_cog(cog)
