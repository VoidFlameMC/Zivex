import os
from datetime import timedelta

from flask import Flask, redirect, render_template, session, url_for

from config import (
    BOT_NAME,
    SESSION_SECRET,
    WEB_HOST,
    WEB_PORT,
)


# =========================================================
# Zivex Web Application
# =========================================================

def create_app():
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
        static_url_path="/static"
    )

    # =====================================================
    # Flask Configuration
    # =====================================================

    app.config.update(
        SECRET_KEY=(
            SESSION_SECRET
            or os.getenv(
                "FLASK_SECRET_KEY",
                "zivex-development-secret-change-me"
            )
        ),

        SESSION_COOKIE_NAME="zivex_session",

        SESSION_COOKIE_HTTPONLY=True,

        SESSION_COOKIE_SAMESITE="Lax",

        SESSION_COOKIE_SECURE=(
            os.getenv(
                "SESSION_COOKIE_SECURE",
                "false"
            ).lower() == "true"
        ),

        PERMANENT_SESSION_LIFETIME=timedelta(
            days=7
        ),

        MAX_CONTENT_LENGTH=2 * 1024 * 1024,

        JSON_SORT_KEYS=False,
    )

    # =====================================================
    # Context Processor
    # =====================================================

    @app.context_processor
    def inject_global_data():
        return {
            "bot_name": BOT_NAME,
            "logged_in": bool(
                session.get("discord_user")
            )
        }

    # =====================================================
    # Home
    # =====================================================

    @app.route("/")
    def index():
        return render_template(
            "index.html"
        )

    # =====================================================
    # Login
    # =====================================================

    @app.route("/login")
    def login():
        if session.get("discord_user"):
            return redirect(
                url_for("dashboard")
            )

        return render_template(
            "login.html"
        )

    # =====================================================
    # Dashboard
    # =====================================================

    @app.route("/dashboard")
    def dashboard():
        if not session.get("discord_user"):
            return redirect(
                url_for("login")
            )

        return render_template(
            "dashboard.html"
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
            "web": True
        }

    # =====================================================
    # 404
    # =====================================================

    @app.errorhandler(404)
    def not_found(error):
        try:
            return render_template(
                "error.html",
                error_code=404,
                error_title="الصفحة غير موجودة",
                error_message=(
                    "الصفحة التي تبحث عنها غير موجودة "
                    "أو تم نقلها."
                )
            ), 404

        except Exception:
            return (
                "<h1>404</h1>"
                "<p>Page not found.</p>"
            ), 404

    # =====================================================
    # 403
    # =====================================================

    @app.errorhandler(403)
    def forbidden(error):
        try:
            return render_template(
                "error.html",
                error_code=403,
                error_title="غير مسموح",
                error_message=(
                    "ما عندك صلاحية للوصول إلى هذه الصفحة."
                )
            ), 403

        except Exception:
            return (
                "<h1>403</h1>"
                "<p>Forbidden.</p>"
            ), 403

    # =====================================================
    # 500
    # =====================================================

    @app.errorhandler(500)
    def internal_error(error):
        try:
            return render_template(
                "error.html",
                error_code=500,
                error_title="حدث خطأ",
                error_message=(
                    "حدث خطأ غير متوقع في الموقع. "
                    "حاول مرة ثانية."
                )
            ), 500

        except Exception:
            return (
                "<h1>500</h1>"
                "<p>Internal server error.</p>"
            ), 500

    return app


# =========================================================
# Flask App
# =========================================================

app = create_app()


# =========================================================
# تشغيل الموقع مباشرة
# =========================================================

if __name__ == "__main__":
    app.run(
        host=WEB_HOST,
        port=WEB_PORT,
        debug=False
    )
