from flask import Flask, jsonify, request
from flask_cors import CORS
import os
from datetime import datetime
import requests
from dotenv import load_dotenv

# Load .env from backend/.env or project root during local development. In production
# (Render) environment variables are provided via the dashboard and this is a no-op.
load_dotenv()

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": [
            "http://localhost:5500",
            "http://127.0.0.1:5500",
            "https://whiteout-survival.vercel.app"
        ],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Authorization", "Content-Type"]
    }
})

# Debug route to check environment variables
@app.route("/debug/env")
def debug_env():
    """Debug route to verify environment variables (redacts sensitive parts)"""
    env_status = {
        'DISCORD_CLIENT_ID': bool(os.environ.get('DISCORD_CLIENT_ID')),
        'DISCORD_CLIENT_SECRET': bool(os.environ.get('DISCORD_CLIENT_SECRET')),
        'DISCORD_BOT_TOKEN': bool(os.environ.get('DISCORD_BOT_TOKEN')),
        'DISCORD_BOT_ID': bool(os.environ.get('DISCORD_BOT_ID'))
    }
    return jsonify({"env_vars_present": env_status})

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

    # Always return JSON
    try:
        data = resp.json()
    except Exception:
        # If Discord returns non-JSON, return error
        return jsonify({'error': 'Discord token endpoint returned invalid response', 'raw': resp.text}), resp.status_code

    # If error from Discord, surface it
    if resp.status_code != 200 or 'error' in data:
        return jsonify({'error': data.get('error_description') or data.get('error') or 'Unknown error', 'raw': data}), resp.status_code

    return jsonify(data), 200


@app.route('/oauth/me')
def oauth_me():
    """Proxy endpoint to fetch /users/@me from Discord using a Bearer token passed in Authorization header.
    This avoids CORS issues when the frontend runs in the browser.
    """
    auth = request.headers.get('Authorization')
    app.logger.info("GET /oauth/me - Received request")
    
    if not auth or not auth.lower().startswith('bearer '):
        app.logger.error("Missing or invalid Authorization header")
        return jsonify({'error': 'missing Authorization: Bearer <token> header'}), 401

    token = auth.split(None, 1)[1]
    try:
        app.logger.info("Calling Discord API /users/@me")
        r = requests.get(
            'https://discord.com/api/v10/users/@me',
            headers={
                'Authorization': f'Bearer {token}',
                'Accept': 'application/json'
            },
            timeout=10
        )
        app.logger.info(f"Discord API response status: {r.status_code}")
        if not r.ok:
            app.logger.error(f"Discord API error: {r.text}")
    except Exception as e:
        app.logger.error(f"Failed to contact Discord API: {str(e)}")
        return jsonify({'error': 'failed to contact Discord API', 'details': str(e)}), 502

    try:
        # Verify we got valid JSON before returning
        response_data = r.json()
        app.logger.info(f"Successfully got user data: {response_data.get('username', 'unknown')}")
        return jsonify(response_data)
    except ValueError as e:
        app.logger.error(f"Invalid JSON response from Discord: {r.text[:200]}")
        return jsonify({'error': 'invalid response from Discord', 'details': r.text[:200]}), 502


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


@app.route('/bot/guilds_status', methods=['POST'])
def bot_guilds_status():
    """Check which of the provided guild IDs the bot is currently a member of.
    Expects JSON: { guild_ids: ["id1","id2", ...] }
    Requires environment variable: DISCORD_BOT_TOKEN and DISCORD_BOT_ID
    Returns: { present: [...], missing: [...], errors: {guild_id: error_message} }
    """
    data = request.json or {}
    guild_ids = data.get('guild_ids') or []
    
    app.logger.info(f"Checking bot presence for guild IDs: {guild_ids}")
    
    bot_token = os.environ.get('DISCORD_BOT_TOKEN')
    bot_id = os.environ.get('DISCORD_BOT_ID')

    if not bot_token:
        app.logger.error("DISCORD_BOT_TOKEN missing from environment")
        return jsonify({'error': 'DISCORD_BOT_TOKEN not configured'}), 500
    if not bot_id:
        app.logger.error("DISCORD_BOT_ID missing from environment")
        return jsonify({'error': 'DISCORD_BOT_ID not configured'}), 500

    if not bot_token or not bot_id:
        return jsonify({'error': 'server missing DISCORD_BOT_TOKEN or DISCORD_BOT_ID env vars'}), 500

    present = []
    missing = []
    errors = {}

    headers = {'Authorization': f'Bot {bot_token}'}
    for gid in guild_ids:
        try:
            url = f'https://discord.com/api/guilds/{gid}/members/{bot_id}'
            app.logger.info(f"Checking guild {gid} with URL: {url}")
            r = requests.get(url, headers=headers, timeout=8)
            app.logger.info(f"Response for guild {gid}: status={r.status_code}")
            
            if r.status_code == 200:
                present.append(gid)
                app.logger.info(f"Bot is present in guild {gid}")
            elif r.status_code == 404:
                missing.append(gid)
                app.logger.info(f"Bot is missing from guild {gid}")
            else:
                error_msg = f'status={r.status_code} body={r.text[:300]}'
                app.logger.error(f"Error checking guild {gid}: {error_msg}")
                errors[gid] = error_msg
        except Exception as e:
            app.logger.error(f"Exception checking guild {gid}: {str(e)}")
            errors[gid] = str(e)
            continue

    return jsonify({'present': present, 'missing': missing, 'errors': errors})

@app.route("/update_stats", methods=["POST"])
def update_stats():
    """Bot updates its stats here"""
    data = request.json or {}
    bot_stats.update(data)
    return jsonify({"success": True, "updated": bot_stats})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
