import discord
from discord import app_commands
from discord.ext import commands

from database import db


# =========================================================
# زر إغلاق التذكرة
# =========================================================

class TicketCloseView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="إغلاق التذكرة",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="zivex_ticket_close"
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        channel = interaction.channel

        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "❌ هذه ليست تذكرة.",
                ephemeral=True
            )
            return

        if not channel.name.startswith("ticket-"):
            await interaction.response.send_message(
                "❌ هذه القناة ليست تذكرة Zivex.",
                ephemeral=True
            )
            return

        member = interaction.user

        if (
            not member.guild_permissions.manage_channels
            and not channel.permissions_for(member).manage_channels
        ):
            await interaction.response.send_message(
                "❌ ما عندك صلاحية إغلاق التذكرة.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "🔒 سيتم إغلاق التذكرة خلال 5 ثوانٍ..."
        )

        await self.cog.close_ticket_after_delay(
            channel
        )


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
                value="support"
            ),
            discord.SelectOption(
                label="شكوى",
                description="لتقديم شكوى للإدارة",
                emoji="⚠️",
                value="complaint"
            ),
            discord.SelectOption(
                label="شراكة",
                description="لطلب شراكة مع السيرفر",
                emoji="🤝",
                value="partnership"
            )
        ]

        super().__init__(
            placeholder="اختر نوع التذكرة",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="zivex_ticket_type"
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):
        ticket_type = self.values[0]

        await self.cog.create_ticket(
            interaction,
            ticket_type
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
        "partnership": "شراكة"
    }

    # =========================================================
    # تجهيز السيرفر
    # =========================================================

    async def ensure_guild(
        self,
        guild: discord.Guild
    ):
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
                else ""
            )
        )

        return await db.get_guild(
            guild.id
        )

    # =========================================================
    # البحث عن تذكرة العضو
    # =========================================================

    def find_member_ticket(
        self,
        guild: discord.Guild,
        member: discord.Member
    ):
        for channel in guild.text_channels:
            if not channel.name.startswith("ticket-"):
                continue

            permissions = channel.permissions_for(
                member
            )

            if permissions.view_channel:
                return channel

        return None

    # =========================================================
    # إنشاء التذكرة
    # =========================================================

    async def create_ticket(
        self,
        interaction: discord.Interaction,
        ticket_type: str
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ هذا النظام يعمل داخل السيرفر فقط.",
                ephemeral=True
            )
            return

        guild = interaction.guild
        member = interaction.user

        if not isinstance(
            member,
            discord.Member
        ):
            await interaction.response.send_message(
                "❌ تعذر التحقق من العضو.",
                ephemeral=True
            )
            return

        settings = await self.ensure_guild(
            guild
        )

        if not settings["tickets_enabled"]:
            await interaction.response.send_message(
                "❌ نظام التذاكر غير مفعل في هذا السيرفر.",
                ephemeral=True
            )
            return

        existing_ticket = self.find_member_ticket(
            guild,
            member
        )

        if existing_ticket:
            await interaction.response.send_message(
                f"❌ عندك تذكرة مفتوحة بالفعل: {existing_ticket.mention}",
                ephemeral=True
            )
            return

        await interaction.response.defer(
            ephemeral=True
        )

        # =====================================================
        # البحث عن كاتيجوري التذاكر
        # =====================================================

        category = None

        category_names = [
            "🎫・𝗦𝚞𝚙𝚙𝚘𝚛𝚝",
            "🎫・Support",
            "Support"
        ]

        for name in category_names:
            category = discord.utils.get(
                guild.categories,
                name=name
            )

            if category:
                break

        # إنشاء الكاتيجوري إذا لم تكن موجودة
        if category is None:
            try:
                category = await guild.create_category(
                    "🎫・𝗦𝚞𝚙𝚙𝚘𝚛𝚝",
                    reason="إنشاء كاتيجوري تذاكر Zivex"
                )

            except discord.Forbidden:
                await interaction.followup.send(
                    "❌ ما عندي صلاحية إنشاء الكاتيجوري.",
                    ephemeral=True
                )
                return

        # =====================================================
        # رقم التذكرة
        # =====================================================

        ticket_number = 1
        existing_numbers = []

        for channel in guild.text_channels:
            if not channel.name.startswith("ticket-"):
                continue

            try:
                number = int(
                    channel.name.split("-")[-1]
                )

                existing_numbers.append(
                    number
                )

            except ValueError:
                continue

        if existing_numbers:
            ticket_number = max(
                existing_numbers
            ) + 1

        ticket_name = (
            f"ticket-{ticket_number}"
        )

        # =====================================================
        # الصلاحيات
        # =====================================================

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
                    embed_links=True
                )
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
                    embed_links=True
                )
            )

        # إعطاء الإدارة صلاحية رؤية التذاكر
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
                        embed_links=True
                    )
                )

        # =====================================================
        # إنشاء الروم
        # =====================================================

        try:
            channel = await guild.create_text_channel(
                ticket_name,
                category=category,
                overwrites=overwrites,
                reason=(
                    f"تذكرة {self.TICKET_NAMES.get(ticket_type, 'الدعم الفني')}"
                )
            )

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ ما قدرت أنشئ التذكرة. تأكد من صلاحيات البوت.",
                ephemeral=True
            )
            return

        # =====================================================
        # رسالة التذكرة
        # =====================================================

        ticket_title = self.TICKET_NAMES.get(
            ticket_type,
            "الدعم الفني"
        )

        embed = discord.Embed(
            title=f"🎫 {ticket_title}",
            description=(
                f"أهلًا {member.mention} 👋\n\n"
                "تم إنشاء تذكرتك بنجاح.\n"
                "اكتب تفاصيل طلبك هنا وانتظر رد الإدارة."
            ),
            color=discord.Color.blurple()
        )

        embed.add_field(
            name="📌 النوع",
            value=f"`{ticket_title}`",
            inline=True
        )

        embed.add_field(
            name="👤 صاحب التذكرة",
            value=member.mention,
            inline=True
        )

        if guild.icon:
            embed.set_thumbnail(
                url=guild.icon.url
            )

        embed.set_footer(
            text=f"Zivex • {guild.name}"
        )

        await channel.send(
            content=member.mention,
            embed=embed,
            view=TicketCloseView(self)
        )

        await interaction.followup.send(
            f"✅ تم إنشاء تذكرتك: {channel.mention}",
            ephemeral=True
        )

        await self.send_log(
            guild,
            (
                f"🎫 تم إنشاء التذكرة "
                f"{channel.mention} بواسطة "
                f"{member.mention}."
            )
        )

    # =========================================================
    # إغلاق التذكرة بعد 5 ثواني
    # =========================================================

    async def close_ticket_after_delay(
        self,
        channel: discord.TextChannel
    ):
        await discord.utils.sleep(5)

        await self.close_ticket(
            channel
        )

    # =========================================================
    # إغلاق التذكرة
    # =========================================================

    async def close_ticket(
        self,
        channel: discord.TextChannel
    ):
        guild = channel.guild

        await self.send_log(
            guild,
            (
                f"🔒 تم إغلاق التذكرة "
                f"`{channel.name}`."
            )
        )

        try:
            await channel.delete(
                reason="إغلاق تذكرة Zivex"
            )

        except discord.NotFound:
            pass

        except discord.Forbidden:
            pass

    # =========================================================
    # إرسال اللوق
    # =========================================================

    async def send_log(
        self,
        guild: discord.Guild,
        message: str
    ):
        settings = await db.get_guild(
            guild.id
        )

        if not settings:
            return

        if not settings["logs_enabled"]:
            return

        channel_id = settings["logs_channel_id"]

        if not channel_id:
            return

        channel = guild.get_channel(
            channel_id
        )

        if not isinstance(
            channel,
            discord.TextChannel
        ):
            return

        try:
            await channel.send(
                message
            )

        except discord.Forbidden:
            pass

    # =========================================================
    # /ticket
    # =========================================================

    @app_commands.command(
        name="ticket",
        description="إرسال لوحة التذاكر"
    )
    async def slash_ticket(
        self,
        interaction: discord.Interaction
    ):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ هذا الأمر يعمل داخل السيرفر فقط.",
                ephemeral=True
            )
            return

        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ تحتاج صلاحية إدارة السيرفر.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="🎫 تذاكر الدعم",
            description=(
                "مرحبًا بك في نظام التذاكر.\n\n"
                "اختر نوع التذكرة من القائمة بالأسفل:\n\n"
                "🛠️ **الدعم الفني**\n"
                "للحصول على المساعدة.\n\n"
                "⚠️ **شكوى**\n"
                "لتقديم شكوى للإدارة.\n\n"
                "🤝 **شراكة**\n"
                "لطلب شراكة مع السيرفر."
            ),
            color=discord.Color.blurple()
        )

        if interaction.guild.icon:
            embed.set_thumbnail(
                url=interaction.guild.icon.url
            )

        embed.set_footer(
            text=f"Zivex • {interaction.guild.name}"
        )

        await interaction.response.send_message(
            embed=embed,
            view=TicketPanelView(self)
        )

    # =========================================================
    # !تذكرة
    # =========================================================

    @commands.command(name="تذكرة")
    async def prefix_ticket(
        self,
        ctx: commands.Context
    ):
        if ctx.guild is None:
            await ctx.send(
                "❌ هذا الأمر يعمل داخل السيرفر فقط."
            )
            return

        if not ctx.author.guild_permissions.manage_guild:
            await ctx.send(
                "❌ تحتاج صلاحية إدارة السيرفر."
            )
            return

        embed = discord.Embed(
            title="🎫 تذاكر الدعم",
            description=(
                "مرحبًا بك في نظام التذاكر.\n\n"
                "اختر نوع التذكرة من القائمة بالأسفل:\n\n"
                "🛠️ **الدعم الفني**\n"
                "⚠️ **شكوى**\n"
                "🤝 **شراكة**"
            ),
            color=discord.Color.blurple()
        )

        if ctx.guild.icon:
            embed.set_thumbnail(
                url=ctx.guild.icon.url
            )

        embed.set_footer(
            text=f"Zivex • {ctx.guild.name}"
        )

        await ctx.send(
            embed=embed,
            view=TicketPanelView(self)
        )


# =========================================================
# Setup
# =========================================================

async def setup(
    bot: commands.Bot
):
    cog = Tickets(bot)

    # تسجيل الـ Views حتى تستمر الأزرار
    # بالعمل بعد إعادة تشغيل البوت
    bot.add_view(
        TicketPanelView(cog)
    )

    bot.add_view(
        TicketCloseView(cog)
    )

    await bot.add_cog(cog)
