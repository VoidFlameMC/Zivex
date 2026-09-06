# =========================================================
# Zivex — Secure & Professional Dashboard
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
# Database / Async Helpers
# =========================================================

def run_async(coroutine, timeout=30):
    """
    تشغيل Coroutine داخل Event Loop الخاص بالبوت.

    مهم جدًا:
    لا نستخدم asyncio.run() هنا لأن البوت لديه Event Loop
    رئيسي يعمل باستمرار.

    Flask يعمل في Thread مختلف، لذلك نرسل العملية إلى
    Event Loop الخاص بالبوت باستخدام run_coroutine_threadsafe.
    """

    bot = get_bot()

    if bot is None:
        print("❌ Dashboard async error: Bot is not available.")

        try:
            coroutine.close()
        except Exception:
            pass

        return None

    try:
        loop = bot.loop
    except Exception as error:
        print(
            f"❌ Dashboard async error: "
            f"Could not get bot loop: {error}"
        )

        try:
            coroutine.close()
        except Exception:
            pass

        return None

    if loop is None:
        print("❌ Dashboard async error: Bot loop is None.")

        try:
            coroutine.close()
        except Exception:
            pass

        return None

    if not loop.is_running():
        print(
            "❌ Dashboard async error: "
            "Bot Event Loop is not running."
        )

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

        return future.result(
            timeout=timeout
        )

    except asyncio.TimeoutError:
        print(
            "❌ Dashboard async error: "
            "Database operation timed out."
        )

        try:
            future.cancel()
        except Exception:
            pass

        return None

    except Exception as error:
        print(
            f"❌ Dashboard async error: {error}"
        )

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
    """
    التحقق من Discord Guild ID.
    """

    if guild_id is None:
        return False

    guild_id = str(guild_id).strip()

    if not guild_id:
        return False

    if len(guild_id) > 30:
        return False

    if not guild_id.isdigit():
        return False

    try:
        value = int(guild_id)
    except ValueError:
        return False

    return value > 0


# =========================================================
# Authentication
# =========================================================

def get_logged_user():
    """
    بيانات المستخدم المسجل دخوله.
    """

    user = session.get("discord_user")

    if not isinstance(user, dict):
        return None

    if not user.get("id"):
        return None

    return user


def get_access_token():
    """
    Discord OAuth Access Token.
    """

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
    """
    الحصول على نسخة Zivex Bot المستخدمة بواسطة التطبيق.
    """

    return current_app.config.get(
        "ZIVEX_BOT"
    )


def get_bot_guild(guild_id):
    """
    الحصول على السيرفر من ذاكرة البوت.
    """

    if not valid_guild_id(guild_id):
        return None

    bot = get_bot()

    if bot is None:
        return None

    try:
        return bot.get_guild(
            int(guild_id)
        )
    except Exception as error:
        print(
            f"⚠️ Bot guild lookup error: {error}"
        )
        return None


# =========================================================
# Discord Permissions
# =========================================================

def can_manage_guild(guild_data):
    """
    السماح لمن لديه:
    Administrator
    أو
    Manage Server
    """

    if not isinstance(
        guild_data,
        dict,
    ):
        return False

    try:
        permissions = int(
            guild_data.get(
                "permissions",
                0,
            )
        )
    except (
        TypeError,
        ValueError,
    ):
        return False

    return bool(
        permissions
        & (
            ADMINISTRATOR
            | MANAGE_GUILD
        )
    )


# =========================================================
# Discord API
# =========================================================

def get_user_guilds():
    """
    جلب سيرفرات المستخدم من Discord OAuth.
    """

    token = get_access_token()

    if not token:
        return None

    try:
        response = discord_get(
            "/users/@me/guilds",
            token,
        )
    except Exception as error:
        print(
            f"❌ Discord guild request error: {error}"
        )
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

    if not isinstance(
        guilds,
        list,
    ):
        return None

    return guilds


# =========================================================
# Authorized Guild
# =========================================================

def get_authorized_guild(guild_id):
    """
    التحقق من أن المستخدم يستطيع إدارة السيرفر.
    """

    if not require_login():
        return None

    if not valid_guild_id(guild_id):
        return None

    guild_id = str(
        guild_id
    )

    guilds = get_user_guilds()

    if guilds is None:
        return None

    for guild in guilds:

        if not isinstance(
            guild,
            dict,
        ):
            continue

        current_id = str(
            guild.get(
                "id",
                "",
            )
        )

        if current_id != guild_id:
            continue

        if not can_manage_guild(
            guild
        ):
            return None

        return guild

    return None


# =========================================================
# Database
# =========================================================

def get_guild_settings(
    guild_id,
    bot_guild=None,
):
    """
    جلب إعدادات السيرفر.

    إذا لم يكن للسيرفر سجل في قاعدة البيانات،
    نقوم بإنشائه تلقائيًا.
    """

    if not valid_guild_id(
        guild_id
    ):
        return {}

    guild_id = int(
        guild_id
    )

    settings = run_async(
        db.get_guild(
            guild_id
        )
    )

    if settings:
        return settings

    if bot_guild is not None:

        icon_url = None

        try:
            if bot_guild.icon:
                icon_url = str(
                    bot_guild.icon.url
                )
        except Exception:
            icon_url = None

        created = run_async(
            db.ensure_guild(
                guild_id,
                bot_guild.name,
                icon_url,
            )
        )

        if created is False:
            print(
                "⚠️ Could not ensure guild "
                f"{guild_id}"
            )

        settings = run_async(
            db.get_guild(
                guild_id
            )
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
    """
    حالة جميع أنظمة Zivex.
    """

    if not isinstance(
        settings,
        dict,
    ):
        settings = {}

    return {
        system: bool(
            safe_int(
                settings.get(
                    setting,
                    0,
                )
            )
        )
        for system, setting
        in SYSTEM_SETTINGS.items()
    }


# =========================================================
# Guild Statistics
# =========================================================

def get_guild_statistics(
    bot_guild
):
    """
    إحصائيات السيرفر من Discord Bot.
    """

    empty_stats = {
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
        return empty_stats

    try:
        channels = list(
            bot_guild.channels
        )

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
            "channels": len(
                channels
            ),
            "text_channels": text_channels,
            "voice_channels": voice_channels,
            "categories": categories,
            "roles": len(
                bot_guild.roles
            ),
            "emojis": len(
                bot_guild.emojis
            ),
            "stickers": len(
                bot_guild.stickers
            ),
        }

    except Exception as error:
        print(
            f"⚠️ Guild statistics error: {error}"
        )

        return empty_stats


# =========================================================
# Guild Data
# =========================================================

def build_guild_data(
    guild,
    bot_guild=None,
):
    """
    تجهيز بيانات السيرفر للـDashboard.
    """

    guild_id = str(
        guild.get(
            "id",
            "",
        )
    )

    settings = get_guild_settings(
        guild_id,
        bot_guild,
    )

    statistics = get_guild_statistics(
        bot_guild
    )

    return {
        "id": guild_id,
        "name": guild.get(
            "name",
            "Unknown Server",
        ),
        "icon": guild.get(
            "icon"
        ),
        "owner": bool(
            guild.get(
                "owner",
                False,
            )
        ),
        "bot_installed": (
            bot_guild is not None
        ),
        "settings": settings,
        "systems": get_system_status(
            settings
        ),
        "statistics": statistics,
    }


# =========================================================
# Login Decorator
# =========================================================

def login_required(view):
    @wraps(view)
    def wrapped(
        *args,
        **kwargs,
    ):

        if not require_login():
            return redirect(
                url_for("login")
            )

        return view(
            *args,
            **kwargs,
        )

    return wrapped


# =========================================================
# Guild Decorator
# =========================================================

def guild_required(view):
    """
    حماية API الخاص بالسيرفر.
    """

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
                "message": (
                    "يجب تسجيل الدخول أولًا."
                ),
            }), 401

        guild = get_authorized_guild(
            guild_id
        )

        if guild is None:
            return jsonify({
                "success": False,
                "error": "Forbidden",
                "message": (
                    "لا تملك صلاحية إدارة هذا السيرفر."
                ),
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
    """
    الصفحة الرئيسية للـDashboard.
    """

    guilds = get_user_guilds()

    if guilds is None:
        session.clear()

        return redirect(
            url_for("login")
        )

    authorized_guilds = []

    for guild in guilds:

        if not isinstance(
            guild,
            dict,
        ):
            continue

        if not can_manage_guild(
            guild
        ):
            continue

        guild_id = guild.get(
            "id"
        )

        if not valid_guild_id(
            guild_id
        ):
            continue

        bot_guild = get_bot_guild(
            guild_id
        )

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
            "servers": len(
                authorized_guilds
            ),
            "installed": sum(
                1
                for guild
                in authorized_guilds
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

@dashboard_bp.route(
    "/<guild_id>"
)
@login_required
def guild_dashboard(
    guild_id
):
    """
    لوحة التحكم الخاصة بسيرفر محدد.
    """

    guild = get_authorized_guild(
        guild_id
    )

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

    bot_guild = get_bot_guild(
        guild_id
    )

    selected_guild = build_guild_data(
        guild,
        bot_guild,
    )

    return render_template(
        "dashboard.html",
        user=get_logged_user(),
        guilds=[
            selected_guild
        ],
        selected_guild=selected_guild,
        dashboard_stats={
            "servers": 1,
            "installed": int(
                selected_guild[
                    "bot_installed"
                ]
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
    bot_guild = get_bot_guild(
        guild_id
    )

    return jsonify({
        "success": True,
        "authorized": True,
        "guild_id": str(
            guild.get("id")
        ),
        "bot_installed": (
            bot_guild is not None
        ),
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
    """
    معلومات وإحصائيات السيرفر.
    """

    bot_guild = get_bot_guild(
        guild_id
    )

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
            "icon": guild.get(
                "icon"
            ),
            "owner": bool(
                guild.get(
                    "owner",
                    False,
                )
            ),
            "bot_installed": (
                bot_guild is not None
            ),
        },
        "statistics": get_guild_statistics(
            bot_guild
        ),
        "systems": get_system_status(
            settings
        ),
    })


# =========================================================
# Settings API — GET
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
    """
    جلب إعدادات السيرفر.
    """

    bot_guild = get_bot_guild(
        guild_id
    )

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
# Settings API — POST
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
    """
    تحديث إعداد واحد أو عدة إعدادات.
    """

    bot_guild = get_bot_guild(
        guild_id
    )

    if bot_guild is None:
        return jsonify({
            "success": False,
            "error": "BotNotInstalled",
            "message": (
                "البوت غير موجود في هذا السيرفر."
            ),
        }), 400

    if not request.is_json:
        return jsonify({
            "success": False,
            "error": "InvalidJSON",
            "message": (
                "يجب إرسال البيانات بصيغة JSON."
            ),
        }), 400

    data = request.get_json(
        silent=True
    )

    if not isinstance(
        data,
        dict,
    ):
        return jsonify({
            "success": False,
            "error": "InvalidData",
            "message": (
                "بيانات الإعدادات غير صحيحة."
            ),
        }), 400

    # -----------------------------------------------------
    # إعداد واحد
    # -----------------------------------------------------

    if "key" in data:

        key = data.get(
            "key"
        )

        if not isinstance(
            key,
            str,
        ):
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

        if len(key) > 100:
            return jsonify({
                "success": False,
                "error": "KeyTooLong",
            }), 400

        if "value" not in data:
            return jsonify({
                "success": False,
                "error": "MissingValue",
            }), 400

        value = data.get(
            "value"
        )

        result = run_async(
            db.update_setting(
                int(guild_id),
                key,
                value,
            )
        )

        if result is not True:
            return jsonify({
                "success": False,
                "error": "DatabaseError",
                "message": (
                    "تعذر حفظ الإعداد."
                ),
            }), 500

        return jsonify({
            "success": True,
            "message": (
                "تم حفظ الإعداد بنجاح."
            ),
            "key": key,
            "value": value,
        })

    # -----------------------------------------------------
    # عدة إعدادات
    # -----------------------------------------------------

    settings = data.get(
        "settings"
    )

    if isinstance(
        settings,
        dict,
    ):

        if not settings:
            return jsonify({
                "success": False,
                "error": "EmptySettings",
            }), 400

        cleaned_settings = {}

        for key, value in settings.items():

            if not isinstance(
                key,
                str,
            ):
                continue

            key = key.strip()

            if not key:
                continue

            if len(key) > 100:
                continue

            cleaned_settings[
                key
            ] = value

        if not cleaned_settings:
            return jsonify({
                "success": False,
                "error": "InvalidSettings",
            }), 400

        result = run_async(
            db.update_settings(
                int(guild_id),
                cleaned_settings,
            )
        )

        if result is not True:
            return jsonify({
                "success": False,
                "error": "DatabaseError",
                "message": (
                    "تعذر حفظ الإعدادات."
                ),
            }), 500

        return jsonify({
            "success": True,
            "message": (
                "تم حفظ الإعدادات بنجاح."
            ),
            "updated": list(
                cleaned_settings.keys()
            ),
        })

    return jsonify({
        "success": False,
        "error": "MissingSettings",
        "message": (
            "لم يتم إرسال أي إعدادات."
        ),
    }), 400


# =========================================================
# System Toggle API
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
    """
    تشغيل أو إيقاف أحد أنظمة Zivex.
    """

    bot_guild = get_bot_guild(
        guild_id
    )

    if bot_guild is None:
        return jsonify({
            "success": False,
            "error": "BotNotInstalled",
            "message": (
                "البوت غير موجود في السيرفر."
            ),
        }), 400

    system_name = str(
        system_name
    ).strip().lower()

    setting = SYSTEM_SETTINGS.get(
        system_name
    )

    if not setting:
        return jsonify({
            "success": False,
            "error": "UnknownSystem",
            "message": (
                "النظام المطلوب غير موجود."
            ),
        }), 404

    if not request.is_json:
        return jsonify({
            "success": False,
            "error": "InvalidJSON",
        }), 400

    data = request.get_json(
        silent=True
    )

    if not isinstance(
        data,
        dict,
    ):
        return jsonify({
            "success": False,
            "error": "InvalidData",
        }), 400

    if "enabled" not in data:
        return jsonify({
            "success": False,
            "error": "MissingEnabled",
        }), 400

    enabled = data.get(
        "enabled"
    )

    if isinstance(
        enabled,
        bool,
    ):
        enabled_value = (
            1 if enabled else 0
        )

    elif isinstance(
        enabled,
        int,
    ):
        enabled_value = (
            1 if enabled else 0
        )

    elif isinstance(
        enabled,
        str,
    ):
        enabled_value = (
            1
            if enabled.lower()
            in {
                "1",
                "true",
                "on",
                "yes",
            }
            else 0
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
            bool(enabled_value),
        )
    )

    if result is not True:
        return jsonify({
            "success": False,
            "error": "DatabaseError",
            "message": (
                "تعذر تغيير حالة النظام."
            ),
        }), 500

    return jsonify({
        "success": True,
        "system": system_name,
        "enabled": bool(
            enabled_value
        ),
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
    """
    جلب قنوات السيرفر.
    """

    bot_guild = get_bot_guild(
        guild_id
    )

    if bot_guild is None:
        return jsonify({
            "success": False,
            "error": "BotNotInstalled",
            "message": (
                "البوت غير موجود في هذا السيرفر."
            ),
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
                "id": str(
                    channel.id
                ),
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
                    str(
                        channel.category_id
                    )
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
            "message": (
                "تعذر جلب قنوات السيرفر."
            ),
        }), 500

    channels.sort(
        key=lambda channel: (
            channel["position"],
            channel["name"].lower(),
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
# Set Channel API
# =========================================================

CHANNEL_SYSTEMS = {
    "welcome": "welcome",
    "level": "level",
    "levels": "level",

    "ticketcategory": "ticketcategory",
    "ticketlog": "ticketlog",

    "application": "application",
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
    """
    تعيين روم لأحد أنظمة Zivex.
    """

    bot_guild = get_bot_guild(
        guild_id
    )

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

    data = request.get_json(
        silent=True
    )

    if not isinstance(
        data,
        dict,
    ):
        return jsonify({
            "success": False,
            "error": "InvalidData",
        }), 400

    system = str(
        data.get(
            "system",
            "",
        )
    ).strip().lower()

    if system not in CHANNEL_SYSTEMS:
        return jsonify({
            "success": False,
            "error": "UnknownSystem",
        }), 400

    channel_id = data.get(
        "channel_id"
    )

    if channel_id in (
        None,
        "",
        "null",
    ):
        channel_id = None

    else:

        if not valid_guild_id(
            channel_id
        ):
            return jsonify({
                "success": False,
                "error": "InvalidChannel",
            }), 400

        channel_id = int(
            channel_id
        )

        channel = bot_guild.get_channel(
            channel_id
        )

        if channel is None:
            return jsonify({
                "success": False,
                "error": "ChannelNotFound",
                "message": (
                    "الروم غير موجود في السيرفر."
                ),
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
            "message": (
                "تعذر حفظ الروم."
            ),
        }), 500

    return jsonify({
        "success": True,
        "system": system,
        "channel_id": (
            str(channel_id)
            if channel_id is not None
            else None
        ),
        "message": (
            "تم حفظ الروم بنجاح."
        ),
    })


# =========================================================
# Message Configuration API
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
    """
    حفظ إعدادات الرسائل.
    """

    bot_guild = get_bot_guild(
        guild_id
    )

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

    data = request.get_json(
        silent=True
    )

    if not isinstance(
        data,
        dict,
    ):
        return jsonify({
            "success": False,
            "error": "InvalidData",
        }), 400

    system = str(
        data.get(
            "system",
            "",
        )
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
            "message": (
                "هذا النظام لا يدعم إعداد الرسائل حاليًا."
            ),
        }), 400

    title = data.get(
        "title"
    )
    message = data.get(
        "message"
    )
    color = data.get(
        "color"
    )
    footer = data.get(
        "footer"
    )

    if title is not None:
        title = str(title)[:256]

    if message is not None:
        message = str(message)[:4000]

    if color is not None:
        color = str(color)[:20]

    if footer is not None:
        footer = str(footer)[:2048]

    result = run_async(
        db.save_message_config(
            int(guild_id),
            system,
            title=title,
            message=message,
            color=color,
            footer=footer,
        )
    )

    if result is not True:
        return jsonify({
            "success": False,
            "error": "DatabaseError",
            "message": (
                "تعذر حفظ إعدادات الرسالة."
            ),
        }), 500

    return jsonify({
        "success": True,
        "message": (
            "تم حفظ إعدادات الرسالة بنجاح."
        ),
    })


# =========================================================
# Bot Status API
# =========================================================

@dashboard_bp.route(
    "/api/status",
    methods=["GET"],
)
def bot_status():
    """
    حالة Zivex العامة.
    """

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
                "id": str(
                    bot.user.id
                ),
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
    """
    تسجيل الخروج من Dashboard.
    """

    session.clear()

    return redirect(
        url_for("login")
    )
