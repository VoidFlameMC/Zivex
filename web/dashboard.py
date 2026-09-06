from flask import (
    Blueprint,
    jsonify,
    redirect,
    session,
    url_for
)

from web.auth import discord_get


# =========================================================
# Zivex Secure Dashboard
# =========================================================

dashboard_bp = Blueprint(
    "dashboard",
    __name__,
    url_prefix="/dashboard"
)


# =========================================================
# Security Helpers
# =========================================================

def get_logged_user():
    """
    يرجع بيانات المستخدم المسجل دخوله.
    """

    user = session.get(
        "discord_user"
    )

    if not isinstance(
        user,
        dict
    ):
        return None

    user_id = user.get(
        "id"
    )

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

    if not isinstance(
        token,
        str
    ):
        return None

    return token


def require_login():
    """
    التحقق من تسجيل الدخول.
    """

    user = get_logged_user()
    token = get_access_token()

    if not user or not token:
        return False

    return True


# =========================================================
# Discord Permissions
# =========================================================

ADMINISTRATOR = 1 << 3
MANAGE_GUILD = 1 << 5


def can_manage_guild(
    guild_data
):
    """
    التحقق من Administrator أو Manage Server.
    """

    if not isinstance(
        guild_data,
        dict
    ):
        return False

    try:
        permissions = int(
            guild_data.get(
                "permissions",
                0
            )
        )

    except (
        TypeError,
        ValueError
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

    لا نثق بأي guild ID يرسله المستخدم.
    """

    token = get_access_token()

    if not token:
        return None

    response = discord_get(
        "/users/@me/guilds",
        token
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

    if not isinstance(
        guilds,
        list
    ):
        return None

    return guilds


# =========================================================
# Get Authorized Guild
# =========================================================

def get_authorized_guild(
    guild_id
):
    """
    أهم طبقة في Dashboard.

    المستخدم لازم:
    1. يكون مسجل دخول.
    2. السيرفر موجود في حساب Discord.
    3. عنده Administrator أو Manage Server.

    ولا يكفي إرسال Guild ID فقط.
    """

    if not require_login():
        return None

    if not guild_id:
        return None

    # -----------------------------------------------------
    # منع قيم ضخمة
    # -----------------------------------------------------

    if len(str(guild_id)) > 30:
        return None

    try:
        requested_id = int(
            guild_id
        )

    except (
        TypeError,
        ValueError
    ):
        return None

    if requested_id <= 0:
        return None

    guilds = get_user_guilds()

    if guilds is None:
        return None

    for guild in guilds:

        if not isinstance(
            guild,
            dict
        ):
            continue

        current_id = str(
            guild.get(
                "id",
                ""
            )
        )

        if current_id != str(
            requested_id
        ):
            continue

        if not can_manage_guild(
            guild
        ):
            return None

        return guild

    return None


# =========================================================
# Dashboard Home
# =========================================================

@dashboard_bp.route("/")
def dashboard_home():

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
    # عرض السيرفرات التي يستطيع المستخدم إدارتها فقط
    # -----------------------------------------------------

    authorized_guilds = []

    for guild in guilds:

        if not isinstance(
            guild,
            dict
        ):
            continue

        if not can_manage_guild(
            guild
        ):
            continue

        authorized_guilds.append({
            "id": str(
                guild.get(
                    "id"
                )
            ),
            "name": guild.get(
                "name",
                "Unknown Server"
            ),
            "icon": guild.get(
                "icon"
            )
        })

    return jsonify({
        "success": True,
        "user": get_logged_user(),
        "guilds": authorized_guilds
    })


# =========================================================
# Guild Authorization Test
# =========================================================

@dashboard_bp.route(
    "/<guild_id>"
)
def guild_dashboard(
    guild_id
):

    if not require_login():
        return redirect(
            url_for("login")
        )

    # -----------------------------------------------------
    # Authorization
    # -----------------------------------------------------

    guild = get_authorized_guild(
        guild_id
    )

    if guild is None:
        return jsonify({
            "success": False,
            "error": "Forbidden"
        }), 403

    # -----------------------------------------------------
    # معلومات آمنة فقط
    # -----------------------------------------------------

    return jsonify({
        "success": True,
        "guild": {
            "id": str(
                guild.get(
                    "id"
                )
            ),
            "name": guild.get(
                "name",
                "Unknown Server"
            ),
            "icon": guild.get(
                "icon"
            )
        }
    })


# =========================================================
# Guild Authorization API
# =========================================================

@dashboard_bp.route(
    "/api/<guild_id>/authorization"
)
def guild_authorization(
    guild_id
):

    if not require_login():
        return jsonify({
            "success": False,
            "error": "Unauthorized"
        }), 401

    guild = get_authorized_guild(
        guild_id
    )

    if guild is None:
        return jsonify({
            "success": False,
            "error": "Forbidden"
        }), 403

    return jsonify({
        "success": True,
        "authorized": True,
        "guild_id": str(
            guild.get(
                "id"
            )
        )
    })


# =========================================================
# Logout Protection
# =========================================================

@dashboard_bp.route(
    "/logout"
)
def dashboard_logout():

    session.clear()

    return redirect(
        url_for("login")
    )
