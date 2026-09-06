import asyncio
import re
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from database import db


# =========================================================
# Helpers
# =========================================================

def clean_channel_name(name: str) -> str:
    name = name.lower()
    name = re.sub(r"[^a-z0-9\u0600-\u06ff\s-]", "", name)
    name = re.sub(r"\s+", "-", name)
    name = re.sub(r"-+", "-", name).strip("-")

    if not name:
        name = "ticket"

    return name[:70]


def parse_color(value):
    if not value:
        return discord.Color.blurple()

    try:
        value = str(value).strip().replace("#", "")

        if value.lower().startswith("0x"):
            value = value[2:]

        return discord.Color(int(value, 16))

    except (ValueError, TypeError):
        return discord.Color.blurple()


# =========================================================
# Ticket Cog
# =========================================================

class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ready = False

    # =========================================================
    # Database
    # =========================================================

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
                f"❌ [TICKETS] Database error: {error}"
            )
            return None

    # =========================================================
    # Permissions
    # =========================================================

    async def is_owner(self, user):
        try:
            return await self.bot.is_owner(user)
        except Exception:
            return False

    async def can_manage(self, member):
        if await self.is_owner(member):
            return True

        return (
            isinstance(member, discord.Member)
            and (
                member.guild_permissions.manage_guild
                or member.guild_permissions.manage_channels
            )
        )

    # =========================================================
    # Ticket Detection
    # =========================================================

    def is_ticket_channel(
        self,
        channel: discord.TextChannel,
    ):
        return (
            channel.name.startswith("ticket-")
            or channel.topic
            and channel.topic.startswith("ZIVEX_TICKET:")
        )

    def get_ticket_owner_id(
        self,
        channel: discord.TextChannel,
    ):
        if not channel.topic:
            return None

        match = re.search(
            r"ZIVEX_TICKET:(\d+)",
            channel.topic,
        )

        if not match:
            return None

        try:
            return int(match.group(1))
        except ValueError:
            return None

    # =========================================================
    # Category
    # =========================================================

    async def get_category(
        self,
        guild,
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
                ValueError,
                TypeError,
            ):
                pass

        category = discord.utils.get(
            guild.categories,
            name="🎫・𝗦𝚞𝚙𝚙𝚘𝚛𝚝",
        )

        if category:
            return category

        try:
            return await guild.create_category(
                "🎫・𝗦𝚞𝚙𝚙𝚘𝚛𝚝",
                reason="Zivex Ticket System",
            )
        except discord.Forbidden:
            return None

    # =========================================================
    # Create Ticket
    # =========================================================

    async def create_ticket(
        self,
        guild,
        member,
        ticket_type="support",
    ):
        settings = await self.get_settings(
            guild
        )

        if not settings:
            return None, "❌ تعذر تحميل إعدادات التذاكر."

        if not bool(
            settings.get(
                "tickets_enabled",
                0,
            )
        ):
            return None, "❌ نظام التذاكر غير مفعل."

        # Prevent duplicate tickets
        for channel in guild.text_channels:
            if not self.is_ticket_channel(channel):
                continue

            owner_id = self.get_ticket_owner_id(
                channel
            )

            if owner_id == member.id:
                return (
                    channel,
                    "⚠️ عندك تذكرة مفتوحة بالفعل.",
                )

        category = await self.get_category(
            guild,
            settings,
        )

        if not category:
            return (
                None,
                "❌ ما قدرت أحدد كاتيجوري التذاكر.",
            )

        staff_role = None

        role_names = (
            "Support",
            "𝗦𝚞𝚙𝚙𝚘𝚛𝚝",
            "Helper",
            "𝗛𝚎𝚕𝚙𝚎𝚛",
        )

        for role_name in role_names:
            staff_role = discord.utils.get(
                guild.roles,
                name=role_name,
            )

            if staff_role:
                break

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=False
            ),
            member: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                manage_messages=True,
            ),
        }

        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True,
            )

        safe_name = clean_channel_name(
            member.display_name
        )

        channel_name = (
            f"ticket-{safe_name}"
        )

        try:
            channel = await guild.create_text_channel(
                channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"ZIVEX_TICKET:{member.id}",
                reason=(
                    f"Ticket opened by {member}"
                ),
            )

        except discord.Forbidden:
            return (
                None,
                "❌ البوت ما عنده صلاحية إنشاء الرومات.",
            )

        except discord.HTTPException:
            return (
                None,
                "❌ حدث خطأ أثناء إنشاء التذكرة.",
            )

        title = (
            settings.get(
                "tickets_title"
            )
            or "🎫 تذكرتك"
        )

        message = (
            settings.get(
                "tickets_message"
            )
            or (
                "مرحبًا {user}!\n\n"
                "اكتب مشكلتك أو طلبك هنا، "
                "وسيتم الرد عليك من فريق الدعم."
            )
        )

        message = (
            message
            .replace(
                "{user}",
                member.mention,
            )
            .replace(
                "{username}",
                member.display_name,
            )
            .replace(
                "{server}",
                guild.name,
            )
        )

        embed = discord.Embed(
            title=title,
            description=message,
            color=parse_color(
                settings.get(
                    "tickets_color"
                )
            ),
            timestamp=discord.utils.utcnow(),
        )

        if bool(
            settings.get(
                "tickets_thumbnail",
                1,
            )
        ):
            embed.set_thumbnail(
                url=member.display_avatar.url
            )

        footer = (
            settings.get(
                "tickets_footer"
            )
            or "Zivex • Ticket System"
        )

        if guild.icon:
            embed.set_footer(
                text=footer,
                icon_url=guild.icon.url,
            )
        else:
            embed.set_footer(
                text=footer
            )

        view = TicketCloseView(
            self,
            member.id,
        )

        try:
            await channel.send(
                content=member.mention,
                embed=embed,
                view=view,
                allowed_mentions=discord.AllowedMentions(
                    users=True,
                    roles=False,
                    everyone=False,
                ),
            )

            logs = self.bot.get_cog("Logs")

            if logs:
                try:
                    await logs.ticket_created(
                        member,
                        channel,
                    )
                except Exception as error:
                    print(
                        f"⚠️ [TICKETS] Log error: {error}"
                    )

            return (
                channel,
                "✅ تم إنشاء تذكرتك بنجاح.",
            )

        except discord.HTTPException:
            try:
                await channel.delete(
                    reason="Ticket setup failed"
                )
            except Exception:
                pass

            return (
                None,
                "❌ حدث خطأ أثناء تجهيز التذكرة.",
            )

    # =========================================================
    # Close Ticket
    # =========================================================

    async def close_ticket(
        self,
        channel,
        closed_by,
    ):
        if not isinstance(
            channel,
            discord.TextChannel,
        ):
            return False, "❌ هذا ليس روم تذكرة."

        if not self.is_ticket_channel(channel):
            return False, "❌ هذا ليس روم تذكرة."

        settings = await self.get_settings(
            channel.guild
        )

        reason = "تم إغلاق التذكرة"

        try:
            await channel.edit(
                name=(
                    f"closed-{channel.name}"
                )[:100],
                reason=(
                    f"Ticket closed by "
                    f"{closed_by}"
                ),
            )

            overwrites = channel.overwrites_for(
                channel.guild.default_role
            )

            overwrites.view_channel = False

            await channel.set_permissions(
                channel.guild.default_role,
                overwrite=overwrites,
            )

            owner_id = self.get_ticket_owner_id(
                channel
            )

            if owner_id:
                owner = channel.guild.get_member(
                    owner_id
                )

                if owner:
                    owner_overwrite = (
                        channel.overwrites_for(
                            owner
                        )
                    )

                    owner_overwrite.view_channel = False
                    owner_overwrite.send_messages = False

                    await channel.set_permissions(
                        owner,
                        overwrite=owner_overwrite,
                    )

            if settings:
                close_message = (
                    settings.get(
                        "tickets_close_message"
                    )
                    or "🔒 تم إغلاق التذكرة."
                )
            else:
                close_message = (
                    "🔒 تم إغلاق التذكرة."
                )

            await channel.send(
                close_message
            )

            logs = self.bot.get_cog("Logs")

            if logs:
                try:
                    await logs.ticket_closed(
                        channel.guild,
                        channel.name,
                        closed_by,
                    )
                except Exception as error:
                    print(
                        f"⚠️ [TICKETS] Log error: {error}"
                    )

            await asyncio.sleep(3)

            try:
                await channel.delete(
                    reason=reason
                )
            except discord.Forbidden:
                return (
                    True,
                    "⚠️ تم إغلاق التذكرة، لكن البوت لا يستطيع حذف الروم.",
                )

            return (
                True,
                "✅ تم إغلاق التذكرة.",
            )

        except discord.Forbidden:
            return (
                False,
                "❌ ما عندي صلاحية تعديل أو حذف التذكرة.",
            )

        except discord.HTTPException:
            return (
                False,
                "❌ حدث خطأ أثناء إغلاق التذكرة.",
            )

    # =========================================================
    # Add Member
    # =========================================================

    async def add_member(
        self,
        channel,
        member,
    ):
        if not self.is_ticket_channel(channel):
            return False, "❌ هذا ليس روم تذكرة."

        try:
            await channel.set_permissions(
                member,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
            )

            return (
                True,
                f"✅ تمت إضافة {member.mention} للتذكرة.",
            )

        except discord.Forbidden:
            return (
                False,
                "❌ ما عندي صلاحية تعديل صلاحيات الروم.",
            )

    # =========================================================
    # Remove Member
    # =========================================================

    async def remove_member(
        self,
        channel,
        member,
    ):
        if not self.is_ticket_channel(channel):
            return False, "❌ هذا ليس روم تذكرة."

        owner_id = self.get_ticket_owner_id(
            channel
        )

        if owner_id == member.id:
            return (
                False,
                "❌ ما تقدر تحذف صاحب التذكرة.",
            )

        try:
            await channel.set_permissions(
                member,
                overwrite=None,
            )

            return (
                True,
                f"✅ تمت إزالة {member.mention} من التذكرة.",
            )

        except discord.Forbidden:
            return (
                False,
                "❌ ما عندي صلاحية تعديل صلاحيات الروم.",
            )

    # =========================================================
    # Persistent Views
    # =========================================================

    @commands.Cog.listener()
    async def on_ready(self):
        if self.ready:
            return

        self.ready = True

        try:
            await self.bot.tree.sync()
        except Exception as error:
            print(
                f"⚠️ [TICKETS] Slash sync error: {error}"
            )

        print("🎫 Ticket System: Ready")

    # =========================================================
    # Prefix: إنشاء تذكرة
    # =========================================================

    @commands.command(
        name="تذكرة",
    )
    async def prefix_ticket(
        self,
        ctx,
    ):
        channel, message = await self.create_ticket(
            ctx.guild,
            ctx.author,
        )

        if channel:
            await ctx.send(
                f"{message}\n{channel.mention}",
                delete_after=10,
            )
        else:
            await ctx.send(
                message,
                delete_after=8,
            )

    # =========================================================
    # Prefix: إغلاق
    # =========================================================

    @commands.command(
        name="اغلاق",
    )
    async def prefix_close(
        self,
        ctx,
    ):
        if not self.is_ticket_channel(
            ctx.channel
        ):
            await ctx.send(
                "❌ هذا الأمر يستخدم داخل التذاكر فقط."
            )
            return

        owner_id = self.get_ticket_owner_id(
            ctx.channel
        )

        if (
            owner_id != ctx.author.id
            and not await self.can_manage(
                ctx.author
            )
        ):
            await ctx.send(
                "❌ فقط صاحب التذكرة أو الإدارة يستطيع إغلاقها."
            )
            return

        success, message = await self.close_ticket(
            ctx.channel,
            ctx.author,
        )

        if not success:
            await ctx.send(message)

    # =========================================================
    # Prefix: إضافة
    # =========================================================

    @commands.command(
        name="اضافة",
    )
    async def prefix_add(
        self,
        ctx,
        member: discord.Member,
    ):
        if not self.is_ticket_channel(
            ctx.channel
        ):
            await ctx.send(
                "❌ هذا الأمر يستخدم داخل التذاكر فقط."
            )
            return

        if not await self.can_manage(
            ctx.author
        ):
            await ctx.send(
                "❌ تحتاج صلاحية إدارة السيرفر أو الرومات."
            )
            return

        success, message = await self.add_member(
            ctx.channel,
            member,
        )

        await ctx.send(message)

    # =========================================================
    # Prefix: حذف عضو
    # =========================================================

    @commands.command(
        name="حذف",
    )
    async def prefix_remove(
        self,
        ctx,
        member: discord.Member,
    ):
        if not self.is_ticket_channel(
            ctx.channel
        ):
            await ctx.send(
                "❌ هذا الأمر يستخدم داخل التذاكر فقط."
            )
            return

        if not await self.can_manage(
            ctx.author
        ):
            await ctx.send(
                "❌ تحتاج صلاحية إدارة السيرفر أو الرومات."
            )
            return

        success, message = await self.remove_member(
            ctx.channel,
            member,
        )

        await ctx.send(message)

    # =========================================================
    # Slash: Ticket
    # =========================================================

    @app_commands.command(
        name="ticket",
        description="إنشاء تذكرة دعم",
    )
    async def slash_ticket(
        self,
        interaction: discord.Interaction,
    ):
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ هذا الأمر داخل السيرفر فقط.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True
        )

        channel, message = await self.create_ticket(
            interaction.guild,
            interaction.user,
        )

        if channel:
            await interaction.followup.send(
                f"{message}\n{channel.mention}",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                message,
                ephemeral=True,
            )

    @app_commands.command(
        name="ticket-close",
        description="إغلاق التذكرة الحالية",
    )
    async def slash_close(
        self,
        interaction: discord.Interaction,
    ):
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ هذا الأمر داخل السيرفر فقط.",
                ephemeral=True,
            )
            return

        if not self.is_ticket_channel(
            interaction.channel
        ):
            await interaction.response.send_message(
                "❌ هذا الأمر يستخدم داخل التذاكر فقط.",
                ephemeral=True,
            )
            return

        owner_id = self.get_ticket_owner_id(
            interaction.channel
        )

        if (
            owner_id != interaction.user.id
            and not await self.can_manage(
                interaction.user
            )
        ):
            await interaction.response.send_message(
                "❌ فقط صاحب التذكرة أو الإدارة يستطيع إغلاقها.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "🔒 جاري إغلاق التذكرة..."
        )

        await self.close_ticket(
            interaction.channel,
            interaction.user,
        )

    @app_commands.command(
        name="ticket-add",
        description="إضافة عضو إلى التذكرة",
    )
    @app_commands.describe(
        member="العضو",
    )
    async def slash_add(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ):
        if not await self.can_manage(
            interaction.user
        ):
            await interaction.response.send_message(
                "❌ تحتاج صلاحية إدارة السيرفر أو الرومات.",
                ephemeral=True,
            )
            return

        if not self.is_ticket_channel(
            interaction.channel
        ):
            await interaction.response.send_message(
                "❌ هذا الأمر يستخدم داخل التذاكر فقط.",
                ephemeral=True,
            )
            return

        success, message = await self.add_member(
            interaction.channel,
            member,
        )

        await interaction.response.send_message(
            message
        )

    @app_commands.command(
        name="ticket-remove",
        description="إزالة عضو من التذكرة",
    )
    @app_commands.describe(
        member="العضو",
    )
    async def slash_remove(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ):
        if not await self.can_manage(
            interaction.user
        ):
            await interaction.response.send_message(
                "❌ تحتاج صلاحية إدارة السيرفر أو الرومات.",
                ephemeral=True,
            )
            return

        if not self.is_ticket_channel(
            interaction.channel
        ):
            await interaction.response.send_message(
                "❌ هذا الأمر يستخدم داخل التذاكر فقط.",
                ephemeral=True,
            )
            return

        success, message = await self.remove_member(
            interaction.channel,
            member,
        )

        await interaction.response.send_message(
            message
        )


# =========================================================
# Close Button
# =========================================================

class TicketCloseView(
    discord.ui.View
):
    def __init__(
        self,
        cog: Tickets,
        owner_id: int,
    ):
        super().__init__(
            timeout=None
        )

        self.cog = cog
        self.owner_id = owner_id

    @discord.ui.button(
        label="إغلاق التذكرة",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="zivex_ticket_close",
    )
    async def close_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        channel = interaction.channel

        if not isinstance(
            channel,
            discord.TextChannel,
        ):
            await interaction.response.send_message(
                "❌ هذا ليس روم تذكرة.",
                ephemeral=True,
            )
            return

        if not self.cog.is_ticket_channel(
            channel
        ):
            await interaction.response.send_message(
                "❌ هذه التذكرة غير صالحة.",
                ephemeral=True,
            )
            return

        is_owner = (
            interaction.user.id
            == self.owner_id
        )

        is_manager = await self.cog.can_manage(
            interaction.user
        )

        if not is_owner and not is_manager:
            await interaction.response.send_message(
                "❌ فقط صاحب التذكرة أو الإدارة يستطيع إغلاقها.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            "🔒 جاري إغلاق التذكرة..."
        )

        await self.cog.close_ticket(
            channel,
            interaction.user,
        )


# =========================================================
# Ticket Panel
# =========================================================

class TicketPanelView(
    discord.ui.View
):
    def __init__(
        self,
        cog: Tickets,
    ):
        super().__init__(
            timeout=None
        )

        self.cog = cog

    @discord.ui.button(
        label="فتح تذكرة",
        emoji="🎫",
        style=discord.ButtonStyle.primary,
        custom_id="zivex_ticket_open",
    )
    async def open_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.defer(
            ephemeral=True
        )

        channel, message = await self.cog.create_ticket(
            interaction.guild,
            interaction.user,
        )

        if channel:
            await interaction.followup.send(
                f"{message}\n{channel.mention}",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                message,
                ephemeral=True,
            )


# =========================================================
# Setup
# =========================================================

async def setup(bot: commands.Bot):
    cog = Tickets(bot)

    await bot.add_cog(cog)

    bot.add_view(
        TicketPanelView(cog)
    )
