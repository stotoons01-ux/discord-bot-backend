from flask import Flask, jsonify, request
from flask_cors import CORS
import os
from datetime import datetime
import requests

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


# OAuth helper endpoints (minimal proxy/exchange implementation)
@app.route('/oauth/exchange', methods=['POST'])
def oauth_exchange():
    """Exchange an authorization code for tokens using Discord's OAuth2 token endpoint.
    Expects JSON: { code: string, redirect_uri: string }
    Requires environment variables: DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET
    """
    data = request.json or {}
    code = data.get('code')
    redirect_uri = data.get('redirect_uri')
    client_id = os.environ.get('DISCORD_CLIENT_ID')
    client_secret = os.environ.get('DISCORD_CLIENT_SECRET')

    if not code or not redirect_uri:
        return jsonify({'error': 'missing code or redirect_uri'}), 400
    if not client_id or not client_secret:
        return jsonify({'error': 'server missing OAuth client credentials (set DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET)'}), 500

    token_url = 'https://discord.com/api/oauth2/token'
    payload = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri
    }

    headers = { 'Content-Type': 'application/x-www-form-urlencoded' }
    try:
        resp = requests.post(token_url, data=payload, headers=headers, timeout=10)
    except Exception as e:
        return jsonify({'error': 'failed to contact Discord token endpoint', 'details': str(e)}), 502

    return (resp.content, resp.status_code, dict(resp.headers))


@app.route('/oauth/me')
def oauth_me():
    """Proxy endpoint to fetch /users/@me from Discord using a Bearer token passed in Authorization header.
    This avoids CORS issues when the frontend runs in the browser.
    """
    auth = request.headers.get('Authorization')
    if not auth or not auth.lower().startswith('bearer '):
        return jsonify({'error': 'missing Authorization: Bearer <token> header'}), 401

    token = auth.split(None, 1)[1]
    try:
        r = requests.get('https://discord.com/api/users/@me', headers={'Authorization': f'Bearer {token}'}, timeout=10)
    except Exception as e:
        return jsonify({'error': 'failed to contact Discord API', 'details': str(e)}), 502
    return (r.content, r.status_code, dict(r.headers))


@app.route('/oauth/guilds')
def oauth_guilds():
    """Proxy endpoint to fetch /users/@me/guilds from Discord using a Bearer token passed in Authorization header."""
    auth = request.headers.get('Authorization')
    if not auth or not auth.lower().startswith('bearer '):
        return jsonify({'error': 'missing Authorization: Bearer <token> header'}), 401

    token = auth.split(None, 1)[1]
    try:
        r = requests.get('https://discord.com/api/users/@me/guilds', headers={'Authorization': f'Bearer {token}'}, timeout=10)
    except Exception as e:
        return jsonify({'error': 'failed to contact Discord API', 'details': str(e)}), 502
    return (r.content, r.status_code, dict(r.headers))

@app.route("/update_stats", methods=["POST"])
def update_stats():
    """Bot updates its stats here"""
    data = request.json or {}
    bot_stats.update(data)
    return jsonify({"success": True, "updated": bot_stats})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
