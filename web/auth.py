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

USER_AGENT = "Zivex-Dashboard/1.0"


# =========================================================
# Redirect URI
# =========================================================

def get_redirect_uri():
    """
    إنشاء رابط OAuth Callback.
    يجب أن يطابق الرابط الموجود في
    Discord Developer Portal بشكل كامل.
    """

    web_url = (
        WEB_URL
        or ""
    ).strip()

    if not web_url:
        return None

    return (
        f"{web_url.rstrip('/')}"
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


def create_oauth_session():
    """
    إنشاء جلسة OAuth جديدة.
    """

    state = generate_secure_state()

    # حذف أي جلسة OAuth قديمة
    session.pop(
        "oauth_state",
        None,
    )

    # إنشاء State جديد
    session["oauth_state"] = state

    # جعل الجلسة دائمة
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

    if not isinstance(
        saved_state,
        str,
    ):
        return False

    if not isinstance(
        received_state,
        str,
    ):
        return False

    if len(saved_state) < 32:
        return False

    if len(received_state) < 32:
        return False

    if len(saved_state) != len(
        received_state
    ):
        return False

    return secrets.compare_digest(
        saved_state,
        received_state,
    )


def clear_sensitive_session():
    """
    حذف بيانات OAuth الحساسة.
    """

    sensitive_keys = (
        "discord_user",
        "discord_access_token",
        "discord_token_type",
        "discord_token_expires",
        "oauth_state",
    )

    for key in sensitive_keys:
        session.pop(
            key,
            None,
        )


# =========================================================
# Safe Discord API Request
# =========================================================

def discord_get(
    endpoint,
    access_token,
):
    """
    تنفيذ GET إلى Discord API.
    لا يتم تسجيل Access Token.
    """

    if not access_token:
        return None

    if not isinstance(
        access_token,
        str,
    ):
        return None

    access_token = access_token.strip()

    if not access_token:
        return None

    headers = {
        "Authorization": (
            f"Bearer {access_token}"
        ),
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
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

    # إذا كان المستخدم مسجل دخول بالفعل
    if session.get("discord_user"):
        return redirect(
            url_for(
                "dashboard.dashboard_home"
            )
        )

    # -----------------------------------------------------
    # Environment Validation
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
    # Create OAuth Session
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

    return redirect(
        authorize_url
    )


# =========================================================
# OAuth Callback
# =========================================================

@auth_bp.route("/callback")
def oauth_callback():

    # -----------------------------------------------------
    # Discord Error
    # -----------------------------------------------------

    oauth_error = (
        request.args.get(
            "error",
            "",
        ).strip()
    )

    if oauth_error:
        clear_sensitive_session()

        return redirect(
            url_for("index")
        )

    # -----------------------------------------------------
    # Get Code + State
    # -----------------------------------------------------

    code = (
        request.args.get(
            "code",
            "",
        ).strip()
    )

    state = (
        request.args.get(
            "state",
            "",
        ).strip()
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
            "❌ رمز تسجيل الدخول غير صالح.",
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
        "Content-Type": (
            "application/x-www-form-urlencoded"
        ),
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
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

    # -----------------------------------------------------
    # Token Response
    # -----------------------------------------------------

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

    if not isinstance(
        token_json,
        dict,
    ):
        clear_sensitive_session()

        return (
            "❌ بيانات المصادقة غير صالحة.",
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

    if not isinstance(
        access_token,
        str,
    ):
        clear_sensitive_session()

        return (
            "❌ رمز المصادقة غير صالح.",
            401,
        )

    access_token = access_token.strip()

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

    if not isinstance(
        user,
        dict,
    ):
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

    if not isinstance(
        user_id,
        str,
    ):
        clear_sensitive_session()

        return (
            "❌ معرف Discord غير صالح.",
            401,
        )

    if not user_id.isdigit():
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
        "username": str(username)[:100],
        "global_name": (
            str(global_name)[:100]
            if global_name
            else None
        ),
        "avatar": (
            str(avatar)[:200]
            if avatar
            else None
        ),
    }

    # =====================================================
    # Store OAuth Token
    # =====================================================
    #
    # Flask-Session يخزن الجلسة Server-Side،
    # لذلك الـAccess Token لا يتم وضعه داخل
    # Cookie المتصفح.
    #
    # لا تتم طباعة التوكن أو عرضه للمستخدم.
    # =====================================================

    session["discord_access_token"] = (
        access_token
    )

    if token_type:
        session["discord_token_type"] = (
            str(token_type)[:50]
        )

    if expires_in is not None:
        try:
            expires_value = int(
                expires_in
            )

            if expires_value > 0:
                session[
                    "discord_token_expires"
                ] = expires_value

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

    # حذف كل بيانات الجلسة
    session.clear()

    return redirect(
        url_for("index")
    )
