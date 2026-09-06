import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from database import db


# =========================================================
# أدوات التذاكر
# =========================================================

class TicketCloseView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="إغلاق التذكرة",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="zivex_ticket_close",
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        channel = interaction.channel

        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "❌ هذه ليست تذكرة.",
                ephemeral=True,
            )
            return

        if not channel.name.startswith("ticket-"):
            await interaction.response.send_message(
                "❌ هذه القناة ليست تذكرة Zivex.",
                ephemeral=True,
            )
            return

        member = interaction.user

        if (
            not member.guild_permissions.manage_channels
            and not channel.permissions_for(member).manage_channels
        ):
            await interaction.response.send_message(
                "❌ ما عندك صلاحية إغلاق التذكرة.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "🔒 سيتم إغلاق التذكرة خلال 5 ثوانٍ..."
        )

        await self.cog.close_ticket_after_delay(channel)


# =========================================================
# قائمة أنواع التذاكر
# =========================================================

class TicketTypeSelect(discord.ui.Select):
    def __init__(self, cog):
        self.cog = cog

        options = [
            discord.SelectOption(
                label="الدعم الفني",
                description="إذا كنت تحتاج مساعدة من الإدارة",
                emoji="🛠️",
                value="support",
            ),
            discord.SelectOption(
                label="شكوى",
                description="لتقديم شكوى للإدارة",
                emoji="⚠️",
                value="complaint",
            ),
            discord.SelectOption(
                label="شراكة",
                description="لطلب شراكة مع السيرفر",
                emoji="🤝",
                value="partnership",
            ),
        ]

        super().__init__(
            placeholder="اختر نوع التذكرة",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="zivex_ticket_type",
        )

    async def callback(
        self,
        interaction: discord.Interaction,
    ):
        await self.cog.create_ticket(
            interaction,
            self.values[0],
        )


# =========================================================
# لوحة التذاكر
# =========================================================

class TicketPanelView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)

        self.add_item(
            TicketTypeSelect(cog)
        )


# =========================================================
# نظام التذاكر
# =========================================================

class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    TICKET_NAMES = {
        "support": "الدعم الفني",
        "complaint": "شكوى",
        "partnership": "شراكة",
    }

    # =========================================================
    # إعدادات السيرفر
    # =========================================================

    async def ensure_guild(
        self,
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
    # البحث عن تذكرة العضو
    # =========================================================

    def find_member_ticket(
        self,
        guild: discord.Guild,
        member: discord.Member,
    ):
        for channel in guild.text_channels:
            if not channel.name.startswith("ticket-"):
                continue

            if channel.permissions_for(member).view_channel:
                return channel

        return None

    # =========================================================
    # الحصول على كاتيجوري التذاكر
    # =========================================================

    async def get_ticket_category(
        self,
        guild: discord.Guild,
        settings,
    ):
        category_id = settings.get(
            "tickets_category_id"
        )

        if category_id:
            try:
                category = guild.get_channel(
                    int(category_id)
                )

                if isinstance(
                    category,
                    discord.CategoryChannel,
                ):
                    return category

            except (
                TypeError,
                ValueError,
            ):
                pass

        # البحث عن كاتيجوري موجودة
        category_names = [
            "🎫・𝗦𝚞𝚙𝚙𝚘𝚛𝚝",
            "🎫・Support",
            "Support",
        ]

        for name in category_names:
            category = discord.utils.get(
                guild.categories,
                name=name,
            )

            if category:
                await db.set_channel(
                    guild.id,
                    "ticket",
                    category.id,
                )
                return category

        # إنشاء كاتيجوري جديدة
        try:
            category = await guild.create_category(
                "🎫・𝗦𝚞𝚙𝚙𝚘𝚛𝚝",
                reason="إنشاء كاتيجوري تذاكر Zivex",
            )

            await db.set_channel(
                guild.id,
                "ticket",
                category.id,
            )

            return category

        except discord.Forbidden:
            return None

        except discord.HTTPException:
            return None

    # =========================================================
    # إنشاء التذكرة
    # =========================================================

    async def create_ticket(
        self,
        interaction: discord.Interaction,
        ticket_type: str,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ هذا النظام يعمل داخل السيرفر فقط.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        member = interaction.user

        if not isinstance(member, discord.Member):
            await interaction.response.send_message(
                "❌ تعذر التحقق من العضو.",
                ephemeral=True,
            )
            return

        settings = await self.ensure_guild(guild)

        if not settings.get(
            "tickets_enabled",
            0,
        ):
            await interaction.response.send_message(
                "❌ نظام التذاكر غير مفعل في هذا السيرفر.",
                ephemeral=True,
            )
            return

        existing_ticket = self.find_member_ticket(
            guild,
            member,
        )

        if existing_ticket:
            await interaction.response.send_message(
                f"❌ عندك تذكرة مفتوحة بالفعل: {existing_ticket.mention}",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True
        )

        # -----------------------------------------------------
        # الكاتيجوري
        # -----------------------------------------------------

        category = await self.get_ticket_category(
            guild,
            settings,
        )

        if category is None:
            await interaction.followup.send(
                "❌ ما قدرت أجد أو أنشئ كاتيجوري التذاكر.\n"
                "تأكد أن البوت عنده صلاحية **Manage Channels**.",
                ephemeral=True,
            )
            return

        # -----------------------------------------------------
        # رقم التذكرة
        # -----------------------------------------------------

        ticket_number = 1
        existing_numbers = []

        for channel in guild.text_channels:
            if not channel.name.startswith("ticket-"):
                continue

            try:
                number = int(
                    channel.name.split("-")[-1]
                )
                existing_numbers.append(number)

            except ValueError:
                continue

        if existing_numbers:
            ticket_number = max(
                existing_numbers
            ) + 1

        ticket_name = f"ticket-{ticket_number}"

        # -----------------------------------------------------
        # الصلاحيات
        # -----------------------------------------------------

        overwrites = {
            guild.default_role:
                discord.PermissionOverwrite(
                    view_channel=False
                ),

            member:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True,
                ),
        }

        bot_member = guild.me

        if bot_member:
            overwrites[bot_member] = (
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_channels=True,
                    manage_messages=True,
                    attach_files=True,
                    embed_links=True,
                )
            )

        # الإدارة
        for role in guild.roles:
            if role.is_default():
                continue

            if (
                role.permissions.administrator
                or role.permissions.manage_channels
                or role.permissions.manage_guild
            ):
                overwrites[role] = (
                    discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True,
                        attach_files=True,
                        embed_links=True,
                    )
                )

        # -----------------------------------------------------
        # إنشاء الروم
        # -----------------------------------------------------

        try:
            channel = await guild.create_text_channel(
                ticket_name,
                category=category,
                overwrites=overwrites,
                reason=(
                    f"تذكرة "
                    f"{self.TICKET_NAMES.get(ticket_type, 'الدعم الفني')}"
                ),
            )

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ ما قدرت أنشئ التذكرة.\n"
                "تأكد أن البوت عنده صلاحية **Manage Channels**.",
                ephemeral=True,
            )
            return

        except discord.HTTPException:
            await interaction.followup.send(
                "❌ حدث خطأ من Discord أثناء إنشاء التذكرة.",
                ephemeral=True,
            )
            return

        # -----------------------------------------------------
        # بيانات الرسالة من Dashboard
        # -----------------------------------------------------

        ticket_title = (
            settings.get("tickets_title")
            or "🎫 تذاكر الدعم"
        )

        ticket_message = (
            settings.get("tickets_message")
            or (
                "أهلًا {user} 👋\n\n"
                "تم إنشاء تذكرتك بنجاح.\n"
                "اكتب تفاصيل طلبك هنا وانتظر رد الإدارة."
            )
        )

        ticket_button_text = (
            settings.get("tickets_close_message")
            or "إغلاق التذكرة"
        )

        ticket_color = self.parse_color(
            settings.get("tickets_color")
        )

        ticket_title = self.replace_variables(
            ticket_title,
            member,
        )

        ticket_message = self.replace_variables(
            ticket_message,
            member,
        )

        # -----------------------------------------------------
        # Embed
        # -----------------------------------------------------

        embed = discord.Embed(
            title=ticket_title,
            description=ticket_message,
            color=ticket_color,
            timestamp=discord.utils.utcnow(),
        )

        embed.add_field(
            name="📌 النوع",
            value=(
                f"`{self.TICKET_NAMES.get(ticket_type, 'الدعم الفني')}`"
            ),
            inline=True,
        )

        embed.add_field(
            name="👤 صاحب التذكرة",
            value=member.mention,
            inline=True,
        )

        if guild.icon:
            embed.set_thumbnail(
                url=guild.icon.url
            )

        embed.set_footer(
            text=(
                settings.get("tickets_name")
                or f"Zivex • {guild.name}"
            )
        )

        # -----------------------------------------------------
        # زر الإغلاق
        # -----------------------------------------------------

        view = TicketCloseView(self)

        button = view.children[0]

        if isinstance(button, discord.ui.Button):
            if ticket_button_text:
                button.label = ticket_button_text

        # -----------------------------------------------------
        # إرسال التذكرة
        # -----------------------------------------------------

        try:
            await channel.send(
                content=member.mention,
                embed=embed,
                view=view,
            )

        except discord.Forbidden:
            try:
                await channel.delete(
                    reason="فشل إرسال رسالة التذكرة"
                )
            except Exception:
                pass

            await interaction.followup.send(
                "❌ تم إنشاء الروم لكن ما قدرت أرسل رسالة التذكرة.",
                ephemeral=True,
            )
            return

        # -----------------------------------------------------
        # الرد للعضو
        # -----------------------------------------------------

        await interaction.followup.send(
            f"✅ تم إنشاء تذكرتك: {channel.mention}",
            ephemeral=True,
        )

        # -----------------------------------------------------
        # Logs
        # -----------------------------------------------------

        logs = self.bot.get_cog("Logs")

        if logs:
            try:
                await logs.ticket_created(
                    member,
                    channel,
                )
            except Exception as error:
                print(
                    f"⚠️ Ticket log error: {error}"
                )

    # =========================================================
    # إغلاق بعد 5 ثواني
    # =========================================================

    async def close_ticket_after_delay(
        self,
        channel: discord.TextChannel,
    ):
        await asyncio.sleep(5)

        await self.close_ticket(channel)

    # =========================================================
    # إغلاق التذكرة
    # =========================================================

    async def close_ticket(
        self,
        channel: discord.TextChannel,
    ):
        guild = channel.guild

        # محاولة معرفة صاحب التذكرة
        ticket_owner = None

        for member in guild.members:
            if channel.permissions_for(
                member
            ).view_channel:
                if (
                    not member.bot
                    and not member.guild_permissions.manage_channels
                    and not member.guild_permissions.administrator
                ):
                    ticket_owner = member
                    break

        # Logs
        logs = self.bot.get_cog("Logs")

        if logs:
            try:
                await logs.ticket_closed(
                    guild,
                    channel.name,
                    ticket_owner,
                )
            except Exception as error:
                print(
                    f"⚠️ Ticket close log error: {error}"
                )

        try:
            await channel.delete(
                reason="إغلاق تذكرة Zivex",
            )

        except discord.NotFound:
            pass

        except discord.Forbidden:
            print(
                f"⚠️ No permission to delete "
                f"ticket {channel.id}"
            )

        except discord.HTTPException as error:
            print(
                f"⚠️ Ticket delete error: {error}"
            )

    # =========================================================
    # الألوان
    # =========================================================

    def parse_color(self, value):
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
    # المتغيرات
    # =========================================================

    def replace_variables(
        self,
        text: str,
        member: discord.Member,
    ):
        if not text:
            return ""

        guild = member.guild

        replacements = {
            "{user}": member.mention,
            "{username}": member.display_name,
            "{server}": guild.name,
            "{member_count}": str(
                guild.member_count or 0
            ),
        }

        for key, value in replacements.items():
            text = text.replace(
                key,
                str(value),
            )

        return text

    # =========================================================
    # /ticket
    # =========================================================

    @app_commands.command(
        name="ticket",
        description="إرسال لوحة التذاكر",
    )
    async def slash_ticket(
        self,
        interaction: discord.Interaction,
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ هذا الأمر يعمل داخل السيرفر فقط.",
                ephemeral=True,
            )
            return

        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ تحتاج صلاحية إدارة السيرفر.",
                ephemeral=True,
            )
            return

        settings = await self.ensure_guild(
            interaction.guild
        )

        if not settings.get(
            "tickets_enabled",
            0,
        ):
            await interaction.response.send_message(
                "❌ نظام التذاكر غير مفعل.",
                ephemeral=True,
            )
            return

        title = (
            settings.get("tickets_title")
            or "🎫 تذاكر الدعم"
        )

        message = (
            settings.get("tickets_message")
            or (
                "مرحبًا بك في نظام التذاكر.\n\n"
                "اختر نوع التذكرة من القائمة بالأسفل."
            )
        )

        embed = discord.Embed(
            title=title,
            description=message,
            color=self.parse_color(
                settings.get("tickets_color")
            ),
        )

        if interaction.guild.icon:
            embed.set_thumbnail(
                url=interaction.guild.icon.url
            )

        embed.set_footer(
            text=(
                settings.get("tickets_name")
                or f"Zivex • {interaction.guild.name}"
            )
        )

        await interaction.response.send_message(
            embed=embed,
            view=TicketPanelView(self),
        )

    # =========================================================
    # !تذكرة
    # =========================================================

    @commands.command(
        name="تذكرة"
    )
    @commands.guild_only()
    async def prefix_ticket(
        self,
        ctx: commands.Context,
    ):
        if not ctx.author.guild_permissions.manage_guild:
            await ctx.send(
                "❌ تحتاج صلاحية إدارة السيرفر."
            )
            return

        settings = await self.ensure_guild(
            ctx.guild
        )

        if not settings.get(
            "tickets_enabled",
            0,
        ):
            await ctx.send(
                "❌ نظام التذاكر غير مفعل."
            )
            return

        title = (
            settings.get("tickets_title")
            or "🎫 تذاكر الدعم"
        )

        message = (
            settings.get("tickets_message")
            or (
                "مرحبًا بك في نظام التذاكر.\n\n"
                "اختر نوع التذكرة من القائمة بالأسفل."
            )
        )

        embed = discord.Embed(
            title=title,
            description=message,
            color=self.parse_color(
                settings.get("tickets_color")
            ),
        )

        if ctx.guild.icon:
            embed.set_thumbnail(
                url=ctx.guild.icon.url
            )

        embed.set_footer(
            text=(
                settings.get("tickets_name")
                or f"Zivex • {ctx.guild.name}"
            )
        )

        await ctx.send(
            embed=embed,
            view=TicketPanelView(self),
        )

    # =========================================================
    # معالجة أخطاء الأوامر
    # =========================================================

    @slash_ticket.error
    async def slash_ticket_error(
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
            f"❌ Ticket slash error: {error}"
        )


# =========================================================
# Setup
# =========================================================

async def setup(
    bot: commands.Bot,
):
    cog = Tickets(bot)

    # إبقاء الأزرار والقائمة تعمل بعد إعادة تشغيل البوت
    bot.add_view(
        TicketPanelView(cog)
    )

    bot.add_view(
        TicketCloseView(cog)
    )

    await bot.add_cog(cog)
