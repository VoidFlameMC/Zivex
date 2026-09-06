from flask import Flask

from config import SESSION_SECRET


# =========================================================
# Zivex Dashboard
# =========================================================

def create_app():
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static"
    )

    # -----------------------------------------------------
    # إعدادات Flask
    # -----------------------------------------------------

    app.config["SECRET_KEY"] = (
        SESSION_SECRET
        or "zivex-development-secret"
    )

    app.config["SESSION_COOKIE_NAME"] = (
        "zivex_session"
    )

    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    # -----------------------------------------------------
    # الصفحة الرئيسية
    # -----------------------------------------------------

    @app.route("/")
    def index():
        return (
            "<h1>Zivex Dashboard</h1>"
            "<p>Dashboard is running.</p>"
        )

    # -----------------------------------------------------
    # Health Check
    # -----------------------------------------------------

    @app.route("/health")
    def health():
        return {
            "status": "ok",
            "service": "Zivex Dashboard"
        }

    return app


# =========================================================
# تشغيل الموقع مباشرة
# =========================================================

app = create_app()


if __name__ == "__main__":
    from config import WEB_HOST, WEB_PORT

    app.run(
        host=WEB_HOST,
        port=WEB_PORT,
        debug=False
    )
