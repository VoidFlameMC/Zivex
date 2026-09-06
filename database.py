import os
from typing import Any, Optional

import aiosqlite

from config import DATABASE_URL


# =========================================================
# Zivex Database
# =========================================================

DEFAULT_DATABASE = "zivex.db"


class Database:

    def __init__(
        self,
        database_name: str = DEFAULT_DATABASE,
    ):
        self.database_name = database_name

    # =====================================================
    # Database Path
    # =====================================================

    def get_database_path(self) -> str:
        """
        تحويل DATABASE_URL إلى مسار SQLite.

        يدعم:
        sqlite:///zivex.db
        sqlite:///
        zivex.db
        """

        database_url = (
            DATABASE_URL or ""
        ).strip()

        if not database_url:
            return DEFAULT_DATABASE

        # -------------------------------------------------
        # sqlite:///path
        # -------------------------------------------------

        if database_url.startswith(
            "sqlite:///"
        ):
            path = database_url[
                len("sqlite:///"):
            ]

            return (
                path
                if path
                else DEFAULT_DATABASE
            )

        # -------------------------------------------------
        # sqlite://path
        # -------------------------------------------------

        if database_url.startswith(
            "sqlite://"
        ):
            path = database_url[
                len("sqlite://"):
            ]

            return (
                path
                if path
                else DEFAULT_DATABASE
            )

        # -------------------------------------------------
        # Direct SQLite filename
        # -------------------------------------------------

        return database_url

    # =====================================================
    # Connect
    # =====================================================

    async def connect(self):
        """
        إنشاء اتصال SQLite.
        """

        path = self.get_database_path()

        db = await aiosqlite.connect(
            path,
            timeout=30,
        )

        # Foreign keys
        await db.execute(
            "PRAGMA foreign_keys = ON"
        )

        # WAL يحسن التعامل مع القراءة والكتابة
        await db.execute(
            "PRAGMA journal_mode = WAL"
        )

        return db

    # =====================================================
    # Setup
    # =====================================================

    async def setup(self):

        async with await self.connect() as db:

            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id INTEGER PRIMARY KEY,

                    guild_name TEXT NOT NULL DEFAULT '',

                    guild_icon TEXT DEFAULT '',

                    welcome_enabled
                        INTEGER NOT NULL DEFAULT 0,

                    welcome_channel_id
                        INTEGER,

                    level_enabled
                        INTEGER NOT NULL DEFAULT 0,

                    level_channel_id
                        INTEGER,

                    applications_enabled
                        INTEGER NOT NULL DEFAULT 0,

                    applications_channel_id
                        INTEGER,

                    tickets_enabled
                        INTEGER NOT NULL DEFAULT 0,

                    tickets_channel_id
                        INTEGER,

                    logs_enabled
                        INTEGER NOT NULL DEFAULT 0,

                    logs_channel_id
                        INTEGER,

                    commands_channel_id
                        INTEGER,

                    updated_at
                        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
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

    # =====================================================
    # Ensure Guild
    # =====================================================

    async def ensure_guild(
        self,
        guild_id: int,
        guild_name: str,
        guild_icon: Optional[str] = None,
    ):

        if guild_id <= 0:
            raise ValueError(
                "guild_id must be positive"
            )

        guild_name = str(
            guild_name or ""
        )[:200]

        guild_icon = str(
            guild_icon or ""
        )[:500]

        async with await self.connect() as db:

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
                    guild_name =
                        excluded.guild_name,

                    guild_icon =
                        excluded.guild_icon,

                    updated_at =
                        CURRENT_TIMESTAMP
                """,
                (
                    guild_id,
                    guild_name,
                    guild_icon,
                ),
            )

            await db.commit()

    # =====================================================
    # Get Guild
    # =====================================================

    async def get_guild(
        self,
        guild_id: int,
    ) -> Optional[dict]:

        if guild_id <= 0:
            return None

        async with await self.connect() as db:

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

            if row is None:
                return None

            return dict(row)

    # =====================================================
    # Update Setting
    # =====================================================

    async def update_setting(
        self,
        guild_id: int,
        setting: str,
        value: Any,
    ):

        if guild_id <= 0:
            raise ValueError(
                "guild_id must be positive"
            )

        allowed_settings = {
            "guild_name",
            "guild_icon",

            "welcome_enabled",
            "welcome_channel_id",

            "level_enabled",
            "level_channel_id",

            "applications_enabled",
            "applications_channel_id",

            "tickets_enabled",
            "tickets_channel_id",

            "logs_enabled",
            "logs_channel_id",

            "commands_channel_id",
        }

        if setting not in allowed_settings:
            raise ValueError(
                f"Invalid database setting: {setting}"
            )

        async with await self.connect() as db:

            # اسم العمود لا يأتي من المستخدم،
            # لأنه مقيد بالقائمة أعلاه.
            query = f"""
                UPDATE guild_settings
                SET {setting} = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE guild_id = ?
            """

            await db.execute(
                query,
                (
                    value,
                    guild_id,
                ),
            )

            await db.commit()

    # =====================================================
    # Set Channel
    # =====================================================

    async def set_channel(
        self,
        guild_id: int,
        setting: str,
        channel_id: Optional[int],
    ):

        channel_settings = {
            "welcome":
                "welcome_channel_id",

            "level":
                "level_channel_id",

            "applications":
                "applications_channel_id",

            "tickets":
                "tickets_channel_id",

            "logs":
                "logs_channel_id",

            "commands":
                "commands_channel_id",
        }

        if setting not in channel_settings:
            raise ValueError(
                f"Invalid channel setting: {setting}"
            )

        if channel_id is not None:

            if not isinstance(
                channel_id,
                int,
            ):
                raise ValueError(
                    "channel_id must be an integer"
                )

            if channel_id <= 0:
                raise ValueError(
                    "channel_id must be positive"
                )

        await self.update_setting(
            guild_id,
            channel_settings[setting],
            channel_id,
        )

    # =====================================================
    # Set Enabled
    # =====================================================

    async def set_enabled(
        self,
        guild_id: int,
        system: str,
        enabled: bool,
    ):

        enabled_settings = {
            "welcome":
                "welcome_enabled",

            "level":
                "level_enabled",

            "applications":
                "applications_enabled",

            "tickets":
                "tickets_enabled",

            "logs":
                "logs_enabled",
        }

        if system not in enabled_settings:
            raise ValueError(
                f"Invalid system: {system}"
            )

        await self.update_setting(
            guild_id,
            enabled_settings[system],
            1 if enabled else 0,
        )


# =========================================================
# Global Database Instance
# =========================================================

db = Database()
