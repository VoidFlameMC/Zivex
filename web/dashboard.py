# =========================================================
# Zivex — Professional Dashboard
# web/dashboard.py
# =========================================================
import asyncio
from functools import wraps
import discord
from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from database import db
from web.auth import discord_get
# =========================================================
# Blueprint
# =========================================================
dashboard_bp = Blueprint(
    "dashboard",
    __name__,
    url_prefix="/dashboard",
)
# =========================================================
# Discord Permissions
# =========================================================
ADMINISTRATOR = 1 << 3
MANAGE_GUILD = 1 << 5
# =========================================================
# Async Helper
# =========================================================
def run_async(coroutine, timeout=30):
    """
    تشغيل Coroutine داخل Event Loop الخاص بالبوت.
    Flask يعمل في Thread مختلف عن Discord.
    """
    bot = get_bot()
    if bot is None:
        try:
            coroutine.close()
        except Exception:
            pass
        return None
    try:
        loop = bot.loop
    except Exception as error:
        print(f"❌ Dashboard loop error: {error}")
        try:
            coroutine.close()
        except Exception:
            pass
        return None
    if loop is None or not loop.is_running():
        print("❌ Dashboard async error: Bot Event Loop is not running.")
        try:
            coroutine.close()
        except Exception:
            pass
        return None
    try:
        future = asyncio.run_coroutine_threadsafe(
            coroutine,
            loop,
        )
        return future.result(timeout=timeout)
    except asyncio.TimeoutError:
        print("❌ Dashboard async error: Database operation timed out.")
        try:
            future.cancel()
        except Exception:
            pass
        return None
    except Exception as error:
        print(f"❌ Dashboard async error: {error}")
        return None
# =========================================================
# General Helpers
# =========================================================
def safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
def valid_guild_id(guild_id):
    if guild_id is None:
        return False
    value = str(guild_id).strip()
    if not value:
        return False
    if len(value) > 30:
        return False
    if not value.isdigit():
        return False
    try:
        return int(value) > 0
    except ValueError:
        return False
def clean_text(value, maximum):
    if value is None:
        return None
    return str(value).strip()[:maximum]
def clean_channel_id(value):
    if value in (None, "", "null", "None"):
        return None
    if not valid_guild_id(value):
        return None
    return int(value)
# =========================================================
# Authentication
# =========================================================
def get_logged_user():
    user = session.get("discord_user")
    if not isinstance(user, dict):
        return None
    if not user.get("id"):
        return None
    return user
def get_access_token():
    token = session.get("discord_access_token")
    if not token:
        return None
    if not isinstance(token, str):
        return None
    return token
def require_login():
    return bool(
        get_logged_user()
        and get_access_token()
    )
# =========================================================
# Bot
# =========================================================
def get_bot():
    return current_app.config.get("ZIVEX_BOT")
def get_bot_guild(guild_id):
    if not valid_guild_id(guild_id):
        return None
    bot = get_bot()
    if bot is None:
        return None
    try:
        return bot.get_guild(int(guild_id))
    except Exception as error:
        print(f"⚠️ Guild lookup error: {error}")
        return None
# =========================================================
# Discord Permissions
# =========================================================
def can_manage_guild(guild_data):
    if not isinstance(guild_data, dict):
        return False
    try:
        permissions = int(
            guild_data.get("permissions", 0)
        )
    except (TypeError, ValueError):
        return False
    return bool(
        permissions
        & (ADMINISTRATOR | MANAGE_GUILD)
    )
# =========================================================
# Discord API
# =========================================================
def get_user_guilds():
    token = get_access_token()
    if not token:
        return None
    try:
        response = discord_get(
            "/users/@me/guilds",
            token,
        )
    except Exception as error:
        print(f"❌ Discord guild request error: {error}")
        return None
    if response is None:
        return None
    if response.status_code == 401:
        session.clear()
        return None
    if response.status_code != 200:
        print(
            "⚠️ Discord guild request failed:",
            response.status_code,
        )
        return None
    try:
        guilds = response.json()
    except ValueError:
        return None
    if not isinstance(guilds, list):
        return None
    return guilds
# =========================================================
# Authorized Guild
# =========================================================
def get_authorized_guild(guild_id):
    if not require_login():
        return None
    if not valid_guild_id(guild_id):
        return None
    guild_id = str(guild_id)
    guilds = get_user_guilds()
    if guilds is None:
        return None
    for guild in guilds:
        if not isinstance(guild, dict):
            continue
        if str(guild.get("id", "")) != guild_id:
            continue
        if not can_manage_guild(guild):
            return None
        return guild
    return None
# =========================================================
# Database
# =========================================================
def get_guild_settings(guild_id, bot_guild=None):
    if not valid_guild_id(guild_id):
        return {}
    guild_id = int(guild_id)
    settings = run_async(
        db.get_guild(guild_id)
    )
    if settings:
        return settings
    if bot_guild is not None:
        icon_url = None
        try:
            if bot_guild.icon:
                icon_url = str(bot_guild.icon.url)
        except Exception:
            icon_url = None
        run_async(
            db.ensure_guild(
                guild_id,
                bot_guild.name,
                icon_url,
            )
        )
        settings = run_async(
            db.get_guild(guild_id)
        )
        if settings:
            return settings
    return {}
# =========================================================
# System Configuration
# =========================================================
SYSTEM_SETTINGS = {
    "welcome": "welcome_enabled",
    "levels": "level_enabled",
    "tickets": "tickets_enabled",
    "applications": "applications_enabled",
    "moderation": "moderation_enabled",
    "logs": "logs_enabled",
}
def get_system_status(settings):
    if not isinstance(settings, dict):
        settings = {}
    return {
        system: bool(
            safe_int(
                settings.get(setting, 0)
            )
        )
        for system, setting in SYSTEM_SETTINGS.items()
    }
# =========================================================
# Advanced Settings
# =========================================================
SYSTEM_SETTING_KEYS = {
    "levels": {
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
    },
    "welcome": {
        "welcome_enabled",
        "welcome_channel_id",
        "welcome_title",
        "welcome_message",
        "welcome_color",
        "welcome_thumbnail",
        "welcome_footer",
    },
    "tickets": {
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
    },
    "applications": {
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
    },
    "moderation": {
        "moderation_enabled",
        "moderation_log_channel_id",
        "moderation_warn_message",
        "moderation_kick_message",
        "moderation_ban_message",
        "moderation_mute_message",
    },
    "logs": {
        "logs_enabled",
        "logs_channel_id",
    },
}
# =========================================================
# Guild Statistics
# =========================================================
def get_guild_statistics(bot_guild):
    empty = {
        "members": 0,
        "channels": 0,
        "text_channels": 0,
        "voice_channels": 0,
        "categories": 0,
        "roles": 0,
        "emojis": 0,
        "stickers": 0,
    }
    if bot_guild is None:
        return empty
    try:
        channels = list(bot_guild.channels)
        text_channels = sum(
            isinstance(
                channel,
                discord.TextChannel,
            )
            for channel in channels
        )
        voice_channels = sum(
            isinstance(
                channel,
                discord.VoiceChannel,
            )
            for channel in channels
        )
        categories = sum(
            isinstance(
                channel,
                discord.CategoryChannel,
            )
            for channel in channels
        )
        return {
            "members": int(
                bot_guild.member_count or 0
            ),
            "channels": len(channels),
            "text_channels": text_channels,
            "voice_channels": voice_channels,
            "categories": categories,
            "roles": len(bot_guild.roles),
            "emojis": len(bot_guild.emojis),
            "stickers": len(bot_guild.stickers),
        }
    except Exception as error:
        print(f"⚠️ Guild statistics error: {error}")
        return empty
# =========================================================
# Guild Data
# =========================================================
def build_guild_data(guild, bot_guild=None):
    guild_id = str(
        guild.get("id", "")
    )
    settings = get_guild_settings(
        guild_id,
        bot_guild,
    )
    return {
        "id": guild_id,
        "name": guild.get(
            "name",
            "Unknown Server",
        ),
        "icon": guild.get("icon"),
        "owner": bool(
            guild.get("owner", False)
        ),
        "bot_installed": bot_guild is not None,
        "settings": settings,
        "systems": get_system_status(settings),
        "statistics": get_guild_statistics(
            bot_guild
        ),
    }
# =========================================================
# Decorators
# =========================================================
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not require_login():
            return redirect(
                url_for("login")
            )
        return view(*args, **kwargs)
    return wrapped
def guild_required(view):
    @wraps(view)
    def wrapped(
        guild_id,
        *args,
        **kwargs,
    ):
        if not require_login():
            return jsonify({
                "success": False,
                "error": "Unauthorized",
                "message": "يجب تسجيل الدخول أولًا.",
            }), 401
        guild = get_authorized_guild(guild_id)
        if guild is None:
            return jsonify({
                "success": False,
                "error": "Forbidden",
                "message": "لا تملك صلاحية إدارة هذا السيرفر.",
            }), 403
        return view(
            guild_id,
            guild,
            *args,
            **kwargs,
        )
    return wrapped
# =========================================================
# Dashboard Home
# =========================================================
@dashboard_bp.route("/")
@login_required
def dashboard_home():
    guilds = get_user_guilds()
    if guilds is None:
        session.clear()
        return redirect(
            url_for("login")
        )
    authorized_guilds = []
    for guild in guilds:
        if not isinstance(guild, dict):
            continue
        if not can_manage_guild(guild):
            continue
        guild_id = guild.get("id")
        if not valid_guild_id(guild_id):
            continue
        bot_guild = get_bot_guild(guild_id)
        authorized_guilds.append(
            build_guild_data(
                guild,
                bot_guild,
            )
        )
    return render_template(
        "dashboard.html",
        user=get_logged_user(),
        guilds=authorized_guilds,
        selected_guild=None,
        dashboard_stats={
            "servers": len(authorized_guilds),
            "installed": sum(
                1
                for guild in authorized_guilds
                if guild.get(
                    "bot_installed",
                    False,
                )
            ),
        },
    )
# =========================================================
# Guild Dashboard
# =========================================================
@dashboard_bp.route("/<guild_id>")
@login_required
def guild_dashboard(guild_id):
    guild = get_authorized_guild(guild_id)
    if guild is None:
        return render_template(
            "error.html",
            error_code=403,
            error_title="غير مصرح",
            error_message=(
                "لا تملك صلاحية إدارة هذا السيرفر "
                "أو أن السيرفر غير موجود في حسابك."
            ),
        ), 403
    bot_guild = get_bot_guild(guild_id)
    selected_guild = build_guild_data(
        guild,
        bot_guild,
    )
    return render_template(
        "dashboard.html",
        user=get_logged_user(),
        guilds=[selected_guild],
        selected_guild=selected_guild,
        dashboard_stats={
            "servers": 1,
            "installed": int(
                selected_guild["bot_installed"]
            ),
        },
    )
# =========================================================
# Authorization API
# =========================================================
@dashboard_bp.route(
    "/api/<guild_id>/authorization",
    methods=["GET"],
)
@guild_required
def guild_authorization(
    guild_id,
    guild,
):
    bot_guild = get_bot_guild(guild_id)
    return jsonify({
        "success": True,
        "authorized": True,
        "guild_id": str(
            guild.get("id")
        ),
        "bot_installed": bot_guild is not None,
    })
# =========================================================
# Overview API
# =========================================================
@dashboard_bp.route(
    "/api/<guild_id>/overview",
    methods=["GET"],
)
@guild_required
def guild_overview(
    guild_id,
    guild,
):
    bot_guild = get_bot_guild(guild_id)
    settings = get_guild_settings(
        guild_id,
        bot_guild,
    )
    return jsonify({
        "success": True,
        "guild": {
            "id": str(
                guild.get("id")
            ),
            "name": guild.get(
                "name",
                "Unknown Server",
            ),
            "icon": guild.get("icon"),
            "owner": bool(
                guild.get(
                    "owner",
                    False,
                )
            ),
            "bot_installed": bot_guild is not None,
        },
        "statistics": get_guild_statistics(
            bot_guild
        ),
        "systems": get_system_status(
            settings
        ),
        "settings": settings,
    })
# =========================================================
# Settings GET
# =========================================================
@dashboard_bp.route(
    "/api/<guild_id>/settings",
    methods=["GET"],
)
@guild_required
def get_settings_api(
    guild_id,
    guild,
):
    bot_guild = get_bot_guild(guild_id)
    settings = get_guild_settings(
        guild_id,
        bot_guild,
    )
    return jsonify({
        "success": True,
        "guild_id": str(
            guild.get("id")
        ),
        "settings": settings,
        "systems": get_system_status(
            settings
        ),
    })
# =========================================================
# Settings POST
# =========================================================
@dashboard_bp.route(
    "/api/<guild_id>/settings",
    methods=["POST"],
)
@guild_required
def update_settings_api(
    guild_id,
    guild,
):
    bot_guild = get_bot_guild(guild_id)
    if bot_guild is None:
        return jsonify({
            "success": False,
            "error": "BotNotInstalled",
            "message": "البوت غير موجود في هذا السيرفر.",
        }), 400
    if not request.is_json:
        return jsonify({
            "success": False,
            "error": "InvalidJSON",
            "message": "يجب إرسال البيانات بصيغة JSON.",
        }), 400
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "error": "InvalidData",
        }), 400
    if "key" in data:
        key = data.get("key")
        if not isinstance(key, str):
            return jsonify({
                "success": False,
                "error": "InvalidKey",
            }), 400
        key = key.strip()
        if not key:
            return jsonify({
                "success": False,
                "error": "InvalidKey",
            }), 400
        if "value" not in data:
            return jsonify({
                "success": False,
                "error": "MissingValue",
            }), 400
        result = run_async(
            db.update_setting(
                int(guild_id),
                key,
                data.get("value"),
            )
        )
        if result is not True:
            return jsonify({
                "success": False,
                "error": "DatabaseError",
                "message": "تعذر حفظ الإعداد.",
            }), 500
        return jsonify({
            "success": True,
            "message": "تم حفظ الإعداد بنجاح.",
            "key": key,
            "value": data.get("value"),
        })
    settings = data.get("settings")
    if not isinstance(settings, dict):
        return jsonify({
            "success": False,
            "error": "MissingSettings",
        }), 400
    if not settings:
        return jsonify({
            "success": False,
            "error": "EmptySettings",
        }), 400
    result = run_async(
        db.update_settings(
            int(guild_id),
            settings,
        )
    )
    if result is not True:
        return jsonify({
            "success": False,
            "error": "DatabaseError",
            "message": "تعذر حفظ الإعدادات.",
        }), 500
    return jsonify({
        "success": True,
        "message": "تم حفظ الإعدادات بنجاح.",
        "updated": list(settings.keys()),
    })
# =========================================================
# Advanced System Settings GET
# =========================================================
@dashboard_bp.route(
    "/api/<guild_id>/system/<system_name>/settings",
    methods=["GET"],
)
@guild_required
def get_system_settings(
    guild_id,
    guild,
    system_name,
):
    system_name = str(
        system_name
    ).strip().lower()
    allowed = SYSTEM_SETTING_KEYS.get(
        system_name
    )
    if allowed is None:
        return jsonify({
            "success": False,
            "error": "UnknownSystem",
        }), 404
    bot_guild = get_bot_guild(guild_id)
    settings = get_guild_settings(
        guild_id,
        bot_guild,
    )
    return jsonify({
        "success": True,
        "system": system_name,
        "settings": {
            key: settings.get(key)
            for key in allowed
        },
    })
# =========================================================
# Advanced System Settings POST
# =========================================================
@dashboard_bp.route(
    "/api/<guild_id>/system/<system_name>/settings",
    methods=["POST"],
)
@guild_required
def save_system_settings(
    guild_id,
    guild,
    system_name,
):
    system_name = str(
        system_name
    ).strip().lower()
    allowed = SYSTEM_SETTING_KEYS.get(
        system_name
    )
    if allowed is None:
        return jsonify({
            "success": False,
            "error": "UnknownSystem",
        }), 404
    if not request.is_json:
        return jsonify({
            "success": False,
            "error": "InvalidJSON",
        }), 400
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "error": "InvalidData",
        }), 400
    updates = {}
    for key, value in data.items():
        if key not in allowed:
            continue
        # -------------------------------------------------
        # Channel IDs
        # -------------------------------------------------
        if key.endswith("_channel_id") or key.endswith(
            "_category_id"
        ):
            value = clean_channel_id(value)
        # -------------------------------------------------
        # Integer Settings
        # -------------------------------------------------
        elif key in {
            "level_xp_min",
            "level_xp_max",
            "level_cooldown",
            "level_xp_per_level",
        }:
            try:
                value = int(value)
            except (TypeError, ValueError):
                return jsonify({
                    "success": False,
                    "error": "InvalidNumber",
                    "message": f"القيمة {key} يجب أن تكون رقمًا.",
                }), 400
            if value < 0:
                return jsonify({
                    "success": False,
                    "error": "InvalidNumber",
                    "message": f"القيمة {key} لا يمكن أن تكون سالبة.",
                }), 400
        # -------------------------------------------------
        # Boolean Settings
        # -------------------------------------------------
        elif key in {
            "welcome_enabled",
            "welcome_thumbnail",
            "level_enabled",
            "level_thumbnail",
            "tickets_enabled",
            "applications_enabled",
            "moderation_enabled",
            "logs_enabled",
        }:
            if isinstance(value, bool):
                value = 1 if value else 0
            else:
                value = (
                    1
                    if str(value).lower()
                    in {
                        "1",
                        "true",
                        "on",
                        "yes",
                    }
                    else 0
                )
        # -------------------------------------------------
        # Text
        # -------------------------------------------------
        else:
            limits = {
                "welcome_title": 256,
                "welcome_message": 4000,
                "welcome_color": 20,
                "welcome_footer": 2048,
                "level_title": 256,
                "level_message": 4000,
                "level_color": 20,
                "level_footer": 2048,
                "tickets_title": 256,
                "tickets_message": 4000,
                "tickets_button_text": 80,
                "tickets_button_emoji": 20,
                "tickets_button_color": 20,
                "tickets_name": 100,
                "tickets_close_message": 2000,
                "tickets_color": 20,
                "application_title": 256,
                "application_message": 4000,
                "application_button_text": 80,
                "application_button_emoji": 20,
                "application_color": 20,
                "application_success_message": 2000,
                "application_log_message": 2000,
                "moderation_warn_message": 2000,
                "moderation_kick_message": 2000,
                "moderation_ban_message": 2000,
                "moderation_mute_message": 2000,
            }
            value = clean_text(
                value,
                limits.get(key, 4000),
            )
        updates[key] = value
    if not updates:
        return jsonify({
            "success": False,
            "error": "NoValidSettings",
        }), 400
    # -----------------------------------------------------
    # Level validation
    # -----------------------------------------------------
    if (
        "level_xp_min" in updates
        and "level_xp_max" in updates
        and updates["level_xp_min"]
        > updates["level_xp_max"]
    ):
        return jsonify({
            "success": False,
            "error": "InvalidXPRange",
            "message": "XP Min لا يمكن أن يكون أكبر من XP Max.",
        }), 400
    result = run_async(
        db.update_settings(
            int(guild_id),
            updates,
        )
    )
    if result is not True:
        return jsonify({
            "success": False,
            "error": "DatabaseError",
            "message": "تعذر حفظ إعدادات النظام.",
        }), 500
    return jsonify({
        "success": True,
        "system": system_name,
        "message": "تم حفظ إعدادات النظام بنجاح.",
        "updated": list(updates.keys()),
    })
# =========================================================
# System Toggle
# =========================================================
@dashboard_bp.route(
    "/api/<guild_id>/system/<system_name>",
    methods=["POST"],
)
@guild_required
def toggle_system(
    guild_id,
    guild,
    system_name,
):
    system_name = str(
        system_name
    ).strip().lower()
    if system_name not in SYSTEM_SETTINGS:
        return jsonify({
            "success": False,
            "error": "UnknownSystem",
        }), 404
    bot_guild = get_bot_guild(guild_id)
    if bot_guild is None:
        return jsonify({
            "success": False,
            "error": "BotNotInstalled",
            "message": "البوت غير موجود في السيرفر.",
        }), 400
    if not request.is_json:
        return jsonify({
            "success": False,
            "error": "InvalidJSON",
        }), 400
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "error": "InvalidData",
        }), 400
    enabled = data.get("enabled")
    if isinstance(enabled, bool):
        enabled_value = enabled
    elif isinstance(enabled, int):
        enabled_value = bool(enabled)
    elif isinstance(enabled, str):
        enabled_value = (
            enabled.lower()
            in {
                "1",
                "true",
                "on",
                "yes",
            }
        )
    else:
        return jsonify({
            "success": False,
            "error": "InvalidEnabled",
        }), 400
    result = run_async(
        db.set_enabled(
            int(guild_id),
            system_name,
            enabled_value,
        )
    )
    if result is not True:
        return jsonify({
            "success": False,
            "error": "DatabaseError",
            "message": "تعذر تغيير حالة النظام.",
        }), 500
    return jsonify({
        "success": True,
        "system": system_name,
        "enabled": enabled_value,
        "message": (
            "تم تشغيل النظام بنجاح."
            if enabled_value
            else "تم إيقاف النظام بنجاح."
        ),
    })
# =========================================================
# Channels API
# =========================================================
@dashboard_bp.route(
    "/api/<guild_id>/channels",
    methods=["GET"],
)
@guild_required
def get_channels(
    guild_id,
    guild,
):
    bot_guild = get_bot_guild(guild_id)
    if bot_guild is None:
        return jsonify({
            "success": False,
            "error": "BotNotInstalled",
        }), 400
    channels = []
    try:
        for channel in bot_guild.channels:
            if isinstance(
                channel,
                discord.TextChannel,
            ):
                channel_type = "text"
            elif isinstance(
                channel,
                discord.VoiceChannel,
            ):
                channel_type = "voice"
            elif isinstance(
                channel,
                discord.CategoryChannel,
            ):
                channel_type = "category"
            elif isinstance(
                channel,
                discord.StageChannel,
            ):
                channel_type = "stage"
            elif isinstance(
                channel,
                discord.ForumChannel,
            ):
                channel_type = "forum"
            else:
                channel_type = "other"
            channels.append({
                "id": str(channel.id),
                "name": channel.name,
                "type": channel_type,
                "position": safe_int(
                    getattr(
                        channel,
                        "position",
                        0,
                    )
                ),
                "category_id": (
                    str(channel.category_id)
                    if getattr(
                        channel,
                        "category_id",
                        None,
                    )
                    else None
                ),
            })
    except Exception as error:
        print(
            f"❌ Channel API error: {error}"
        )
        return jsonify({
            "success": False,
            "error": "ChannelFetchError",
            "message": "تعذر جلب قنوات السيرفر.",
        }), 500
    channels.sort(
        key=lambda item: (
            item["position"],
            item["name"].lower(),
        )
    )
    return jsonify({
        "success": True,
        "guild_id": str(
            guild.get("id")
        ),
        "channels": channels,
    })
# =========================================================
# Channel Configuration
# =========================================================
CHANNEL_SYSTEMS = {
    "welcome": "welcome",
    "level": "level",
    "levels": "level",
    "ticket": "ticketcategory",
    "tickets": "ticketcategory",
    "ticketcategory": "ticketcategory",
    "ticketlog": "ticketlog",
    "application": "application",
    "applications": "application",
    "applicationlog": "applicationlog",
    "moderationlog": "moderationlog",
    "logs": "logs",
    "commands": "commands",
}
@dashboard_bp.route(
    "/api/<guild_id>/channel",
    methods=["POST"],
)
@guild_required
def set_channel_api(
    guild_id,
    guild,
):
    bot_guild = get_bot_guild(guild_id)
    if bot_guild is None:
        return jsonify({
            "success": False,
            "error": "BotNotInstalled",
        }), 400
    if not request.is_json:
        return jsonify({
            "success": False,
            "error": "InvalidJSON",
        }), 400
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "error": "InvalidData",
        }), 400
    system = str(
        data.get("system", "")
    ).strip().lower()
    if system not in CHANNEL_SYSTEMS:
        return jsonify({
            "success": False,
            "error": "UnknownSystem",
        }), 400
    channel_id = clean_channel_id(
        data.get("channel_id")
    )
    if channel_id is not None:
        channel = bot_guild.get_channel(
            channel_id
        )
        if channel is None:
            return jsonify({
                "success": False,
                "error": "ChannelNotFound",
                "message": "الروم غير موجود في السيرفر.",
            }), 404
    result = run_async(
        db.set_channel(
            int(guild_id),
            CHANNEL_SYSTEMS[system],
            channel_id,
        )
    )
    if result is not True:
        return jsonify({
            "success": False,
            "error": "DatabaseError",
            "message": "تعذر حفظ الروم.",
        }), 500
    return jsonify({
        "success": True,
        "system": system,
        "channel_id": (
            str(channel_id)
            if channel_id is not None
            else None
        ),
        "message": "تم حفظ الروم بنجاح.",
    })
# =========================================================
# Message Configuration
# =========================================================
@dashboard_bp.route(
    "/api/<guild_id>/message",
    methods=["POST"],
)
@guild_required
def save_message_config(
    guild_id,
    guild,
):
    bot_guild = get_bot_guild(guild_id)
    if bot_guild is None:
        return jsonify({
            "success": False,
            "error": "BotNotInstalled",
        }), 400
    if not request.is_json:
        return jsonify({
            "success": False,
            "error": "InvalidJSON",
        }), 400
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({
            "success": False,
            "error": "InvalidData",
        }), 400
    system = str(
        data.get("system", "")
    ).strip().lower()
    if system not in {
        "welcome",
        "level",
        "levels",
        "ticket",
        "tickets",
    }:
        return jsonify({
            "success": False,
            "error": "UnknownSystem",
        }), 400
    result = run_async(
        db.save_message_config(
            int(guild_id),
            system,
            title=clean_text(
                data.get("title"),
                256,
            ),
            message=clean_text(
                data.get("message"),
                4000,
            ),
            color=clean_text(
                data.get("color"),
                20,
            ),
            footer=clean_text(
                data.get("footer"),
                2048,
            ),
        )
    )
    if result is not True:
        return jsonify({
            "success": False,
            "error": "DatabaseError",
            "message": "تعذر حفظ إعدادات الرسالة.",
        }), 500
    return jsonify({
        "success": True,
        "message": "تم حفظ إعدادات الرسالة بنجاح.",
    })
# =========================================================
# Bot Status
# =========================================================
@dashboard_bp.route(
    "/api/status",
    methods=["GET"],
)
def bot_status():
    bot = get_bot()
    if bot is None:
        return jsonify({
            "success": True,
            "online": False,
            "ready": False,
            "servers": 0,
            "latency": None,
        })
    try:
        ready = bool(
            bot.is_ready()
        )
        latency = None
        if ready:
            try:
                latency = round(
                    bot.latency * 1000,
                    2,
                )
            except Exception:
                latency = None
        bot_user = None
        if bot.user:
            bot_user = {
                "id": str(bot.user.id),
                "name": bot.user.name,
                "display_name": (
                    bot.user.display_name
                    if hasattr(
                        bot.user,
                        "display_name",
                    )
                    else bot.user.name
                ),
            }
        return jsonify({
            "success": True,
            "online": ready,
            "ready": ready,
            "servers": len(
                bot.guilds
            ),
            "latency": latency,
            "user": bot_user,
        })
    except Exception as error:
        print(
            f"⚠️ Bot status error: {error}"
        )
        return jsonify({
            "success": True,
            "online": False,
            "ready": False,
            "servers": 0,
            "latency": None,
        })
# =========================================================
# Logout
# =========================================================
@dashboard_bp.route(
    "/logout",
    methods=["GET"],
)
def dashboard_logout():
    session.clear()
    return redirect(
        url_for("login")
    )
