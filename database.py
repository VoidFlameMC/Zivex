import aiosqlite
from typing import Optional, Any


DATABASE_NAME = "zivex.db"


class Database:
    def __init__(self, database_name: str = DATABASE_NAME):
        self.database_name = database_name

    async def connect(self):
        return await aiosqlite.connect(self.database_name)

    async def setup(self):
        async with await self.connect() as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id INTEGER PRIMARY KEY,
                    guild_name TEXT NOT NULL DEFAULT '',
                    guild_icon TEXT DEFAULT '',

                    welcome_enabled INTEGER NOT NULL DEFAULT 0,
                    welcome_channel_id INTEGER,

                    level_enabled INTEGER NOT NULL DEFAULT 0,
                    level_channel_id INTEGER,

                    applications_enabled INTEGER NOT NULL DEFAULT 0,
                    applications_channel_id INTEGER,

                    tickets_enabled INTEGER NOT NULL DEFAULT 0,
                    tickets_channel_id INTEGER,

                    logs_enabled INTEGER NOT NULL DEFAULT 0,
                    logs_channel_id INTEGER,

                    commands_channel_id INTEGER,

                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.commit()

    async def ensure_guild(
        self,
        guild_id: int,
        guild_name: str,
        guild_icon: Optional[str] = None
    ):
        async with await self.connect() as db:
            await db.execute("""
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
            """, (
                guild_id,
                guild_name,
                guild_icon or ""
            ))

            await db.commit()

    async def get_guild(self, guild_id: int) -> Optional[dict]:
        async with await self.connect() as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute("""
                SELECT *
                FROM guild_settings
                WHERE guild_id = ?
            """, (guild_id,))

            row = await cursor.fetchone()

            if row is None:
                return None

            return dict(row)

    async def update_setting(
        self,
        guild_id: int,
        setting: str,
        value: Any
    ):
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

            "commands_channel_id"
        }

        if setting not in allowed_settings:
            raise ValueError(
                f"Invalid database setting: {setting}"
            )

        async with await self.connect() as db:
            await db.execute(
                f"""
                UPDATE guild_settings
                SET {setting} = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE guild_id = ?
                """,
                (value, guild_id)
            )

            await db.commit()

    async def set_channel(
        self,
        guild_id: int,
        setting: str,
        channel_id: Optional[int]
    ):
        channel_settings = {
            "welcome": "welcome_channel_id",
            "level": "level_channel_id",
            "applications": "applications_channel_id",
            "tickets": "tickets_channel_id",
            "logs": "logs_channel_id",
            "commands": "commands_channel_id"
        }

        if setting not in channel_settings:
            raise ValueError(
                f"Invalid channel setting: {setting}"
            )

        await self.update_setting(
            guild_id,
            channel_settings[setting],
            channel_id
        )

    async def set_enabled(
        self,
        guild_id: int,
        system: str,
        enabled: bool
    ):
        enabled_settings = {
            "welcome": "welcome_enabled",
            "level": "level_enabled",
            "applications": "applications_enabled",
            "tickets": "tickets_enabled",
            "logs": "logs_enabled"
        }

        if system not in enabled_settings:
            raise ValueError(
                f"Invalid system: {system}"
            )

        await self.update_setting(
            guild_id,
            enabled_settings[system],
            1 if enabled else 0
        )


db = Database()
