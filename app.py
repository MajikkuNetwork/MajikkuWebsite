from flask import Flask, redirect, request, render_template, session, url_for, jsonify
import requests
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

# --- CONFIGURATION ---
# Replace these with your actual details from the Discord Developer Portal
CLIENT_ID = "REPLACE ME"
CLIENT_SECRET = "REPLACE ME"

# Localhost URL for testing (Make sure this is in your Discord Dev Portal Redirects)
REDIRECT_URI = "http://127.0.0.1:5000/callback"

API_ENDPOINT = 'https://discord.com/api/v10'

# Your Discord Webhook URL (Used for both Apps and Appeals)
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1455816015656128575/rXXJqbAHgNMJRQFPpnBtLFmHQBud8zPX2HN1gKghES14HhPBqwZVLt2H2g5aoAn5Xx76"

# --- PUBLIC ROUTES ---

@app.route('/')
def home():
    # Renders the Home page with announcements
    return render_template('home.html', user=session.get('user'))

@app.route('/info')
def info():
    # Renders Lore & Rules
    return render_template('info.html', user=session.get('user'))

@app.route('/staff')
def staff():
    # Renders Staff list
    return render_template('staff.html', user=session.get('user'))

# --- AUTHENTICATION ROUTES ---

@app.route('/login')
def login():
    discord_auth_url = (
        f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify"
    )
    return redirect(discord_auth_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    
    # Exchange code for token
    token_response = requests.post(f'{API_ENDPOINT}/oauth2/token', data=data, headers=headers)
    token_json = token_response.json()
    access_token = token_json.get('access_token')

    # Get User Info
    user_response = requests.get(
        f'{API_ENDPOINT}/users/@me',
        headers={'Authorization': f'Bearer {access_token}'}
    )
    user_data = user_response.json()
    
    # Save to session
    session['user'] = user_data
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# --- PROTECTED ROUTES (Require Login) ---

@app.route('/apply')
def apply():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('apply.html', user=session['user'])

@app.route('/appeal')
def appeal():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('appeal.html', user=session['user'])

# --- SUBMISSION LOGIC ---

@app.route('/submit', methods=['POST'])
def submit_application():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    user = session['user']
    team_name = data.get('team', 'General')
    
    # --- NEW: GET PROFILE PICTURE URL ---
    user_id = user['id']
    avatar_hash = user.get('avatar')
    
    # Construct the URL. If they have no avatar, we skip the thumbnail.
    avatar_url = None
    if avatar_hash:
        avatar_url = f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.png"

    # --- BUILD EMBED ---
    embed = {
        "title": f"New Application: {team_name}",
        "color": 10182117, # Purple
        "fields": [
            {"name": "Discord User", "value": f"<@{user_id}> ({user['username']})", "inline": False},
            {"name": "Hytale Name", "value": data.get('hytale_name', 'N/A'), "inline": True},
            {"name": "Age", "value": data.get('age', 'N/A'), "inline": True},
            {"name": "Timezone", "value": data.get('timezone', 'N/A'), "inline": True},
            {"name": "Availability", "value": data.get('availability', 'N/A'), "inline": False},
        ],
        "footer": {"text": "Majikku Network Application System"}
    }

    # --- NEW: ADD THUMBNAIL TO EMBED ---
    if avatar_url:
        embed["thumbnail"] = {"url": avatar_url}

    # Add questions and answers
    for question, answer in data.get('answers', {}).items():
        if answer:
            # Truncate if too long
            safe_answer = (answer[:1000] + '...') if len(answer) > 1000 else answer
            embed["fields"].append({"name": question, "value": safe_answer, "inline": False})

    # Payload for Forum Channel
    payload = {
        "thread_name": f"APP - {team_name} - {data.get('hytale_name', user['username'])}",
        "embeds": [embed]
    }

    requests.post(DISCORD_WEBHOOK_URL, json=payload)
    return jsonify({'success': True})

@app.route('/submit-appeal', methods=['POST'])
def submit_appeal():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    user = session['user']
    
    # Build Embed for Appeal
    embed = {
        "title": "New Ban Appeal",
        "color": 15158332, # Red Color
        "description": "A user has submitted a ban appeal.",
        "fields": [
            {"name": "Discord User", "value": f"{user['username']} ({user['id']})", "inline": False},
            {"name": "Ban Reason (User Stated)", "value": data.get('reason', 'N/A'), "inline": False},
            {"name": "Appeal / Apology", "value": data.get('apology', 'N/A'), "inline": False}
        ],
        "footer": {"text": "Majikku Network Appeal System"}
    }

    # Payload for Forum Channel
    payload = {
        "thread_name": f"APPEAL - {user['username']}",
        "embeds": [embed]
    }

    requests.post(DISCORD_WEBHOOK_URL, json=payload)
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True)