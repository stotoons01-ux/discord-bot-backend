from flask import Flask, jsonify, request
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)  # allow frontend to connect

# Temporary storage for bot stats
bot_stats = {
    "servers": 0,
    "users": 0,
    "uptime": "Unknown"
}

@app.route("/")
def home():
    return jsonify({"message": "Bot API is running!"})

@app.route("/stats")
def stats():
    """Frontend calls this to get bot stats."""
    return jsonify(bot_stats)

@app.route("/update_stats", methods=["POST"])
def update_stats():
    """Bot sends its current stats here."""
    data = request.json or {}
    bot_stats.update(data)
    return jsonify({"success": True, "updated": bot_stats})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
