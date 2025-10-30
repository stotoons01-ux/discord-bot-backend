from flask import Flask, jsonify, request
from flask_cors import CORS
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Track startup time for uptime display
start_time = datetime.now()

# Simple in-memory stats (bot can update these later)
bot_stats = {
    "bot_name": "Whiteout Survival",
    "servers": 0,
    "users": 0,
    "uptime": "Starting..."
}

@app.route("/")
def home():
    """Root route to verify backend is live"""
    return jsonify({"status": "online", "message": "Whiteout Survival API running!"})

@app.route("/stats")
def stats():
    """Frontend requests live bot stats"""
    uptime_seconds = (datetime.now() - start_time).total_seconds()
    hours = int(uptime_seconds // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    bot_stats["uptime"] = f"{hours}h {minutes}m"
    return jsonify(bot_stats)

@app.route("/update_stats", methods=["POST"])
def update_stats():
    """Bot updates its stats here"""
    data = request.json or {}
    bot_stats.update(data)
    return jsonify({"success": True, "updated": bot_stats})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
