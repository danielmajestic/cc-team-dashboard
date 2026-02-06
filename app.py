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

    @app.route("/")
    def dashboard():
        return render_template("dashboard.html")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
