import asyncio
import os
from typing import Any, Optional

import aiosqlite

from config import DATABASE_URL


DEFAULT_DATABASE = "zivex.db"


class Database:
    def __init__(self, database_name: str = DEFAULT_DATABASE):
        self.database_name = database_name

        # يمنع عمليات الكتابة المتزامنة على SQLite
        self._write_lock = asyncio.Lock()

    # =========================================================
    # Database Path
    # =========================================================

    def get_database_path(self) -> str:
        database_url = (DATABASE_URL or "").strip()

        if not database_url:
            return self.database_name

        if database_url.startswith("sqlite:///"):
            path = database_url[len("sqlite:///"):]
            return path or self.database_name

        if database_url.startswith("sqlite://"):
            path = database_url[len("sqlite://"):]
            return path or self.database_name

        return database_url

    # =========================================================
    # Connection
    # =========================================================

    def connect(self):
        """
        مهم:
        هذه الدالة ليست async.

        aiosqlite.connect() يرجع Connection غير مشغّل.
        تشغيله يتم مرة واحدة فقط بواسطة:
            async with self.connect() as db:

        عدم استخدام:
            async with await self.connect()

        يمنع خطأ:
            RuntimeError: threads can only be started once
        """

        return aiosqlite.connect(
            self.get_database_path(),
            timeout=30,
        )

    async def configure_connection(self, db):
        """
        إعداد اتصال SQLite بعد تشغيل الـ Connection.
        """

        await db.execute(
            "PRAGMA foreign_keys = ON"
        )

        await db.execute(
            "PRAGMA busy_timeout = 30000"
        )

        await db.execute(
            "PRAGMA synchronous = NORMAL"
        )

    # =========================================================
    # Setup
    # =========================================================

    async def setup(self):
        async with self._write_lock:

            async with self.connect() as db:

                await self.configure_connection(db)

                # -------------------------------------------------
                # WAL
                # -------------------------------------------------

                try:
                    await db.execute(
                        "PRAGMA journal_mode = WAL"
                    )
                except Exception as error:
                    print(
                        f"⚠️ WAL warning: {error}"
                    )

                # =================================================
                # Guild Settings
                # =================================================

                await db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS guild_settings (
                        guild_id INTEGER PRIMARY KEY,
                        guild_name TEXT NOT NULL DEFAULT '',
                        guild_icon TEXT,

                        welcome_enabled INTEGER NOT NULL DEFAULT 0,
                        welcome_channel_id INTEGER,

                        welcome_title TEXT NOT NULL DEFAULT 'مرحبًا بك في {server}',
                        welcome_message TEXT NOT NULL DEFAULT
                            'أهلًا وسهلًا {user} في {server}! 🎉',
                        welcome_color TEXT NOT NULL DEFAULT '#5865F2',
                        welcome_thumbnail INTEGER NOT NULL DEFAULT 1,
                        welcome_footer TEXT NOT NULL DEFAULT 'Zivex • {server}',

                        level_enabled INTEGER NOT NULL DEFAULT 0,
                        level_channel_id INTEGER,

                        level_message TEXT NOT NULL DEFAULT
                            'مبروك {user}! 🎉\nوصلت إلى المستوى **{level}** في **{server}**.',
                        level_title TEXT NOT NULL DEFAULT 'Level Up! 🎉',
                        level_color TEXT NOT NULL DEFAULT '#5865F2',
                        level_thumbnail INTEGER NOT NULL DEFAULT 1,
                        level_footer TEXT NOT NULL DEFAULT 'Zivex • {server}',
                        level_xp_min INTEGER NOT NULL DEFAULT 15,
                        level_xp_max INTEGER NOT NULL DEFAULT 25,
                        level_cooldown INTEGER NOT NULL DEFAULT 60,
                        level_xp_per_level INTEGER NOT NULL DEFAULT 100,

                        tickets_enabled INTEGER NOT NULL DEFAULT 0,
                        tickets_category_id INTEGER,
                        tickets_log_channel_id INTEGER,

                        tickets_title TEXT NOT NULL DEFAULT '🎫 الدعم الفني',
                        tickets_message TEXT NOT NULL DEFAULT
                            'اضغط على الزر بالأسفل لفتح تذكرة.',
                        tickets_button_text TEXT NOT NULL DEFAULT 'فتح تذكرة',
                        tickets_button_emoji TEXT NOT NULL DEFAULT '🎫',
                        tickets_button_color TEXT NOT NULL DEFAULT 'blurple',
                        tickets_name TEXT NOT NULL DEFAULT 'ticket-{number}',
                        tickets_close_message TEXT NOT NULL DEFAULT
                            'تم إغلاق التذكرة بنجاح.',
                        tickets_color TEXT NOT NULL DEFAULT '#5865F2',

                        applications_enabled INTEGER NOT NULL DEFAULT 0,
                        application_channel_id INTEGER,
                        application_log_channel_id INTEGER,

                        application_title TEXT NOT NULL DEFAULT '📝 التقديمات',
                        application_message TEXT NOT NULL DEFAULT
                            'اضغط على الزر بالأسفل لبدء التقديم.',
                        application_button_text TEXT NOT NULL DEFAULT 'تقديم',
                        application_button_emoji TEXT NOT NULL DEFAULT '📝',
                        application_color TEXT NOT NULL DEFAULT '#5865F2',
                        application_success_message TEXT NOT NULL DEFAULT
                            'تم إرسال تقديمك بنجاح، يرجى انتظار رد الإدارة.',
                        application_log_message TEXT NOT NULL DEFAULT
                            '📥 تم استلام تقديم جديد من {user}.',

                        moderation_enabled INTEGER NOT NULL DEFAULT 0,
                        moderation_log_channel_id INTEGER,

                        moderation_warn_message TEXT NOT NULL DEFAULT
                            '⚠️ تم تحذير {user}.',
                        moderation_kick_message TEXT NOT NULL DEFAULT
                            '👢 تم طرد {user}.',
                        moderation_ban_message TEXT NOT NULL DEFAULT
                            '🔨 تم حظر {user}.',
                        moderation_mute_message TEXT NOT NULL DEFAULT
                            '🔇 تم إسكات {user}.',

                        logs_enabled INTEGER NOT NULL DEFAULT 0,
                        logs_channel_id INTEGER,

                        commands_channel_id INTEGER,

                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

                # =================================================
                # Migration
                # =================================================

                columns = [
                    ("guild_name", "TEXT NOT NULL DEFAULT ''"),
                    ("guild_icon", "TEXT"),

                    ("welcome_enabled", "INTEGER NOT NULL DEFAULT 0"),
                    ("welcome_channel_id", "INTEGER"),
                    (
                        "welcome_title",
                        "TEXT NOT NULL DEFAULT 'مرحبًا بك في {server}'"
                    ),
                    (
                        "welcome_message",
                        "TEXT NOT NULL DEFAULT 'أهلًا وسهلًا {user} في {server}! 🎉'"
                    ),
                    (
                        "welcome_color",
                        "TEXT NOT NULL DEFAULT '#5865F2'"
                    ),
                    (
                        "welcome_thumbnail",
                        "INTEGER NOT NULL DEFAULT 1"
                    ),
                    (
                        "welcome_footer",
                        "TEXT NOT NULL DEFAULT 'Zivex • {server}'"
                    ),

                    ("level_enabled", "INTEGER NOT NULL DEFAULT 0"),
                    ("level_channel_id", "INTEGER"),
                    (
                        "level_message",
                        "TEXT NOT NULL DEFAULT 'مبروك {user}! 🎉\\nوصلت إلى المستوى **{level}** في **{server}**.'"
                    ),
                    (
                        "level_title",
                        "TEXT NOT NULL DEFAULT 'Level Up! 🎉'"
                    ),
                    (
                        "level_color",
                        "TEXT NOT NULL DEFAULT '#5865F2'"
                    ),
                    (
                        "level_thumbnail",
                        "INTEGER NOT NULL DEFAULT 1"
                    ),
                    (
                        "level_footer",
                        "TEXT NOT NULL DEFAULT 'Zivex • {server}'"
                    ),
                    (
                        "level_xp_min",
                        "INTEGER NOT NULL DEFAULT 15"
                    ),
                    (
                        "level_xp_max",
                        "INTEGER NOT NULL DEFAULT 25"
                    ),
                    (
                        "level_cooldown",
                        "INTEGER NOT NULL DEFAULT 60"
                    ),
                    (
                        "level_xp_per_level",
                        "INTEGER NOT NULL DEFAULT 100"
                    ),

                    ("tickets_enabled", "INTEGER NOT NULL DEFAULT 0"),
                    ("tickets_category_id", "INTEGER"),
                    ("tickets_log_channel_id", "INTEGER"),
                    (
                        "tickets_title",
                        "TEXT NOT NULL DEFAULT '🎫 الدعم الفني'"
                    ),
                    (
                        "tickets_message",
                        "TEXT NOT NULL DEFAULT 'اضغط على الزر بالأسفل لفتح تذكرة.'"
                    ),
                    (
                        "tickets_button_text",
                        "TEXT NOT NULL DEFAULT 'فتح تذكرة'"
                    ),
                    (
                        "tickets_button_emoji",
                        "TEXT NOT NULL DEFAULT '🎫'"
                    ),
                    (
                        "tickets_button_color",
                        "TEXT NOT NULL DEFAULT 'blurple'"
                    ),
                    (
                        "tickets_name",
                        "TEXT NOT NULL DEFAULT 'ticket-{number}'"
                    ),
                    (
                        "tickets_close_message",
                        "TEXT NOT NULL DEFAULT 'تم إغلاق التذكرة بنجاح.'"
                    ),
                    (
                        "tickets_color",
                        "TEXT NOT NULL DEFAULT '#5865F2'"
                    ),

                    ("applications_enabled", "INTEGER NOT NULL DEFAULT 0"),
                    ("application_channel_id", "INTEGER"),
                    ("application_log_channel_id", "INTEGER"),
                    (
                        "application_title",
                        "TEXT NOT NULL DEFAULT '📝 التقديمات'"
                    ),
                    (
                        "application_message",
                        "TEXT NOT NULL DEFAULT 'اضغط على الزر بالأسفل لبدء التقديم.'"
                    ),
                    (
                        "application_button_text",
                        "TEXT NOT NULL DEFAULT 'تقديم'"
                    ),
                    (
                        "application_button_emoji",
                        "TEXT NOT NULL DEFAULT '📝'"
                    ),
                    (
                        "application_color",
                        "TEXT NOT NULL DEFAULT '#5865F2'"
                    ),
                    (
                        "application_success_message",
                        "TEXT NOT NULL DEFAULT 'تم إرسال تقديمك بنجاح، يرجى انتظار رد الإدارة.'"
                    ),
                    (
                        "application_log_message",
                        "TEXT NOT NULL DEFAULT '📥 تم استلام تقديم جديد من {user}.'"
                    ),

                    (
                        "moderation_enabled",
                        "INTEGER NOT NULL DEFAULT 0"
                    ),
                    (
                        "moderation_log_channel_id",
                        "INTEGER"
                    ),
                    (
                        "moderation_warn_message",
                        "TEXT NOT NULL DEFAULT '⚠️ تم تحذير {user}.'"
                    ),
                    (
                        "moderation_kick_message",
                        "TEXT NOT NULL DEFAULT '👢 تم طرد {user}.'"
                    ),
                    (
                        "moderation_ban_message",
                        "TEXT NOT NULL DEFAULT '🔨 تم حظر {user}.'"
                    ),
                    (
                        "moderation_mute_message",
                        "TEXT NOT NULL DEFAULT '🔇 تم إسكات {user}.'"
                    ),

                    (
                        "logs_enabled",
                        "INTEGER NOT NULL DEFAULT 0"
                    ),
                    (
                        "logs_channel_id",
                        "INTEGER"
                    ),
                    (
                        "commands_channel_id",
                        "INTEGER"
                    ),
                    (
                        "updated_at",
                        "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                    ),
                ]

                cursor = await db.execute(
                    "PRAGMA table_info(guild_settings)"
                )

                rows = await cursor.fetchall()

                existing_columns = {
                    row[1]
                    for row in rows
                }

                for column_name, column_type in columns:

                    if column_name in existing_columns:
                        continue

                    try:
                        await db.execute(
                            f"""
                            ALTER TABLE guild_settings
                            ADD COLUMN {column_name} {column_type}
                            """
                        )

                    except Exception as error:
                        print(
                            "⚠️ Database migration warning "
                            f"({column_name}): {error}"
                        )

                # =================================================
                # Index
                # =================================================

                await db.execute(
                    """
                    CREATE INDEX IF NOT EXISTS
                    idx_guild_settings_updated
                    ON guild_settings(updated_at)
                    """
                )

                await db.commit()

        print("✅ Database setup completed.")

    # =========================================================
    # Ensure Guild
    # =========================================================

    async def ensure_guild(
        self,
        guild_id: int,
        guild_name: str,
        guild_icon: Optional[str] = None,
    ):
        try:
            guild_id = int(guild_id)

        except (TypeError, ValueError):
            return False

        if guild_id <= 0:
            return False

        guild_name = str(
            guild_name or "Unknown Server"
        )[:200]

        if guild_icon:
            guild_icon = str(guild_icon)[:500]

        async with self._write_lock:

            async with self.connect() as db:

                await self.configure_connection(db)

                await db.execute(
                    """
                    INSERT INTO guild_settings (
                        guild_id,
                        guild_name,
                        guild_icon
                    )
                    VALUES (?, ?, ?)

                    ON CONFLICT(guild_id)
                    DO UPDATE SET
                        guild_name = excluded.guild_name,
                        guild_icon = excluded.guild_icon,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        guild_id,
                        guild_name,
                        guild_icon,
                    ),
                )

                await db.commit()

        return True

    # =========================================================
    # Get Guild
    # =========================================================

    async def get_guild(
        self,
        guild_id: int,
    ):
        try:
            guild_id = int(guild_id)

        except (TypeError, ValueError):
            return None

        if guild_id <= 0:
            return None

        async with self.connect() as db:

            await self.configure_connection(db)

            db.row_factory = aiosqlite.Row

            cursor = await db.execute(
                """
                SELECT *
                FROM guild_settings
                WHERE guild_id = ?
                """,
                (guild_id,),
            )

            row = await cursor.fetchone()

            if not row:
                return None

            return dict(row)

    # =========================================================
    # Update Setting
    # =========================================================

    async def update_setting(
        self,
        guild_id: int,
        setting: str,
        value: Any,
    ):
        try:
            guild_id = int(guild_id)

        except (TypeError, ValueError):
            return False

        if guild_id <= 0:
            return False

        allowed_settings = {
            "guild_name",
            "guild_icon",
            "commands_channel_id",

            "welcome_enabled",
            "welcome_channel_id",
            "welcome_title",
            "welcome_message",
            "welcome_color",
            "welcome_thumbnail",
            "welcome_footer",

            "level_enabled",
            "level_channel_id",
            "level_message",
            "level_title",
            "level_color",
            "level_thumbnail",
            "level_footer",
            "level_xp_min",
            "level_xp_max",
            "level_cooldown",
            "level_xp_per_level",

            "tickets_enabled",
            "tickets_category_id",
            "tickets_log_channel_id",
            "tickets_title",
            "tickets_message",
            "tickets_button_text",
            "tickets_button_emoji",
            "tickets_button_color",
            "tickets_name",
            "tickets_close_message",
            "tickets_color",

            "applications_enabled",
            "application_channel_id",
            "application_log_channel_id",
            "application_title",
            "application_message",
            "application_button_text",
            "application_button_emoji",
            "application_color",
            "application_success_message",
            "application_log_message",

            "moderation_enabled",
            "moderation_log_channel_id",
            "moderation_warn_message",
            "moderation_kick_message",
            "moderation_ban_message",
            "moderation_mute_message",

            "logs_enabled",
            "logs_channel_id",
        }

        if setting not in allowed_settings:
            return False

        async with self._write_lock:

            async with self.connect() as db:

                await self.configure_connection(db)

                await db.execute(
                    f"""
                    UPDATE guild_settings
                    SET {setting} = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE guild_id = ?
                    """,
                    (
                        value,
                        guild_id,
                    ),
                )

                await db.commit()

        return True

    # =========================================================
    # Update Multiple Settings
    # =========================================================

    async def update_settings(
        self,
        guild_id: int,
        settings: dict,
    ):
        if not isinstance(settings, dict):
            return False

        allowed_settings = {
            "guild_name",
            "guild_icon",
            "commands_channel_id",

            "welcome_enabled",
            "welcome_channel_id",
            "welcome_title",
            "welcome_message",
            "welcome_color",
            "welcome_thumbnail",
            "welcome_footer",

            "level_enabled",
            "level_channel_id",
            "level_message",
            "level_title",
            "level_color",
            "level_thumbnail",
            "level_footer",
            "level_xp_min",
            "level_xp_max",
            "level_cooldown",
            "level_xp_per_level",

            "tickets_enabled",
            "tickets_category_id",
            "tickets_log_channel_id",
            "tickets_title",
            "tickets_message",
            "tickets_button_text",
            "tickets_button_emoji",
            "tickets_button_color",
            "tickets_name",
            "tickets_close_message",
            "tickets_color",

            "applications_enabled",
            "application_channel_id",
            "application_log_channel_id",
            "application_title",
            "application_message",
            "application_button_text",
            "application_button_emoji",
            "application_color",
            "application_success_message",
            "application_log_message",

            "moderation_enabled",
            "moderation_log_channel_id",
            "moderation_warn_message",
            "moderation_kick_message",
            "moderation_ban_message",
            "moderation_mute_message",

            "logs_enabled",
            "logs_channel_id",
        }

        for setting in settings:
            if setting not in allowed_settings:
                return False

        try:
            guild_id = int(guild_id)

        except (TypeError, ValueError):
            return False

        if guild_id <= 0:
            return False

        async with self._write_lock:

            async with self.connect() as db:

                await self.configure_connection(db)

                for setting, value in settings.items():

                    await db.execute(
                        f"""
                        UPDATE guild_settings
                        SET {setting} = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE guild_id = ?
                        """,
                        (
                            value,
                            guild_id,
                        ),
                    )

                await db.commit()

        return True

    # =========================================================
    # Set Channel
    # =========================================================

    async def set_channel(
        self,
        guild_id: int,
        setting: str,
        channel_id: Optional[int],
    ):
        channel_settings = {
            "welcome": "welcome_channel_id",

            "level": "level_channel_id",
            "levels": "level_channel_id",

            "ticket": "tickets_category_id",
            "tickets": "tickets_category_id",
            "ticketcategory": "tickets_category_id",

            "ticketlog": "tickets_log_channel_id",

            "application": "application_channel_id",
            "applications": "application_channel_id",

            "applicationlog": "application_log_channel_id",

            "moderationlog": "moderation_log_channel_id",

            "logs": "logs_channel_id",

            "commands": "commands_channel_id",
        }

        column = channel_settings.get(
            str(setting).lower()
        )

        if not column:
            return False

        if channel_id is not None:

            try:
                channel_id = int(channel_id)

            except (TypeError, ValueError):
                return False

            if channel_id <= 0:
                return False

        return await self.update_setting(
            guild_id,
            column,
            channel_id,
        )

    # =========================================================
    # Set Enabled
    # =========================================================

    async def set_enabled(
        self,
        guild_id: int,
        system: str,
        enabled: bool,
    ):
        enabled_settings = {
            "welcome": "welcome_enabled",

            "level": "level_enabled",
            "levels": "level_enabled",

            "ticket": "tickets_enabled",
            "tickets": "tickets_enabled",

            "application": "applications_enabled",
            "applications": "applications_enabled",

            "moderation": "moderation_enabled",

            "logs": "logs_enabled",
        }

        column = enabled_settings.get(
            str(system).lower()
        )

        if not column:
            return False

        return await self.update_setting(
            guild_id,
            column,
            1 if enabled else 0,
        )

    # =========================================================
    # Save Message Configuration
    # =========================================================

    async def save_message_config(
        self,
        guild_id: int,
        system: str,
        title: Optional[str] = None,
        message: Optional[str] = None,
        color: Optional[str] = None,
        footer: Optional[str] = None,
    ):
        prefixes = {
            "welcome": "welcome",

            "level": "level",
            "levels": "level",

            "ticket": "tickets",
            "tickets": "tickets",
        }

        prefix = prefixes.get(
            str(system).lower()
        )

        if not prefix:
            return False

        updates = {}

        if title is not None:
            updates[
                f"{prefix}_title"
            ] = str(title)[:256]

        if message is not None:
            updates[
                f"{prefix}_message"
            ] = str(message)[:4000]

        if color is not None:
            updates[
                f"{prefix}_color"
            ] = str(color)[:20]

        if footer is not None:
            updates[
                f"{prefix}_footer"
            ] = str(footer)[:2048]

        if not updates:
            return False

        return await self.update_settings(
            guild_id,
            updates,
        )

    # =========================================================
    # Get Setting
    # =========================================================

    async def get_setting(
        self,
        guild_id: int,
        setting: str,
        default=None,
    ):
        settings = await self.get_guild(
            guild_id
        )

        if not settings:
            return default

        return settings.get(
            setting,
            default,
        )


# =============================================================
# Global Database Instance
# =============================================================

db = Database()
