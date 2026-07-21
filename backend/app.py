"""
Flask Application Factory

Entry point for the AI Business Intelligence Agent backend.
Registers all blueprints, configures CORS, and sets up error handlers.
"""

import os
import logging
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Load environment variables before anything else
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def create_app():
    """Application factory."""
    app = Flask(__name__)
    
    # CORS — allow frontend dev server and production origins
    CORS(app, resources={
        r"/api/*": {
            "origins": [
                "http://localhost:5173",   # Vite dev server
                "http://localhost:3000",   # Fallback
                os.getenv("FRONTEND_URL", ""),
            ],
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": ["Content-Type"],
        }
    })

    # -----------------------------------------------------------------------
    # Health Check
    # -----------------------------------------------------------------------
    @app.route("/api/health", methods=["GET"])
    def health():
        """Health check endpoint."""
        return jsonify({
            "status": "healthy",
            "service": "monday-bi-agent",
            "version": "1.0.0",
        })

    # -----------------------------------------------------------------------
    # Register Blueprints
    # -----------------------------------------------------------------------
    from routes.monday import monday_bp
    app.register_blueprint(monday_bp, url_prefix="/api/monday")

    from routes.chat import chat_bp
    app.register_blueprint(chat_bp, url_prefix="/api")

    # -----------------------------------------------------------------------
    # Error Handlers
    # -----------------------------------------------------------------------
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad request", "detail": str(e)}), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def server_error(e):
        logger.error(f"Internal server error: {e}")
        return jsonify({"error": "Internal server error", "detail": str(e)}), 500

    @app.errorhandler(Exception)
    def unhandled_exception(e):
        logger.exception(f"Unhandled exception: {e}")
        return jsonify({"error": "An unexpected error occurred", "detail": str(e)}), 500

    logger.info("Monday.com BI Agent backend initialized")
    return app


# Create the global app instance for Gunicorn
app = create_app()

# ---------------------------------------------------------------------------
# Direct execution (dev mode)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 5000)),
        debug=os.getenv("FLASK_DEBUG", "1") == "1",
    )
