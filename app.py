import os
from flask import Flask, render_template
from config import Config, TestConfig


def create_app(testing=False):
    app = Flask(__name__)

    if testing:
        app.config.from_object(TestConfig)
    else:
        app.config.from_object(Config)

    # Ensure instance folder exists
    os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)

    from models import init_db, get_db_connection

    # Initialize database
    if not testing:
        db_conn = get_db_connection(app.config["DATABASE_PATH"])
        init_db(db_conn)
        db_conn.close()

    @app.route("/")
    def dashboard():
        return render_template("dashboard.html")

    @app.route("/agents")
    def agents():
        return render_template("agents.html")

    @app.route("/issues")
    def issues():
        return render_template("issues.html")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
