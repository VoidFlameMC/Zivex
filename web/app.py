import os

from flask import (
    Flask,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from config import (
    BOT_NAME,
    SESSION_SECRET,
    WEB_HOST,
    WEB_PORT,
)

from web.auth import auth_bp
from web.dashboard import dashboard_bp


# =========================================================
# Zivex Secure Web Application
# =========================================================

def create_app(bot=None):

    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
        static_url_path="/static",
    )

    # =====================================================
    # Security Configuration
    # =====================================================

    secret_key = (
        SESSION_SECRET
        or os.getenv("FLASK_SECRET_KEY", "")
    ).strip()

    if not secret_key:
        raise RuntimeError(
            "❌ SESSION_SECRET غير موجود في Environment Variables."
        )

    if len(secret_key) < 32:
        raise RuntimeError(
            "❌ SESSION_SECRET ضعيف. "
            "استخدم Secret عشوائي بطول 32 حرفًا أو أكثر."
        )

    # =====================================================
    # Flask Configuration
    # =====================================================

    app.config.update(
        SECRET_KEY=secret_key,

        SESSION_COOKIE_NAME="zivex_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",

        SESSION_COOKIE_SECURE=(
            os.getenv(
                "SESSION_COOKIE_SECURE",
                "false",
            ).lower()
            == "true"
        ),

        PERMANENT_SESSION_LIFETIME=60 * 60 * 24,

        MAX_CONTENT_LENGTH=2 * 1024 * 1024,

        DEBUG=False,
        TESTING=False,

        ZIVEX_BOT=bot,
    )

    # =====================================================
    # Security Headers
    # =====================================================

    @app.after_request
    def security_headers(response):

        response.headers["X-Content-Type-Options"] = "nosniff"

        response.headers["X-Frame-Options"] = "DENY"

        response.headers["Referrer-Policy"] = (
            "strict-origin-when-cross-origin"
        )

        response.headers["Permissions-Policy"] = (
            "camera=(), "
            "microphone=(), "
            "geolocation=(), "
            "payment=()"
        )

        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none'; "
            "object-src 'none'; "
            "img-src 'self' "
            "https://cdn.discordapp.com "
            "https://media.discordapp.net "
            "https://images-ext-1.discordapp.net "
            "data:; "
            "style-src 'self'; "
            "script-src 'self'; "
            "connect-src 'self';"
        )

        # HSTS عند تشغيل HTTPS
        if request.is_secure:
            response.headers[
                "Strict-Transport-Security"
            ] = (
                "max-age=31536000; "
                "includeSubDomains"
            )

        return response

    # =====================================================
    # Global Template Data
    # =====================================================

    @app.context_processor
    def global_template_data():

        return {
            "bot_name": BOT_NAME,

            "logged_in": bool(
                session.get("discord_user")
            ),

            "discord_user": session.get(
                "discord_user"
            ),
        }

    # =====================================================
    # Home
    # =====================================================

    @app.route("/")
    def index():

        if session.get("discord_user"):
            return redirect(
                url_for(
                    "dashboard.dashboard_home"
                )
            )

        try:
            return render_template(
                "index.html"
            )

        except Exception:
            return (
                "<h1>Zivex</h1>"
                "<p>Dashboard is starting...</p>"
            )

    # =====================================================
    # Login
    # =====================================================

    @app.route("/login")
    def login():

        if session.get("discord_user"):
            return redirect(
                url_for(
                    "dashboard.dashboard_home"
                )
            )

        try:
            return render_template(
                "login.html"
            )

        except Exception:
            return redirect(
                url_for(
                    "auth.oauth_login"
                )
            )

    # =====================================================
    # Logout
    # =====================================================

    @app.route("/logout")
    def logout():

        session.clear()

        return redirect(
            url_for("index")
        )

    # =====================================================
    # Health Check
    # =====================================================

    @app.route("/health")
    def health():

        return {
            "status": "ok",
            "service": BOT_NAME,
        }

    # =====================================================
    # Register Authentication
    # =====================================================

    app.register_blueprint(
        auth_bp
    )

    # =====================================================
    # Register Dashboard
    # =====================================================

    app.register_blueprint(
        dashboard_bp
    )

    # =====================================================
    # Error Handlers
    # =====================================================

    @app.errorhandler(400)
    def bad_request(error):

        return render_error(
            "400",
            "طلب غير صالح",
            "الطلب الذي أرسلته غير صالح.",
        )

    @app.errorhandler(401)
    def unauthorized(error):

        session.clear()

        return render_error(
            "401",
            "تسجيل الدخول مطلوب",
            "يجب تسجيل الدخول أولًا.",
        )

    @app.errorhandler(403)
    def forbidden(error):

        return render_error(
            "403",
            "غير مصرح",
            "ليس لديك صلاحية للوصول إلى هذا المحتوى.",
        )

    @app.errorhandler(404)
    def not_found(error):

        return render_error(
            "404",
            "الصفحة غير موجودة",
            "الصفحة التي تبحث عنها غير موجودة.",
        )

    @app.errorhandler(405)
    def method_not_allowed(error):

        return render_error(
            "405",
            "طريقة غير مسموحة",
            "طريقة الطلب المستخدمة غير مسموحة.",
        )

    @app.errorhandler(413)
    def request_too_large(error):

        return render_error(
            "413",
            "الطلب كبير جدًا",
            "حجم الطلب أكبر من الحد المسموح.",
        )

    @app.errorhandler(429)
    def too_many_requests(error):

        return render_error(
            "429",
            "طلبات كثيرة",
            "تم إرسال عدد كبير من الطلبات. حاول لاحقًا.",
        )

    @app.errorhandler(500)
    def internal_error(error):

        return render_error(
            "500",
            "حدث خطأ",
            "حدث خطأ غير متوقع. حاول مرة أخرى.",
        )

    return app


# =========================================================
# Error Rendering
# =========================================================

def render_error(
    code,
    title,
    message,
):

    try:
        return (
            render_template(
                "error.html",
                error_code=code,
                error_title=title,
                error_message=message,
            ),
            int(code),
        )

    except Exception:
        return (
            f"<h1>{code}</h1>"
            f"<h2>{title}</h2>"
            f"<p>{message}</p>",
            int(code),
        )


# =========================================================
# Flask Application
# =========================================================

app = create_app()


# =========================================================
# Direct Run
# =========================================================

if __name__ == "__main__":

    railway_port = os.getenv("PORT")

    try:
        port = int(
            railway_port
            if railway_port
            else WEB_PORT
        )
    except (TypeError, ValueError):
        port = int(WEB_PORT)

    app.run(
        host=WEB_HOST,
        port=port,
        debug=False,
    )
