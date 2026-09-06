import secrets
from urllib.parse import urlencode

import requests
from flask import (
    Blueprint,
    redirect,
    request,
    session,
    url_for,
)

from config import (
    DISCORD_CLIENT_ID,
    DISCORD_CLIENT_SECRET,
    WEB_URL,
)


# =========================================================
# Zivex Secure Discord OAuth2
# =========================================================

auth_bp = Blueprint(
    "auth",
    __name__,
    url_prefix="/auth",
)


# =========================================================
# Discord OAuth Configuration
# =========================================================

DISCORD_API = "https://discord.com/api/v10"

DISCORD_AUTHORIZE_URL = (
    "https://discord.com/oauth2/authorize"
)

DISCORD_TOKEN_URL = (
    f"{DISCORD_API}/oauth2/token"
)

OAUTH_TIMEOUT = (5, 15)


# =========================================================
# Redirect URI
# =========================================================

def get_redirect_uri():
    """
    رابط OAuth يجب أن يطابق الرابط الموجود
    في Discord Developer Portal بشكل كامل.
    """

    if not WEB_URL:
        return None

    return (
        f"{WEB_URL.rstrip('/')}"
        "/auth/callback"
    )


# =========================================================
# Security Helpers
# =========================================================

def generate_secure_state():
    """
    إنشاء State قوي لحماية OAuth من CSRF.
    """

    return secrets.token_urlsafe(48)


def generate_oauth_nonce():
    """
    إنشاء Nonce إضافي للجلسة.
    """

    return secrets.token_urlsafe(32)


def create_oauth_session():
    """
    إنشاء جلسة OAuth جديدة.
    """

    state = generate_secure_state()
    nonce = generate_oauth_nonce()

    session.clear()

    session["oauth_state"] = state
    session["oauth_nonce"] = nonce

    session.permanent = True

    return state


def validate_oauth_state(received_state):
    """
    التحقق من State القادم من Discord.
    """

    saved_state = session.pop(
        "oauth_state",
        None,
    )

    if not saved_state:
        return False

    if not received_state:
        return False

    if not isinstance(saved_state, str):
        return False

    if not isinstance(received_state, str):
        return False

    if len(saved_state) < 32:
        return False

    return secrets.compare_digest(
        saved_state,
        received_state,
    )


def clear_sensitive_session():
    """
    حذف بيانات المصادقة من الجلسة.
    """

    keys = (
        "discord_user",
        "discord_access_token",
        "discord_token_type",
        "discord_token_expires",
        "oauth_state",
        "oauth_nonce",
    )

    for key in keys:
        session.pop(key, None)


# =========================================================
# Safe Discord API Request
# =========================================================

def discord_get(
    endpoint,
    access_token,
):
    """
    تنفيذ GET إلى Discord API بدون تسجيل
    الـAccess Token في Logs.
    """

    if not access_token:
        return None

    if not isinstance(access_token, str):
        return None

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "User-Agent": "Zivex-Dashboard/1.0",
    }

    try:
        return requests.get(
            f"{DISCORD_API}{endpoint}",
            headers=headers,
            timeout=OAUTH_TIMEOUT,
        )

    except requests.RequestException:
        return None


# =========================================================
# Login
# =========================================================

@auth_bp.route("/login")
def oauth_login():

    if session.get("discord_user"):
        return redirect(
            url_for(
                "dashboard.dashboard_home"
            )
        )

    # -----------------------------------------------------
    # Environment Variables
    # -----------------------------------------------------

    if not DISCORD_CLIENT_ID:
        return (
            "❌ إعداد Discord Client ID غير موجود.",
            500,
        )

    if not DISCORD_CLIENT_SECRET:
        return (
            "❌ إعداد Discord Client Secret غير موجود.",
            500,
        )

    redirect_uri = get_redirect_uri()

    if not redirect_uri:
        return (
            "❌ WEB_URL غير مضبوط.",
            500,
        )

    # -----------------------------------------------------
    # OAuth Session
    # -----------------------------------------------------

    state = create_oauth_session()

    # -----------------------------------------------------
    # Discord OAuth2
    # -----------------------------------------------------

    params = {
        "client_id": DISCORD_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": "identify guilds",
        "state": state,
        "prompt": "consent",
    }

    authorize_url = (
        f"{DISCORD_AUTHORIZE_URL}?"
        f"{urlencode(params)}"
    )

    return redirect(authorize_url)


# =========================================================
# OAuth Callback
# =========================================================

@auth_bp.route("/callback")
def oauth_callback():

    # -----------------------------------------------------
    # Discord Error
    # -----------------------------------------------------

    oauth_error = request.args.get("error")

    if oauth_error:
        clear_sensitive_session()

        return redirect(
            url_for("index")
        )

    # -----------------------------------------------------
    # Code + State
    # -----------------------------------------------------

    code = request.args.get(
        "code",
        "",
    )

    state = request.args.get(
        "state",
        "",
    )

    # -----------------------------------------------------
    # Basic Validation
    # -----------------------------------------------------

    if not code:
        clear_sensitive_session()

        return (
            "❌ لم يتم استلام رمز تسجيل الدخول.",
            400,
        )

    if not state:
        clear_sensitive_session()

        return (
            "❌ طلب تسجيل الدخول غير صالح.",
            400,
        )

    if len(code) > 2048:
        clear_sensitive_session()

        return (
            "❌ طلب تسجيل الدخول غير صالح.",
            400,
        )

    if len(state) > 512:
        clear_sensitive_session()

        return (
            "❌ طلب تسجيل الدخول غير صالح.",
            400,
        )

    # -----------------------------------------------------
    # CSRF Protection
    # -----------------------------------------------------

    if not validate_oauth_state(state):
        clear_sensitive_session()

        return (
            "❌ جلسة تسجيل الدخول غير صالحة أو منتهية.",
            403,
        )

    # -----------------------------------------------------
    # Environment Validation
    # -----------------------------------------------------

    if not DISCORD_CLIENT_ID:
        clear_sensitive_session()

        return (
            "❌ إعداد Discord Client ID غير موجود.",
            500,
        )

    if not DISCORD_CLIENT_SECRET:
        clear_sensitive_session()

        return (
            "❌ إعداد Discord Client Secret غير موجود.",
            500,
        )

    redirect_uri = get_redirect_uri()

    if not redirect_uri:
        clear_sensitive_session()

        return (
            "❌ WEB_URL غير مضبوط.",
            500,
        )

    # =====================================================
    # Exchange Authorization Code
    # =====================================================

    token_data = {
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }

    token_headers = {
        "Content-Type":
            "application/x-www-form-urlencoded",
        "Accept":
            "application/json",
        "User-Agent":
            "Zivex-Dashboard/1.0",
    }

    try:
        token_response = requests.post(
            DISCORD_TOKEN_URL,
            data=token_data,
            headers=token_headers,
            timeout=OAUTH_TIMEOUT,
        )

    except requests.RequestException:
        clear_sensitive_session()

        return (
            "❌ تعذر الاتصال بخدمة Discord.",
            502,
        )

    if token_response.status_code != 200:
        clear_sensitive_session()

        return (
            "❌ فشل التحقق من تسجيل الدخول.",
            401,
        )

    try:
        token_json = token_response.json()

    except ValueError:
        clear_sensitive_session()

        return (
            "❌ استجابة غير صالحة من Discord.",
            502,
        )

    # =====================================================
    # Token Validation
    # =====================================================

    access_token = token_json.get(
        "access_token"
    )

    token_type = token_json.get(
        "token_type"
    )

    expires_in = token_json.get(
        "expires_in"
    )

    if not access_token:
        clear_sensitive_session()

        return (
            "❌ لم يتم الحصول على رمز المصادقة.",
            401,
        )

    if not isinstance(access_token, str):
        clear_sensitive_session()

        return (
            "❌ رمز المصادقة غير صالح.",
            401,
        )

    if len(access_token) < 10:
        clear_sensitive_session()

        return (
            "❌ رمز المصادقة غير صالح.",
            401,
        )

    # =====================================================
    # Get Discord User
    # =====================================================

    user_response = discord_get(
        "/users/@me",
        access_token,
    )

    if user_response is None:
        clear_sensitive_session()

        return (
            "❌ تعذر الاتصال بـ Discord.",
            502,
        )

    if user_response.status_code != 200:
        clear_sensitive_session()

        return (
            "❌ تعذر التحقق من حساب Discord.",
            401,
        )

    try:
        user = user_response.json()

    except ValueError:
        clear_sensitive_session()

        return (
            "❌ بيانات حساب Discord غير صالحة.",
            502,
        )

    # =====================================================
    # User Validation
    # =====================================================

    user_id = user.get("id")
    username = user.get("username")
    global_name = user.get("global_name")
    avatar = user.get("avatar")

    if not user_id:
        clear_sensitive_session()

        return (
            "❌ لم يتم التعرف على حساب Discord.",
            401,
        )

    if not isinstance(user_id, str):
        clear_sensitive_session()

        return (
            "❌ معرف Discord غير صالح.",
            401,
        )

    if not username:
        username = "Unknown"

    # =====================================================
    # Session Rotation
    # =====================================================

    session.clear()

    session.permanent = True

    # =====================================================
    # Store User
    # =====================================================

    session["discord_user"] = {
        "id": user_id,
        "username": str(username),
        "global_name": (
            str(global_name)
            if global_name
            else None
        ),
        "avatar": (
            str(avatar)
            if avatar
            else None
        ),
    }

    # =====================================================
    # Store OAuth Token
    # =====================================================
    #
    # لا تتم طباعة التوكن أو عرضه للمستخدم.
    # =====================================================

    session["discord_access_token"] = (
        access_token
    )

    if token_type:
        session["discord_token_type"] = (
            str(token_type)
        )

    if expires_in is not None:
        try:
            session["discord_token_expires"] = int(
                expires_in
            )

        except (
            TypeError,
            ValueError,
        ):
            pass

    # =====================================================
    # Dashboard
    # =====================================================

    return redirect(
        url_for(
            "dashboard.dashboard_home"
        )
    )


# =========================================================
# Logout
# =========================================================

@auth_bp.route("/logout")
def oauth_logout():

    clear_sensitive_session()

    session.clear()

    return redirect(
        url_for("index")
    )
