from flask import Flask, redirect, request, render_template, session, url_for, jsonify
import requests
import os
import time
import sqlite3
import mysql.connector 
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(24))

# --- CONFIGURATION ---
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
BOT_TOKEN = os.getenv("BOT_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

# Webhooks
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL") 
APPEALS_WEBHOOK_URL = os.getenv("APPEALS_WEBHOOK_URL") 

REDIRECT_URI = os.getenv("REDIRECT_URI")
API_ENDPOINT = 'https://discord.com/api/v10'

# IDs allowed to access Admin Panel
ADMIN_ROLE_IDS = [
    "1207778262378487918", # Owner
    "1207778264819572836"  # Administrator
]

# ID allowed to post Events only
LEAD_COORDINATOR_ID = "1207778273791184927"

# ID allowed to post Lore only (NEW)
LEAD_STORYTELLER_ID = "1452004814375616765"

# --- DATABASE SETUP (WEBSITE: SQLite) ---
def init_sqlite_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT DEFAULT 'NEWS',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            author TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_sqlite_db()

# --- HELPER: GET HYTALE INFO (GAME DB: MySQL) ---
def get_hytale_profile(discord_id):
    """Fetches player data from the MySQL game database using Discord ID."""
    try:
        conn = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST"),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
            database=os.getenv("MYSQL_DB")
        )
        cursor = conn.cursor(dictionary=True) 
        query = "SELECT username, hytale_uuid, time_played FROM players WHERE discord_id = %s LIMIT 1"
        cursor.execute(query, (discord_id,))
        result = cursor.fetchone()
        conn.close()
        return result
    except Exception as e:
        print(f"MySQL Connection Error: {e}")
        return None

# --- STAFF PAGE CONFIGURATION (RESTORED) ---
STAFF_GROUPS = [
    {"name": "Leadership", "roles": [{"id": "1207778262378487918", "title": "Owner"}, {"id": "1207778264819572836", "title": "Administrator"}]},
    {"name": "Team Leads", "roles": [{"id": "1207778273166098502", "title": "Lead Developer"}, {"id": "1207778274642759760", "title": "Lead Builder"}, {"id": "1452499234103234690", "title": "Lead Modeler"}, {"id": "1207778273791184927", "title": "Lead Coordinator"}, {"id": "1392535920665690142", "title": "Lead Artist"}, {"id": "1452004814375616765", "title": "Lead Storyteller"}, {"id": "1392535925606715533", "title": "Lead Tester"}]},
    {"name": "Development Team", "roles": [{"id": "1207778273166098502", "title": "Lead Developer"}, {"id": "1207778264190292052", "title": "Developer"}, {"id": "1392535924918714408", "title": "Jr. Developer"}]},
    {"name": "Build Team", "roles": [{"id": "1207778274642759760", "title": "Lead Builder"}, {"id": "1452499233591791777", "title": "Senior Builder"}, {"id": "1207778275334553640", "title": "Builder"}]},
    {"name": "Modeling Team", "roles": [{"id": "1452499234103234690", "title": "Lead Modeler"}, {"id": "1452499235332292801", "title": "Senior Modeler"}, {"id": "1452499236091592806", "title": "Modeler"}]},
    {"name": "Coordinator Team", "roles": [{"id": "1207778273791184927", "title": "Lead Coordinator"}, {"id": "1392535922331095051", "title": "Event Coordinator"}, {"id": "1392535907965341806", "title": "Social Coordinator"}]},
    {"name": "Art & Story", "roles": [{"id": "1392535920665690142", "title": "Lead Artist"}, {"id": "1452004814375616765", "title": "Lead Storyteller"}, {"id": "1392535921487908945", "title": "Artist"}, {"id": "1452004927441342616", "title": "Storyteller"}]},
    {"name": "Quality Assurance", "roles": [{"id": "1392535925606715533", "title": "Lead Tester"}, {"id": "1452499234720055316", "title": "Senior Tester"}, {"id": "1392535923203379260", "title": "Tester"}]},
    {"name": "Moderation Team", "roles": [{"id": "1207778265008439467", "title": "Senior Moderator"}, {"id": "1207778265931055204", "title": "Moderator"}, {"id": "1207778266572918904", "title": "Helper"}]}
]

staff_cache = {"data": None, "timestamp": 0}

# --- HELPERS ---
def get_staff_data():
    """Restored Logic: Matches roles to specific titles under headers."""
    if time.time() - staff_cache["timestamp"] < 300 and staff_cache["data"]:
        return staff_cache["data"]

    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    try:
        response = requests.get(f"{API_ENDPOINT}/guilds/{GUILD_ID}/members?limit=1000", headers=headers)
        
        if response.status_code != 200:
            print(f"Error fetching staff: {response.text}")
            return {}

        members = response.json()
        grouped_staff = {group["name"]: [] for group in STAFF_GROUPS}
        
        for member in members:
            user = member.get("user", {})
            user_roles = member.get("roles", [])
            
            avatar_url = "https://cdn.discordapp.com/embed/avatars/0.png"
            if user.get("avatar"):
                avatar_url = f"https://cdn.discordapp.com/avatars/{user['id']}/{user['avatar']}.png"

            for group in STAFF_GROUPS:
                found_title = None
                for role_def in group["roles"]:
                    if role_def["id"] in user_roles:
                        found_title = role_def["title"]
                        break # Found highest priority role for this group
                
                if found_title:
                    staff_member = {
                        "name": member.get("nick") or user.get("username"),
                        "avatar": avatar_url,
                        "role": found_title
                    }
                    grouped_staff[group["name"]].append(staff_member)

        staff_cache["data"] = grouped_staff
        staff_cache["timestamp"] = time.time()
        return grouped_staff
    except Exception as e:
        print(f"Exception in get_staff_data: {e}")
        return {}

def check_is_admin(user_id):
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    try:
        response = requests.get(f"{API_ENDPOINT}/guilds/{GUILD_ID}/members/{user_id}", headers=headers)
        if response.status_code == 200:
            member_data = response.json()
            roles = member_data.get('roles', [])
            for role_id in roles:
                if role_id in ADMIN_ROLE_IDS:
                    return True
    except:
        pass
    return False

def check_is_coordinator(user_id):
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    try:
        response = requests.get(f"{API_ENDPOINT}/guilds/{GUILD_ID}/members/{user_id}", headers=headers)
        if response.status_code == 200:
            member_data = response.json()
            roles = member_data.get('roles', [])
            if LEAD_COORDINATOR_ID in roles:
                return True
    except:
        pass
    return False

# NEW: Check for Storyteller Lead
def check_is_storyteller(user_id):
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    try:
        response = requests.get(f"{API_ENDPOINT}/guilds/{GUILD_ID}/members/{user_id}", headers=headers)
        if response.status_code == 200:
            member_data = response.json()
            roles = member_data.get('roles', [])
            if LEAD_STORYTELLER_ID in roles:
                return True
    except:
        pass
    return False

# --- ROUTES ---

@app.route('/')
def home():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    posts = conn.execute("SELECT * FROM announcements WHERE category='NEWS' ORDER BY id DESC").fetchall()
    conn.close()
    return render_template('home.html', user=session.get('user'), announcements=posts)

@app.route('/events')
def events():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    posts = conn.execute("SELECT * FROM announcements WHERE category='EVENT' ORDER BY id DESC").fetchall()
    conn.close()
    return render_template('events.html', user=session.get('user'), announcements=posts)

# NEW: Separate Lore Route
@app.route('/lore')
def lore():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    posts = conn.execute("SELECT * FROM announcements WHERE category='LORE' ORDER BY id DESC").fetchall()
    conn.close()
    return render_template('lore.html', user=session.get('user'), announcements=posts)

# NEW: Separate Rules Route
@app.route('/rules')
def rules():
    return render_template('rules.html', user=session.get('user'))

@app.route('/socials')
def socials():
    return render_template('socials.html', user=session.get('user'))

@app.route('/info')
def info():
    return render_template('info.html', user=session.get('user'))

@app.route('/staff')
def staff():
    grouped_staff = get_staff_data()
    return render_template('staff.html', staff_groups=grouped_staff, group_order=STAFF_GROUPS, user=session.get('user'))

# --- AUTH ROUTES ---
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
        'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET,
        'grant_type': 'authorization_code', 'code': code, 'redirect_uri': REDIRECT_URI
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    
    try:
        token_resp = requests.post(f'{API_ENDPOINT}/oauth2/token', data=data, headers=headers)
        token_resp.raise_for_status()
        access_token = token_resp.json().get('access_token')

        user_resp = requests.get(f'{API_ENDPOINT}/users/@me', headers={'Authorization': f'Bearer {access_token}'})
        user_data = user_resp.json()
        
        # Check permissions
        is_admin = check_is_admin(user_data['id'])
        is_coord = check_is_coordinator(user_data['id'])
        is_story = check_is_storyteller(user_data['id']) 
        
        session['user'] = user_data
        session['is_admin'] = is_admin
        session['is_coord'] = is_coord
        session['is_story'] = is_story
        
    except Exception as e:
        return f"Login Error: {e}"
    
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# --- ADMIN ROUTES (RICH TEXT SUPPORT) ---
@app.route('/admin')
def admin():
    if 'user' not in session: return redirect(url_for('login'))
    
    # Permission Gate (Allows Admin, Coord, OR Storyteller)
    if not (session.get('is_admin') or session.get('is_coord') or session.get('is_story')):
        return render_template('base.html', content="<h1>Access Denied</h1>")

    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    
    # Filter posts based on permission
    if session.get('is_admin'):
        posts = conn.execute('SELECT * FROM announcements ORDER BY id DESC').fetchall()
    else:
        # Build allowed categories list
        allowed = []
        if session.get('is_coord'): allowed.append("'EVENT'")
        if session.get('is_story'): allowed.append("'LORE'")
        
        if allowed:
            query = f"SELECT * FROM announcements WHERE category IN ({','.join(allowed)}) ORDER BY id DESC"
            posts = conn.execute(query).fetchall()
        else:
            posts = []

    conn.close()
    return render_template('admin.html', user=session.get('user'), announcements=posts)

@app.route('/admin/post', methods=['POST'])
def admin_post():
    if 'user' not in session: return "Unauthorized", 403
    
    title = request.form['title']
    content = request.form['content'] # HTML from Summernote
    category = request.form.get('category')
    author = session['user']['username']

    # Strict Permission Checks
    if category == 'NEWS' and not session.get('is_admin'): return "Unauthorized", 403
    if category == 'EVENT' and not (session.get('is_admin') or session.get('is_coord')): return "Unauthorized", 403
    if category == 'LORE' and not (session.get('is_admin') or session.get('is_story')): return "Unauthorized", 403

    conn = sqlite3.connect('database.db')
    conn.execute('INSERT INTO announcements (title, content, category, author) VALUES (?, ?, ?, ?)',
                 (title, content, category, author))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/admin/edit/<int:id>', methods=['GET', 'POST'])
def admin_edit(id):
    if 'user' not in session: return redirect(url_for('login'))

    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        conn.execute("UPDATE announcements SET title = ?, content = ? WHERE id = ?", (title, content, id))
        conn.commit()
        conn.close()
        return redirect(url_for('admin'))

    # GET request - show the form
    post = conn.execute("SELECT * FROM announcements WHERE id = ?", (id,)).fetchone()
    
    if not post:
        conn.close()
        return "Post not found", 404
        
    # Permission Check
    cat = post['category']
    allowed = False
    if session.get('is_admin'): allowed = True
    elif cat == 'EVENT' and session.get('is_coord'): allowed = True
    elif cat == 'LORE' and session.get('is_story'): allowed = True

    if not allowed:
        conn.close()
        return "Unauthorized to edit this post", 403

    conn.close()
    return render_template('edit_post.html', post=post, user=session.get('user'))

@app.route('/admin/delete/<int:id>')
def admin_delete(id):
    if 'user' not in session: return "Unauthorized", 403
    
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT category FROM announcements WHERE id = ?", (id,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return redirect(url_for('admin'))
    
    cat = row[0]
    allowed = False
    if session.get('is_admin'): allowed = True
    elif cat == 'EVENT' and session.get('is_coord'): allowed = True
    elif cat == 'LORE' and session.get('is_story'): allowed = True

    if allowed:
        conn.execute('DELETE FROM announcements WHERE id = ?', (id,))
        conn.commit()
    
    conn.close()
    return redirect(url_for('admin'))

# --- APPLICATION ROUTES (Webhook Enabled) ---
@app.route('/apply')
def apply():
    if 'user' not in session: return redirect(url_for('login'))
    
    # 1. Fetch Hytale Profile using MySQL
    hytale_data = get_hytale_profile(session['user']['id'])
    
    # 2. Pass 'player' data to template
    return render_template('apply.html', user=session['user'], player=hytale_data)

@app.route('/submit', methods=['POST'])
def submit_application():
    if 'user' not in session: return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    user = session['user']
    team_name = data.get('team', 'General')
    
    avatar_url = None
    if user.get("avatar"):
        avatar_url = f"https://cdn.discordapp.com/avatars/{user['id']}/{user['avatar']}.png"

    embed = {
        "title": f"New Application: {team_name}",
        "color": 10182117, # Green-ish
        "fields": [
            {"name": "Discord User", "value": f"<@{user['id']}> ({user['username']})", "inline": False},
            {"name": "Hytale Name", "value": data.get('hytale_name', 'N/A'), "inline": True},
            {"name": "Age", "value": data.get('age', 'N/A'), "inline": True},
            {"name": "Timezone", "value": data.get('timezone', 'N/A'), "inline": True},
            {"name": "Pronouns", "value": data.get('pronouns', 'N/A'), "inline": True},
        ],
        "footer": {"text": "Majikku Network Application System"}
    }
    if avatar_url: embed["thumbnail"] = {"url": avatar_url}

    for question, answer in data.get('answers', {}).items():
        if answer:
            safe_answer = (answer[:1000] + '...') if len(answer) > 1000 else answer
            embed["fields"].append({"name": question, "value": safe_answer, "inline": False})
#
    payload = {
        "thread_name": f"APP - {team_name} - {data.get('hytale_name', user['username'])}",
        "embeds": [embed]
    }
    
    # Send to Staff Webhook
    try:
        if DISCORD_WEBHOOK_URL:
            requests.post(DISCORD_WEBHOOK_URL, json=payload)
        return jsonify({'success': True})
    except Exception as e:
        print(f"Webhook Error: {e}")
        return jsonify({'error': 'Failed to send'}), 500

# --- APPEAL ROUTES (Webhook Enabled) ---
@app.route('/appeal')
def appeal():
    if 'user' not in session: return redirect(url_for('login'))
    
    # 1. Fetch Hytale Profile using MySQL
    hytale_data = get_hytale_profile(session['user']['id'])
    
    return render_template('appeal.html', user=session['user'], player=hytale_data)

@app.route('/submit-appeal', methods=['POST'])
def submit_appeal():
    if 'user' not in session: return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    user = session['user']
    
    avatar_url = None
    if user.get("avatar"):
        avatar_url = f"https://cdn.discordapp.com/avatars/{user['id']}/{user['avatar']}.png"

    # RED Embed for Appeals (Color: 16711680)
    embed = {
        "title": "🚨 New Punishment Appeal",
        "color": 16711680,
        "fields": [
            {"name": "Discord User", "value": f"<@{user['id']}> ({user['username']})", "inline": True},
            {"name": "Hytale IGN", "value": data.get('hytale_username', 'N/A'), "inline": True},
            {"name": "Punishment Type", "value": data.get('type', 'N/A'), "inline": True},
            {"name": "Platform", "value": data.get('platform', 'N/A'), "inline": True},
            {"name": "Punishment ID", "value": data.get('punishment_id', 'N/A'), "inline": True},
            {"name": "Given Reason", "value": data.get('ban_reason', 'N/A'), "inline": False},
            {"name": "Appeal Statement", "value": data.get('appeal_text', 'N/A')[:1024], "inline": False}
        ],
        "footer": {"text": "Majikku Network Appeal System"},
        "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    }
    
    if avatar_url: embed["thumbnail"] = {"url": avatar_url}

    payload = {
        "thread_name": f"APPEAL - {data.get('hytale_username', user['username'])}",
        "embeds": [embed]
    }
    
    try:
        # Send to APPEAL Webhook
        if APPEALS_WEBHOOK_URL:
            requests.post(APPEALS_WEBHOOK_URL, json=payload)
        return jsonify({'success': True})
    except Exception as e:
        print(f"Error sending appeal webhook: {e}")
        return jsonify({'error': 'Failed to send to Discord'}), 500

if __name__ == '__main__':
    app.run(debug=True)