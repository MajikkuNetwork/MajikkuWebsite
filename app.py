from flask import Flask, redirect, request, render_template, session, url_for, jsonify
import requests
import os
import time
import mysql.connector 
from dotenv import load_dotenv

# Load .env variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(24))

# --- CONFIGURATION VARIABLES ---
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
BOT_TOKEN = os.getenv("BOT_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

# Webhooks
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL") 
APPEALS_WEBHOOK_URL = os.getenv("APPEALS_WEBHOOK_URL") 

REDIRECT_URI = os.getenv("REDIRECT_URI")
API_ENDPOINT = 'https://discord.com/api/v10'

# --- ROLE IDS ---
# Admin Panel Access (Full Control)
ADMIN_ROLE_IDS = [
    "1207778262378487918", # Owner
    "1207778264819572836"  # Administrator
]

# Event & Lore Leads
LEAD_COORDINATOR_ID = "1207778273791184927"
LEAD_STORYTELLER_ID = "1452004814375616765"

# Wiki Roles
LEAD_WIKI_EDITOR_ID = "1454631224592171099" # Can Publish Directly
WIKI_EDITOR_ID = "1454631225309401269"      # Can Submit for Approval (Limited Access)

# --- INITIAL WIKI DATA (Seeding) ---
INITIAL_WIKI_DATA = {
    "getting-started": {
        "title": "Getting Started",
        "category": "General",
        "content": "<h3>Welcome to Majikku!</h3><p>This guide will help you begin your journey...</p>"
    },
    "races": {
        "title": "Races of Majikku",
        "category": "Lore",
        "content": "<h3>The Kweebecs</h3><p>Small, tree-like creatures...</p>"
    },
    "commands": {
        "title": "Server Commands",
        "category": "Gameplay",
        "content": "<p>Here is a list of useful commands:</p>"
    }
}

LEGAL_DATA = {
    "tos": {
        "title": "Terms of Service",
        "content": """
            <p><strong>Last Updated:</strong> 01/04/2026</p>
            <h3>1. Acceptance of Terms</h3>
            <p>By accessing or using Majikku (the "Service"), including our game servers, Discord server, and website, you agree to be bound by these Terms.</p>
            <h3>2. User Conduct</h3>
            <p>You agree to follow all rules outlined in our Rules Document.</p>
        """
    },
    "privacy": {
        "title": "Privacy Policy",
        "content": """
            <p><strong>Last Updated:</strong> 01/04/2026</p>
            <h3>1. Introduction</h3>
            <p>Welcome to Majikku. We are committed to protecting your privacy.</p>
        """
    },
    "refund": {
        "title": "Refund Policy",
        "content": """
            <p><strong>Last Updated:</strong> 01/04/2026</p>
            <h3>1. Digital Goods</h3>
            <p>All sales are final.</p>
        """
    }
}

# --- DATABASE CONNECTION ---
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DB"),
        collation='utf8mb4_general_ci'
    )

# --- DATABASE INIT ---
def init_mysql_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create Tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS announcements (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                content LONGTEXT NOT NULL,
                category VARCHAR(50) DEFAULT 'NEWS',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                author VARCHAR(255) NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wiki (
                slug VARCHAR(255) PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                category VARCHAR(255) NOT NULL,
                content LONGTEXT NOT NULL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wiki_submissions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                slug VARCHAR(255),
                title VARCHAR(255),
                category VARCHAR(255),
                content LONGTEXT,
                author_id VARCHAR(50),
                author_name VARCHAR(100),
                submission_type VARCHAR(10),
                status VARCHAR(20) DEFAULT 'PENDING',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                denial_reason TEXT DEFAULT NULL
            )
        ''')
        
        # Note: Applications DB logic removed as requested, keeping purely for placeholders if needed later
        
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ Database initialized.")
    except mysql.connector.Error as err:
        print(f"❌ Error initializing database: {err}")

def seed_wiki_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM wiki")
        if cursor.fetchone()[0] == 0:
            print("🌱 Seeding Wiki Database...")
            for slug, data in INITIAL_WIKI_DATA.items():
                cursor.execute("INSERT INTO wiki (slug, title, category, content) VALUES (%s, %s, %s, %s)", (slug, data['title'], data['category'], data['content']))
            conn.commit()
        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        print(f"❌ Error seeding database: {err}")

init_mysql_db()
seed_wiki_db()

# --- HELPER FUNCTIONS ---

def get_hytale_profile(discord_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True) 
        cursor.execute("SELECT username, hytale_uuid, time_played FROM players WHERE discord_id = %s LIMIT 1", (discord_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result
    except: return None

# --- STAFF CACHE ---
STAFF_GROUPS = [
    {"name": "Leadership", "roles": [{"id": "1207778262378487918", "title": "Owner"}, {"id": "1207778264819572836", "title": "Administrator"}]},
    {"name": "Team Leads", "roles": [{"id": "1207778273166098502", "title": "Lead Developer"}, {"id": "1207778274642759760", "title": "Lead Builder"}, {"id": "1452499234103234690", "title": "Lead Modeler"}, {"id": "1207778273791184927", "title": "Lead Coordinator"}, {"id": "1392535920665690142", "title": "Lead Artist"}, {"id": "1452004814375616765", "title": "Lead Storyteller"}, {"id": "1392535925606715533", "title": "Lead Tester"}]},
    {"name": "Development Team", "roles": [{"id": "1207778273166098502", "title": "Lead Developer"}, {"id": "1207778264190292052", "title": "Developer"}, {"id": "1392535924918714408", "title": "Jr. Developer"}]},
    {"name": "Build Team", "roles": [{"id": "1207778274642759760", "title": "Lead Builder"}, {"id": "1452499233591791777", "title": "Senior Builder"}, {"id": "1207778275334553640", "title": "Builder"}]},
    {"name": "Modeling Team", "roles": [{"id": "1452499234103234690", "title": "Lead Modeler"}, {"id": "1452499235332292801", "title": "Senior Modeler"}, {"id": "1452499236091592806", "title": "Modeler"}]},
    {"name": "Coordinator Team", "roles": [{"id": "1207778273791184927", "title": "Lead Coordinator"}, {"id": "1392535922331095051", "title": "Event Coordinator"}, {"id": "1392535907965341806", "title": "Social Coordinator"}]},
    {"name": "Story Team", "roles": [{"id": "1452004814375616765", "title": "Lead Storyteller"}, {"id": "1452004927441342616", "title": "Storyteller"}]},
    {"name": "Art Team", "roles": [{"id": "1392535920665690142", "title": "Lead Artist"}, {"id": "1392535921487908945", "title": "Artist"}]},
    {"name": "Wiki Team", "roles": [{"id": "1454631224592171099", "title": "Lead Wiki Editor"}, {"id": "1454631225309401269", "title": "Wiki Editor"}]},
    {"name": "Tester Team", "roles": [{"id": "1392535925606715533", "title": "Lead Tester"}, {"id": "1452499234720055316", "title": "Senior Tester"}, {"id": "1392535923203379260", "title": "Tester"}]},
    {"name": "Moderation Team", "roles": [{"id": "1207778265008439467", "title": "Senior Moderator"}, {"id": "1207778265931055204", "title": "Moderator"}, {"id": "1207778266572918904", "title": "Helper"}]}
]

staff_cache = {"data": None, "timestamp": 0}

def get_staff_data():
    if time.time() - staff_cache["timestamp"] < 300 and staff_cache["data"]: return staff_cache["data"]
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    try:
        response = requests.get(f"{API_ENDPOINT}/guilds/{GUILD_ID}/members?limit=1000", headers=headers)
        if response.status_code != 200: return {}
        members = response.json()
        grouped = {group["name"]: [] for group in STAFF_GROUPS}
        for member in members:
            user = member.get("user", {})
            user_roles = member.get("roles", [])
            avatar = f"https://cdn.discordapp.com/avatars/{user['id']}/{user['avatar']}.png" if user.get("avatar") else "https://cdn.discordapp.com/embed/avatars/0.png"
            for group in STAFF_GROUPS:
                found = None
                for r in group["roles"]:
                    if r["id"] in user_roles: found = r["title"]; break
                if found: grouped[group["name"]].append({"name": member.get("nick") or user.get("username"), "avatar": avatar, "role": found})
        staff_cache["data"] = grouped; staff_cache["timestamp"] = time.time()
        return grouped
    except: return {}

# --- ROLE CHECKS ---
def check_role(user_id, role_ids):
    """Generic helper to check if user has ANY of the role_ids."""
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    try:
        r = requests.get(f"{API_ENDPOINT}/guilds/{GUILD_ID}/members/{user_id}", headers=headers)
        if r.status_code == 200:
            user_roles = r.json().get('roles', [])
            return any(rid in user_roles for rid in role_ids)
    except: pass
    return False

def check_is_admin(uid): return check_role(uid, ADMIN_ROLE_IDS)
def check_is_coordinator(uid): return check_role(uid, [LEAD_COORDINATOR_ID])
def check_is_storyteller(uid): return check_role(uid, [LEAD_STORYTELLER_ID])
def check_is_lead_wiki(uid): return check_role(uid, [LEAD_WIKI_EDITOR_ID])
def check_is_wiki_editor(uid): return check_role(uid, [WIKI_EDITOR_ID])

# --- DISCORD MESSAGING ---
def send_wiki_approval_request(submission_id, title, category, author_name, sub_type):
    """Sends an embed to the Leadership channel when a wiki edit needs approval."""
    channel_id = os.getenv("LEADERSHIP_CHANNEL_ID") 
    if not channel_id: return

    color = 15844367 # Gold/Yellow for Pending
    
    embed = {
        "title": "📜 Wiki Approval Required",
        "description": f"**{author_name}** has submitted a **{sub_type}** page.",
        "color": color,
        "fields": [
            {"name": "Page Title", "value": title, "inline": True},
            {"name": "Category", "value": category, "inline": True},
            {"name": "Content Preview", "value": "Content hidden (too large). Approve to publish.", "inline": False}
        ],
        "footer": {"text": f"Submission ID: {submission_id} | Status: PENDING"}
    }

    components = [{
        "type": 1,
        "components": [
            {
                "type": 2, "style": 3, "label": "Approve & Publish", "emoji": {"name": "✅", "id": None},
                "custom_id": f"wiki_approve_{submission_id}"
            },
            {
                "type": 2, "style": 4, "label": "Deny", "emoji": {"name": "⛔", "id": None},
                "custom_id": f"wiki_deny_{submission_id}"
            }
        ]
    }]

    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {"Authorization": f"Bot {os.getenv('BOT_TOKEN')}", "Content-Type": "application/json"}
    requests.post(url, headers=headers, json={"embeds": [embed], "components": components})

def send_report_bot_message(report_id, report_type, source, reporter_name, target_name, server, reason, evidence, is_anonymous):
    """Sends an embed to Discord when a new report is filed."""
    
    if report_type == 'STAFF':
        channel_id = os.getenv("LEADERSHIP_CHANNEL_ID")
        color = 10181046 # Purple/Dark Red
        title_prefix = "🚨 STAFF REPORT"
    else:
        channel_id = os.getenv("REPORTS_CHANNEL_ID")
        color = 16711680 # Bright Red
        title_prefix = "⚠️ PLAYER REPORT"

    if not channel_id:
        print("ERROR: Channel ID missing in .env")
        return

    fields = [
        {"name": "Reported User", "value": f"**{target_name}**", "inline": True},
        {"name": "Server/Origin", "value": str(server), "inline": True},
    ]

    if is_anonymous:
        fields.append({"name": "Reported By", "value": "||Anonymous User||", "inline": True})
    else:
        fields.append({"name": "Reported By", "value": str(reporter_name), "inline": True})

    fields.append({"name": "Reason / Incident", "value": reason if reason else "No details provided.", "inline": False})
    fields.append({"name": "Evidence", "value": evidence if evidence else "No evidence provided.", "inline": False})

    description_text = ""
    if is_anonymous:
        description_text = "🔴 **THIS USER WOULD LIKE TO REMAIN ANONYMOUS** 🔴\n"

    embed = {
        "title": f"{title_prefix} #{report_id}",
        "description": description_text,
        "color": color,
        "fields": fields,
        "footer": {"text": f"Source: {source} | ID: {report_id} | Status: OPEN"}
    }

    components = [
        {
            "type": 1, 
            "components": [
                {
                    "type": 2, 
                    "style": 1, 
                    "label": "Claim / Investigate",
                    "emoji": {"name": "🔎", "id": None}, 
                    "custom_id": f"claim_report_{report_id}" 
                }
            ]
        }
    ]

    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {"Authorization": f"Bot {os.getenv('BOT_TOKEN')}", "Content-Type": "application/json"}
    requests.post(url, headers=headers, json={"embeds": [embed], "components": components})

# --- ROUTES: AUTH ---
@app.route('/login')
def login():
    return redirect(f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify")

@app.route('/callback')
def callback():
    code = request.args.get('code')
    data = {'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET, 'grant_type': 'authorization_code', 'code': code, 'redirect_uri': REDIRECT_URI}
    try:
        token_resp = requests.post(f'{API_ENDPOINT}/oauth2/token', data=data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
        token_resp.raise_for_status()
        user_resp = requests.get(f'{API_ENDPOINT}/users/@me', headers={'Authorization': f'Bearer {token_resp.json().get("access_token")}'})
        user_data = user_resp.json()
        
        # SAVE USER & ROLES TO SESSION
        # We removed the 'permanent' flag, so session lasts until browser close (default)
        session['user'] = user_data
        
        session['is_admin'] = check_is_admin(user_data['id'])
        session['is_coord'] = check_is_coordinator(user_data['id'])
        session['is_story'] = check_is_storyteller(user_data['id'])
        session['is_wiki_lead'] = check_is_lead_wiki(user_data['id'])
        session['is_wiki_editor'] = check_is_wiki_editor(user_data['id']) # Check permissions for normal wiki editor
        
    except Exception as e:
        return f"Login Error: {e}"
    
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# --- ROUTES: ADMIN DASHBOARD ---
@app.route('/admin')
def admin():
    if 'user' not in session: return redirect(url_for('login'))
    
    # Permission Check
    has_access = (
        session.get('is_admin') or 
        session.get('is_coord') or 
        session.get('is_story') or 
        session.get('is_wiki_lead') or 
        session.get('is_wiki_editor')
    )

    if not has_access:
        return render_template('base.html', content="<h1>Access Denied</h1>")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 1. Fetch Announcements
    posts = []
    if session.get('is_admin'):
        cursor.execute('SELECT * FROM announcements ORDER BY id DESC')
        posts = cursor.fetchall()
    else:
        allowed = []
        if session.get('is_coord'): allowed.append("EVENT")
        if session.get('is_story'): allowed.append("LORE")
        if allowed:
            fmt = ','.join(['%s'] * len(allowed))
            cursor.execute(f"SELECT * FROM announcements WHERE category IN ({fmt}) ORDER BY id DESC", tuple(allowed))
            posts = cursor.fetchall()
    
    # 2. Fetch Wiki Pages
    wiki_pages = []
    can_view_wiki = (
        session.get('is_admin') or 
        session.get('is_story') or 
        session.get('is_wiki_lead') or 
        session.get('is_wiki_editor')
    )

    if can_view_wiki:
        cursor.execute('SELECT * FROM wiki ORDER BY category, title')
        wiki_pages = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('admin.html', user=session.get('user'), announcements=posts, wiki_pages=wiki_pages)

# --- ROUTES: ANNOUNCEMENTS ---
@app.route('/admin/post', methods=['POST'])
def admin_post():
    if 'user' not in session: return "Unauthorized", 403
    title = request.form['title']
    content = request.form['content']
    category = request.form.get('category')
    author = session['user']['username']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO announcements (title, content, category, author) VALUES (%s, %s, %s, %s)', (title, content, category, author))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin'))

@app.route('/admin/edit/<int:id>', methods=['GET', 'POST'])
def admin_edit(id):
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        cursor.execute("UPDATE announcements SET title = %s, content = %s WHERE id = %s", (request.form['title'], request.form['content'], id))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('admin'))
    
    cursor.execute("SELECT * FROM announcements WHERE id = %s", (id,))
    post = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('edit_post.html', post=post, user=session.get('user'))

@app.route('/admin/delete/<int:id>')
def admin_delete(id):
    if 'user' not in session: return "Unauthorized", 403
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM announcements WHERE id = %s', (id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin'))

# --- ROUTES: WIKI EDITING ---
@app.route('/admin/wiki/new', methods=['GET', 'POST'])
def admin_wiki_new():
    if 'user' not in session: return "Unauthorized", 403
    
    has_access = (session.get('is_admin') or session.get('is_story') or session.get('is_wiki_lead') or session.get('is_wiki_editor'))
    if not has_access: return "Unauthorized", 403

    if request.method == 'POST':
        slug = request.form['slug'].lower().replace(" ", "-")
        title = request.form['title']
        category = request.form['category']
        content = request.form['content']
        username = session['user']['username']
        user_id = session['user']['id']
        
        # BYPASS LOGIC: Admin/Story/LeadWiki = Direct Publish. Regular Wiki = Queue.
        is_bypass = (session.get('is_admin') or session.get('is_story') or session.get('is_wiki_lead'))

        conn = get_db_connection()
        cursor = conn.cursor()
        
        if is_bypass:
            cursor.execute("REPLACE INTO wiki (slug, title, category, content) VALUES (%s, %s, %s, %s)", (slug, title, category, content))
            conn.commit()
        else:
            cursor.execute('''INSERT INTO wiki_submissions (slug, title, category, content, author_id, author_name, submission_type) VALUES (%s, %s, %s, %s, %s, %s, 'NEW')''', (slug, title, category, content, user_id, username))
            conn.commit()
            sub_id = cursor.lastrowid
            send_wiki_approval_request(sub_id, title, category, username, "NEW")
        
        cursor.close()
        conn.close()
        return redirect(url_for('admin'))

    return render_template('edit_wiki.html', page=None, user=session.get('user'))

@app.route('/admin/wiki/edit/<slug>', methods=['GET', 'POST'])
def admin_wiki_edit(slug):
    if 'user' not in session: return "Unauthorized", 403
    
    has_access = (session.get('is_admin') or session.get('is_story') or session.get('is_wiki_lead') or session.get('is_wiki_editor'))
    if not has_access: return "Unauthorized", 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if request.method == 'POST':
            title = request.form['title']
            category = request.form['category']
            content = request.form['content']
            username = session['user']['username']
            user_id = session['user']['id']
            
            is_bypass = (session.get('is_admin') or session.get('is_story') or session.get('is_wiki_lead'))

            if is_bypass:
                cursor.execute("UPDATE wiki SET title=%s, category=%s, content=%s WHERE slug=%s", (title, category, content, slug))
                conn.commit()
            else:
                cursor.execute('''INSERT INTO wiki_submissions (slug, title, category, content, author_id, author_name, submission_type) VALUES (%s, %s, %s, %s, %s, %s, 'EDIT')''', (slug, title, category, content, user_id, username))
                conn.commit()
                sub_id = cursor.lastrowid
                send_wiki_approval_request(sub_id, title, category, username, "EDIT")

            cursor.close()
            conn.close()
            return redirect(url_for('admin'))

        cursor.execute("SELECT * FROM wiki WHERE slug = %s", (slug,))
        page = cursor.fetchone()
        cursor.close()
        conn.close()
        return render_template('edit_wiki.html', page=page, user=session.get('user'))
        
    except Exception as e:
        return f"Error: {e}", 500

@app.route('/admin/wiki/delete/<slug>')
def admin_wiki_delete(slug):
    if 'user' not in session: return "Unauthorized", 403
    
    # Wiki Editors CANNOT delete. Only Leads/Admins.
    can_delete = (session.get('is_admin') or session.get('is_story') or session.get('is_wiki_lead'))
    if not can_delete: return "Unauthorized", 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM wiki WHERE slug=%s", (slug,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin'))

# --- PUBLIC ROUTES ---
def build_wiki_tree(pages):
    tree = {}
    for page in pages:
        parts = [p.strip() for p in page['category'].split('>')]
        current_level = tree
        for i, part in enumerate(parts):
            if part not in current_level: current_level[part] = { "subcategories": {}, "pages": [] }
            if i == len(parts) - 1: current_level[part]["pages"].append(page)
            current_level = current_level[part]["subcategories"]
    return tree

@app.route('/wiki')
def wiki_hub():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM wiki ORDER BY category, title")
    rows = cursor.fetchall()
    conn.close()
    return render_template('wiki_hub.html', wiki_tree=build_wiki_tree(rows), user=session.get('user'))

@app.route('/wiki/<slug>')
def wiki_page(slug):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM wiki WHERE slug=%s", (slug,))
    page = cursor.fetchone()
    conn.close()
    if not page: return "Page not found", 404
    return render_template('wiki_entry.html', page=page, user=session.get('user'))

@app.route('/legal/<doc_type>')
def legal_page(doc_type):
    doc = LEGAL_DATA.get(doc_type)
    if not doc: return "Document not found", 404
    return render_template('legal_doc.html', doc=doc, user=session.get('user'))

@app.route('/apply')
def apply():
    if 'user' not in session: return redirect(url_for('login'))
    hytale_data = get_hytale_profile(session['user']['id'])
    return render_template('apply.html', user=session['user'], player=hytale_data)

@app.route('/submit', methods=['POST'])
def submit_application():
    if 'user' not in session: return jsonify({'error': 'Unauthorized'}), 401
    return jsonify({'success': True})

@app.route('/appeal')
def appeal():
    if 'user' not in session: return redirect(url_for('login'))
    hytale_data = get_hytale_profile(session['user']['id'])
    return render_template('appeal.html', user=session['user'], player=hytale_data)

@app.route('/submit-appeal', methods=['POST'])
def submit_appeal():
    return jsonify({'success': True})

# --- REPORTS ---
@app.route('/report', methods=['GET', 'POST'])
def report():
    if 'user' not in session: return redirect(url_for('login'))

    if request.method == 'POST':
        report_type = request.form.get('report_type')
        target_name = request.form.get('target_name')
        server_origin = request.form.get('server_origin')
        reason = request.form.get('reason')
        evidence = request.form.get('evidence')
        is_anon = request.form.get('anonymous') == 'on'
        
        reporter_name = session['user']['username']
        reporter_id = session['user']['id']

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO reports (type, source, reporter_id, reported_name, server_origin, reason, evidence, is_anonymous) VALUES (%s, 'WEBSITE', %s, %s, %s, %s, %s, %s)''', (report_type, reporter_id, target_name, server_origin, reason, evidence, 1 if is_anon else 0))
            conn.commit()
            report_id = cursor.lastrowid
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"DATABASE ERROR: {e}")
            return "Database Error", 500

        send_report_bot_message(report_id, report_type, "WEBSITE", reporter_name, target_name, server_origin, reason, evidence, is_anon)
        return redirect(url_for('report_success', report_id=report_id))
    
    return render_template('report.html', user=session['user'])

@app.route('/report/success/<int:report_id>')
def report_success(report_id):
    if 'user' not in session: return redirect(url_for('login'))
    return render_template('report_success.html', user=session['user'], report_id=report_id)

if __name__ == '__main__':
    app.run(debug=True)