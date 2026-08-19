"""Flask app for the Timetable Solver."""
import os
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, render_template

# Load configuration from config/.env
config_path = Path(__file__).parent.parent / "config" / ".env"
load_dotenv(config_path)

app = Flask(
    __name__,
    template_folder=Path(__file__).parent.parent / "frontend",
    static_folder=Path(__file__).parent.parent / "frontend" / "static",
)


@app.route("/")
def index():
    """Serve the main page."""
    return render_template("index.html")


if __name__ == "__main__":
    host = os.getenv("FLASK_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    app.run(host=host, port=port, debug=debug)
