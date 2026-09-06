from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    session,
    url_for,
)

from web.auth import discord_get


# =========================================================
# Zivex Secure Dashboard
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
# Security Helpers
# =========================================================

def get_logged_user():
    """
    يرجع بيانات المستخدم المسجل دخوله.
    """

    user = session.get("discord_user")

    if not isinstance(user, dict):
        return None

    user_id = user.get("id")

    if not user_id:
        return None

    return user


def get_access_token():
    """
    يرجع OAuth token من الجلسة.
    """

    token = session.get(
        "discord_access_token"
    )

    if not token:
        return None

    if not isinstance(token, str):
        return None

    return token


def require_login():
    """
    التحقق من تسجيل الدخول.
    """

    user = get_logged_user()
    token = get_access_token()

    return bool(user and token)


# =========================================================
# Bot Access
# =========================================================

def get_bot():
    """
    الحصول على نسخة Zivex Bot المستخدمة من التطبيق.
    """

    return current_app.config.get(
        "ZIVEX_BOT"
    )


# =========================================================
# Discord Permissions
# =========================================================

def can_manage_guild(guild_data):
    """
    التحقق من Administrator أو Manage Server.
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
# Get User Guilds
# =========================================================

def get_user_guilds():
    """
    جلب السيرفرات من Discord.

    لا نثق بأي Guild ID يرسله المستخدم.
    """

    token = get_access_token()

    if not token:
        return None

    response = discord_get(
        "/users/@me/guilds",
        token,
    )

    if response is None:
        return None

    if response.status_code == 401:
        session.clear()
        return None

    if response.status_code != 200:
        return None

    try:
        guilds = response.json()

    except ValueError:
        return None

    if not isinstance(guilds, list):
        return None

    return guilds


# =========================================================
# Get Authorized Guild
# =========================================================

def get_authorized_guild(guild_id):
    """
    التحقق من أن المستخدم يستطيع إدارة السيرفر.
    """

    if not require_login():
        return None

    if not guild_id:
        return None

    guild_id = str(guild_id)

    # -----------------------------------------------------
    # منع قيم ضخمة
    # -----------------------------------------------------

    if len(guild_id) > 30:
        return None

    # -----------------------------------------------------
    # Discord Snowflake Validation
    # -----------------------------------------------------

    if not guild_id.isdigit():
        return None

    try:
        requested_id = int(guild_id)

    except ValueError:
        return None

    if requested_id <= 0:
        return None

    # -----------------------------------------------------
    # Get Guilds
    # -----------------------------------------------------

    guilds = get_user_guilds()

    if guilds is None:
        return None

    # -----------------------------------------------------
    # Authorization
    # -----------------------------------------------------

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

        if not can_manage_guild(guild):
            return None

        return guild

    return None


# =========================================================
# Dashboard Home
# =========================================================

@dashboard_bp.route("/")
def dashboard_home():
    """
    الصفحة الرئيسية للـDashboard.
    """

    if not require_login():
        return redirect(
            url_for("login")
        )

    guilds = get_user_guilds()

    if guilds is None:
        session.clear()

        return redirect(
            url_for("login")
        )

    # -----------------------------------------------------
    # السيرفرات التي يستطيع المستخدم إدارتها
    # -----------------------------------------------------

    authorized_guilds = []

    for guild in guilds:

        if not isinstance(
            guild,
            dict,
        ):
            continue

        if not can_manage_guild(guild):
            continue

        guild_id = guild.get("id")

        if not guild_id:
            continue

        authorized_guilds.append({
            "id": str(guild_id),
            "name": guild.get(
                "name",
                "Unknown Server",
            ),
            "icon": guild.get("icon"),
            "owner": guild.get(
                "owner",
                False,
            ),
        })

    # -----------------------------------------------------
    # Bot Guild IDs
    # -----------------------------------------------------

    bot = get_bot()

    bot_guild_ids = set()

    if bot is not None:

        try:

            bot_guild_ids = {
                str(guild.id)
                for guild in bot.guilds
            }

        except Exception:
            bot_guild_ids = set()

    # -----------------------------------------------------
    # إضافة حالة البوت لكل سيرفر
    # -----------------------------------------------------

    for guild in authorized_guilds:

        guild["bot_installed"] = (
            guild["id"]
            in bot_guild_ids
        )

    # -----------------------------------------------------
    # Render Dashboard
    # -----------------------------------------------------

    return render_template(
        "dashboard.html",
        user=get_logged_user(),
        guilds=authorized_guilds,
    )


# =========================================================
# Guild Dashboard
# =========================================================

@dashboard_bp.route("/<guild_id>")
def guild_dashboard(guild_id):
    """
    Dashboard الخاص بسيرفر معين.
    """

    if not require_login():
        return redirect(
            url_for("login")
        )

    guild = get_authorized_guild(
        guild_id
    )

    if guild is None:
        return jsonify({
            "success": False,
            "error": "Forbidden",
        }), 403

    bot = get_bot()

    bot_guild = None

    if bot is not None:

        try:

            bot_guild = bot.get_guild(
                int(guild_id)
            )

        except (
            TypeError,
            ValueError,
        ):
            bot_guild = None

    return render_template(
        "dashboard.html",
        user=get_logged_user(),
        guilds=[{
            "id": str(
                guild.get("id")
            ),
            "name": guild.get(
                "name",
                "Unknown Server",
            ),
            "icon": guild.get("icon"),
            "owner": guild.get(
                "owner",
                False,
            ),
            "bot_installed": (
                bot_guild is not None
            ),
        }],
        selected_guild={
            "id": str(
                guild.get("id")
            ),
            "name": guild.get(
                "name",
                "Unknown Server",
            ),
            "icon": guild.get("icon"),
            "bot_installed": (
                bot_guild is not None
            ),
        },
    )


# =========================================================
# Guild Authorization API
# =========================================================

@dashboard_bp.route(
    "/api/<guild_id>/authorization"
)
def guild_authorization(guild_id):

    if not require_login():

        return jsonify({
            "success": False,
            "error": "Unauthorized",
        }), 401

    guild = get_authorized_guild(
        guild_id
    )

    if guild is None:

        return jsonify({
            "success": False,
            "error": "Forbidden",
        }), 403

    bot = get_bot()

    bot_installed = False

    if bot is not None:

        try:

            bot_installed = (
                bot.get_guild(
                    int(guild_id)
                )
                is not None
            )

        except (
            TypeError,
            ValueError,
        ):
            bot_installed = False

    return jsonify({
        "success": True,
        "authorized": True,
        "guild_id": str(
            guild.get("id")
        ),
        "bot_installed": bot_installed,
    })


# =========================================================
# Logout
# =========================================================

@dashboard_bp.route("/logout")
def dashboard_logout():

    session.clear()

    return redirect(
        url_for("login")
    )
