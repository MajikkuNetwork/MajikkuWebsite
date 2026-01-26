from flask import Flask, redirect, request, render_template, session, url_for, jsonify, send_from_directory
import requests
import os
import time
import mysql.connector 
from dotenv import load_dotenv

# Load sensitive info from .env file
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

# --- ROLE IDS (PERMISSIONS) ---
# 1. ADMINS: Can do everything
ADMIN_ROLE_IDS = [
    "1207778262378487918", # Owner
    "1207778264819572836"  # Administrator
]

# 2. COORDINATORS: Can post Events
LEAD_COORDINATOR_ID = "1207778273791184927"

# 3. STORYTELLERS: Can edit Wiki (Bypass Approval)
LEAD_STORYTELLER_ID = "1452004814375616765"

# 4. WIKI TEAM
LEAD_WIKI_EDITOR_ID = "1454631224592171099" # Lead: Can Publish Directly
WIKI_EDITOR_ID = "1454631225309401269"      # Editor: Must Submit for Approval

# --- INITIAL DATA ---
INITIAL_WIKI_DATA = {
    "getting-started": {"title": "Getting Started", "category": "General", "content": "<h3>Welcome!</h3>"},
    "races": {"title": "Races", "category": "Lore", "content": "<h3>The Kweebecs</h3>"}
}

LEGAL_DATA = {
    "tos": {
        "title": "Terms of Service",
        "content": """
            <p><strong>Last Updated:</strong> 01/04/2026</p>
            
            <h3>1. Acceptance of Terms</h3>
            <p>By accessing or using Majikku (the "Service"), including our game servers, Discord server, and website, you agree to be bound by these Terms. If you disagree with any part of the terms, you may not access the Service.</p>
            
            <h3>2. User Conduct</h3>
            <p>You agree to follow all rules outlined in our Rules Document. Specifically, you agree <strong>NOT</strong> to:</p>
            <ul>
                <li>Use cheats, exploits, or third-party software to gain an unfair advantage.</li>
                <li>Harass, threaten, or abuse other players or staff members.</li>
                <li>Attempt to crash, lag, or disrupt the server operations.</li>
            </ul>

            <h3>3. Account Responsibility</h3>
            <p>You are responsible for safeguarding the account you use to access the Service. You are responsible for any activities or actions under your account, whether you authorized them or not.</p>

            <h3>4. Termination</h3>
            <p>We may terminate or suspend your access to our Service immediately, without prior notice or liability, for any reason whatsoever, including without limitation if you breach the Terms.</p>
            <p><strong>Ban Appeals:</strong> Appeals are processed at the sole discretion of the Senior Moderators and the Leadership team.</p>

            <h3>5. Changes</h3>
            <p>We reserve the right, at our sole discretion, to modify or replace these Terms at any time.</p>
        """
    },
    "privacy": {
        "title": "Privacy Policy",
        "content": """
            <p><strong>Last Updated:</strong> 01/04/2026</p>

            <h3>1. Introduction</h3>
            <p>Welcome to Majikku ("we," "our," or "us"). We are committed to protecting your privacy. This policy explains what information we collect when you join our server, use our website, or interact with our services.</p>

            <h3>2. Information We Collect</h3>
            <p>To facilitate gameplay, moderation, and reward delivery, we collect and store the following specific technical identifiers:</p>
            <ul>
                <li><strong>Discord ID:</strong> Used for authentication on our website and linking your community profile.</li>
                <li><strong>Game UUIDs (Hytale):</strong> Used to uniquely identify your game character in our database.</li>
                <li><strong>In-Game Usernames:</strong> Used for display purposes and command execution.</li>
            </ul>

            <h3>3. How We Use Your Information</h3>
            <p>We use this data strictly for backend server functionality, including but not limited to:</p>
            <ul>
                <li><strong>Account Linking:</strong> Connecting your Discord account to your in-game player data.</li>
                <li><strong>Moderation:</strong> Tracking warnings, bans, mutes, and appeals (based on the LiteBans architecture).</li>
                <li><strong>Rewards:</strong> Delivering in-game items or ranks based on purchases or events.</li>
            </ul>

            <h3>4. Data Sharing</h3>
            <p>We do not sell, trade, or rent your personal identification information to others. We may share generic aggregated demographic information not linked to any personal identification information regarding visitors and users with our business partners and advertisers.</p>

            <h3>5. Data Security</h3>
            <p>We adopt appropriate data collection, storage, and processing practices and security measures to protect against unauthorized access to your personal information (specifically the Discord OAuth2 tokens and database entries).</p>
        """
    },
    "refund": {
        "title": "Refund Policy",
        "content": """
            <p><strong>Last Updated:</strong> 01/04/2026</p>

            <h3>1. Digital Goods</h3>
            <p>All items, ranks, and services purchased on the Majikku store are digital intangible goods.</p>

            <h3>2. No Refunds</h3>
            <p>Because our products are digital and delivered immediately upon payment execution, all sales are final. We do not offer refunds, returns, or exchanges once the transaction is complete and the digital goods have been delivered.</p>

            <h3>3. Chargebacks</h3>
            <p>Any attempt to chargeback or dispute a payment via PayPal, your bank, or other payment processors will result in an automatic and <strong>permanent ban</strong> from the Majikku network (including Game Servers, Discord, and Website). This ban allows no opportunity for appeal.</p>

            <h3>4. Server Termination</h3>
            <p>In the event that Majikku closes or ceases operation, no refunds will be issued for previously purchased ranks or items.</p>
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

# --- INIT DATABASE ---
def init_mysql_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Announcements
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
        
        # 2. Live Wiki Pages
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wiki (
                slug VARCHAR(255) PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                category VARCHAR(255) NOT NULL,
                content LONGTEXT NOT NULL
            )
        ''')

        # 3. Wiki Approval Queue (For Editors)
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
            print("🌱 Seeding Wiki...")
            for slug, data in INITIAL_WIKI_DATA.items():
                cursor.execute("INSERT INTO wiki (slug, title, category, content) VALUES (%s, %s, %s, %s)", (slug, data['title'], data['category'], data['content']))
            conn.commit()
        cursor.close()
        conn.close()
    except Exception as e: print(f"Seed Error: {e}")

init_mysql_db()
seed_wiki_db()

# --- HELPERS ---
def get_hytale_profile(discord_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True) 
        cursor.execute("SELECT hytale_uuid, time_played FROM players WHERE discord_id = %s LIMIT 1", (discord_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result
    except: return None

# --- STAFF CACHE ---
STAFF_GROUPS = [
    {"name": "Leadership", "roles": [{"id": "1207778262378487918", "title": "Owner"}, {"id": "1207778264819572836", "title": "Administrator"}]},
    {"name": "Team Leads", "roles": [{"id": "1207778271811346482", "title": "Staff Manager"}, {"id": "1207778273166098502", "title": "Lead Developer"}, {"id": "1207778274642759760", "title": "Lead Builder"}, {"id": "1452499234103234690", "title": "Lead Modeler"}, {"id": "1207778273791184927", "title": "Lead Coordinator"}, {"id": "1392535920665690142", "title": "Lead Artist"}, {"id": "1452004814375616765", "title": "Lead Storyteller"}, {"id": "1392535925606715533", "title": "Lead Tester"}, {"id": "1454631224592171099", "title": "Lead Wiki Editor"}]},
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

# --- PERMISSION CHECKS (The Internal Logic) ---
def check_role(user_id, role_ids):
    """Checks discord API to see if user has a role ID from the list."""
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    try:
        r = requests.get(f"{API_ENDPOINT}/guilds/{GUILD_ID}/members/{user_id}", headers=headers)
        if r.status_code == 200:
            user_roles = r.json().get('roles', [])
            return any(rid in user_roles for rid in role_ids)
    except: pass
    return False

# Specific Role Checks
def check_is_admin(uid): return check_role(uid, ADMIN_ROLE_IDS)
def check_is_coordinator(uid): return check_role(uid, [LEAD_COORDINATOR_ID])
def check_is_storyteller(uid): return check_role(uid, [LEAD_STORYTELLER_ID])
def check_is_lead_wiki(uid): return check_role(uid, [LEAD_WIKI_EDITOR_ID])
def check_is_wiki_editor(uid): return check_role(uid, [WIKI_EDITOR_ID])

# --- DISCORD MESSAGING ---
def send_wiki_approval_request(sub_id, title, category, author_name, sub_type, content):
    """Sends Wiki Approval Embed to Leadership with a content preview."""
    channel_id = os.getenv("WIKI_APPROVAL_CHANNEL_ID") 
    if not channel_id: return

    # Truncate content for preview
    preview_content = (content[:950] + '... (Truncated)') if len(content) > 950 else content

    color = 15844367 # Gold
    embed = {
        "title": "📜 Wiki Approval Required",
        "description": f"**{author_name}** has submitted a **{sub_type}** page.",
        "color": color,
        "fields": [
            {"name": "Page Title", "value": title, "inline": True},
            {"name": "Category", "value": category, "inline": True},
            {"name": "Content Preview", "value": f"```html\n{preview_content}\n```", "inline": False}
        ],
        "footer": {"text": f"Submission ID: {sub_id} | Status: PENDING"}
    }
    
    # NEW: 3 Buttons
    components = [{"type": 1, "components": [
        # 1. Approve (Green)
        {"type": 2, "style": 3, "label": "Approve & Publish", "emoji": {"name": "✅", "id": None}, "custom_id": f"wiki_approve_{sub_id}"},
        # 2. Approve & Edited (Blurple) - Indicates staff made changes
        {"type": 2, "style": 1, "label": "Approved & Edited", "emoji": {"name": "📝", "id": None}, "custom_id": f"wiki_edit_approve_{sub_id}"},
        # 3. Deny (Red)
        {"type": 2, "style": 4, "label": "Deny", "emoji": {"name": "⛔", "id": None}, "custom_id": f"wiki_deny_{sub_id}"}
    ]}]
    
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {"Authorization": f"Bot {os.getenv('BOT_TOKEN')}", "Content-Type": "application/json"}
    requests.post(url, headers=headers, json={"embeds": [embed], "components": components})

# --- LOGIN & SESSIONS ---
@app.route('/login')
def login():
    return redirect(f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify")

@app.route('/callback')
def callback():
    # 1. SAFETY CHECK: If user is already logged in, ignore the code and go home.
    # This prevents the "Bad Request" error if you refresh the page.
    if 'user' in session:
        return redirect(url_for('home'))

    code = request.args.get('code')
    if not code:
        return redirect(url_for('login'))

    data = {
        'client_id': CLIENT_ID, 
        'client_secret': CLIENT_SECRET, 
        'grant_type': 'authorization_code', 
        'code': code, 
        'redirect_uri': REDIRECT_URI
    }

    try:
        # 2. Exchange Code for Token
        token_resp = requests.post(f'{API_ENDPOINT}/oauth2/token', data=data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
        token_resp.raise_for_status() # This raises the error if it fails
        
        # 3. Get User Info
        user_resp = requests.get(f'{API_ENDPOINT}/users/@me', headers={'Authorization': f'Bearer {token_resp.json().get("access_token")}'})
        user_data = user_resp.json()
        
        # 4. Save Session
        session['user'] = user_data
        
        # 5. Check Permissions
        uid = user_data['id']
        session['is_admin'] = check_is_admin(uid)
        session['is_coord'] = check_is_coordinator(uid)
        session['is_story'] = check_is_storyteller(uid)
        session['is_wiki_lead'] = check_is_lead_wiki(uid)
        session['is_wiki_editor'] = check_is_wiki_editor(uid)
        
    except requests.exceptions.HTTPError as e:
        # If Discord says "Bad Request" (400), it usually means the code expired or was reused.
        # Instead of showing an error page, simply restart the login process.
        if e.response.status_code == 400:
            print(f"OAuth Code invalid or expired (User likely refreshed): {e}")
            return redirect(url_for('login'))
        return f"Login Error: {e}"
        
    except Exception as e:
        return f"Internal Login Error: {e}"
    
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# --- ADMIN PANEL ---
@app.route('/admin')
def admin():
    if 'user' not in session: return redirect(url_for('login'))
    
    # Check Access
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
    if session.get('is_admin') or session.get('is_coord') or session.get('is_story'):
        if session.get('is_admin'):
            cursor.execute('SELECT * FROM announcements ORDER BY id DESC')
        else:
            allowed = []
            if session.get('is_coord'): allowed.append("EVENT")
            if session.get('is_story'): allowed.append("LORE")
            if allowed:
                fmt = ','.join(['%s'] * len(allowed))
                cursor.execute(f"SELECT * FROM announcements WHERE category IN ({fmt}) ORDER BY id DESC", tuple(allowed))
        posts = cursor.fetchall()
    
    # 2. Fetch Live Wiki Pages
    wiki_pages = []
    if session.get('is_admin') or session.get('is_story') or session.get('is_wiki_lead') or session.get('is_wiki_editor'):
        cursor.execute('SELECT * FROM wiki ORDER BY category, title')
        wiki_pages = cursor.fetchall()

    # 3. NEW: Fetch Pending Wiki Submissions (For Leads/Admins to review)
    pending_submissions = []
    # Only Admins, Story Leads, and Wiki Leads should see/approve pending items
    if session.get('is_admin') or session.get('is_story') or session.get('is_wiki_lead'):
        cursor.execute("SELECT * FROM wiki_submissions WHERE status='PENDING' ORDER BY created_at DESC")
        pending_submissions = cursor.fetchall()

    cursor.close()
    conn.close()
    
    return render_template('admin.html', 
                           user=session.get('user'), 
                           announcements=posts, 
                           wiki_pages=wiki_pages, 
                           pending_submissions=pending_submissions)

# --- ADMIN ACTIONS ---
@app.route('/admin/post', methods=['POST'])
def admin_post():
    if 'user' not in session: return "Unauthorized", 403
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO announcements (title, content, category, author) VALUES (%s, %s, %s, %s)', 
                   (request.form['title'], request.form['content'], request.form.get('category'), session['user']['username']))
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

# --- WIKI EDITING ---
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
        
        # BYPASS CHECK: Admins/Story/WikiLeads bypass. WikiEditors go to queue.
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
            send_wiki_approval_request(sub_id, title, category, username, "NEW", content)
        
        cursor.close()
        conn.close()
        return redirect(url_for('admin'))

    return render_template('edit_wiki.html', page=None, user=session.get('user'))

@app.route('/admin/wiki/edit/<slug>', methods=['GET', 'POST'])
def admin_wiki_edit(slug):
    if 'user' not in session: return "Unauthorized", 403
    
    # Permission Check
    has_access = (session.get('is_admin') or session.get('is_story') or session.get('is_wiki_lead') or session.get('is_wiki_editor'))
    if not has_access: return "Unauthorized", 403

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Check if we are reviewing a specific pending submission
    submission_id = request.args.get('submission_id')

    if request.method == 'POST':
        title = request.form['title']
        category = request.form['category']
        content = request.form['content']
        username = session['user']['username']
        user_id = session['user']['id']
        
        is_bypass = (session.get('is_admin') or session.get('is_story') or session.get('is_wiki_lead'))

        if is_bypass:
            # ADMIN/LEAD ACTION: PUBLISH IMMEDIATELY
            # We use REPLACE INTO to handle both "New" pages and "Edits" to existing ones.
            cursor.execute(
                "REPLACE INTO wiki (slug, title, category, content) VALUES (%s, %s, %s, %s)", 
                (slug, title, category, content)
            )
            
            # If this was a review of a pending submission, mark it as APPROVED now.
            if submission_id:
                cursor.execute("UPDATE wiki_submissions SET status='APPROVED' WHERE id=%s", (submission_id,))
                
            conn.commit()
        else:
            # EDITOR ACTION: SUBMIT EDIT REQUEST
            cursor.execute('''INSERT INTO wiki_submissions (slug, title, category, content, author_id, author_name, submission_type) VALUES (%s, %s, %s, %s, %s, %s, 'EDIT')''', (slug, title, category, content, user_id, username))
            conn.commit()
            sub_id = cursor.lastrowid
            send_wiki_approval_request(sub_id, title, category, username, "EDIT", content)

        cursor.close()
        conn.close()
        return redirect(url_for('admin'))

    # --- GET REQUEST (LOADING DATA) ---
    page = None
    
    # 1. If reviewing a submission, try to load from submissions table first
    if submission_id:
        cursor.execute("SELECT * FROM wiki_submissions WHERE id = %s", (submission_id,))
        page = cursor.fetchone()
    
    # 2. If no submission ID (or invalid), load from live wiki table
    if not page:
        cursor.execute("SELECT * FROM wiki WHERE slug = %s", (slug,))
        page = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    # 3. If still nothing, it's a 404 (unless we are creating new, but this is the edit route)
    if not page:
        return "Page or Submission not found", 404
        
    return render_template('edit_wiki.html', page=page, user=session.get('user'))

@app.route('/admin/wiki/delete/<slug>')
def admin_wiki_delete(slug):
    if 'user' not in session: return "Unauthorized", 403
    # Editors CANNOT delete
    if not (session.get('is_admin') or session.get('is_story') or session.get('is_wiki_lead')):
        return "Unauthorized", 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM wiki WHERE slug=%s", (slug,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin'))

# --- PUBLIC ROUTES (Fixed 404s) ---
def build_wiki_tree(pages):
    tree = {}
    for page in pages:
        parts = [p.strip() for p in page['category'].split('>')]
        current = tree
        for i, part in enumerate(parts):
            if part not in current: current[part] = {"subcategories": {}, "pages": []}
            if i == len(parts) - 1: current[part]["pages"].append(page)
            current = current[part]["subcategories"]
    return tree

@app.route('/')
def home():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True) 
    cursor.execute("SELECT * FROM announcements WHERE category='NEWS' ORDER BY id DESC")
    posts = cursor.fetchall()
    conn.close()
    return render_template('home.html', user=session.get('user'), announcements=posts)

@app.route('/events')
def events():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM announcements WHERE category='EVENT' ORDER BY id DESC")
    posts = cursor.fetchall()
    conn.close()
    return render_template('events.html', user=session.get('user'), announcements=posts)

@app.route('/lore')
def lore():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM announcements WHERE category='LORE' ORDER BY id DESC")
    posts = cursor.fetchall()
    conn.close()
    return render_template('lore.html', user=session.get('user'), announcements=posts)

@app.route('/rules')
def rules(): return render_template('rules.html', user=session.get('user'))

@app.route('/socials')
def socials(): return render_template('socials.html', user=session.get('user'))

@app.route('/info')
def info(): return render_template('info.html', user=session.get('user'))

@app.route('/staff')
def staff():
    grouped_staff = get_staff_data()
    return render_template('staff.html', staff_groups=grouped_staff, group_order=STAFF_GROUPS, user=session.get('user'))

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

# --- FORMS ---
@app.route('/apply')
def apply():
    if 'user' not in session: return redirect(url_for('login'))
    hytale_data = get_hytale_profile(session['user']['id'])
    return render_template('apply.html', user=session['user'], player=hytale_data)

@app.route('/submit', methods=['POST'])
def submit_application():
    if 'user' not in session: 
        return jsonify({'error': 'Unauthorized'}), 401
    
    # 1. Get Data Safely
    data = request.get_json(silent=True) or {}
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL") 
    
    if not webhook_url:
        print("Error: No Application Webhook URL found.")
        return jsonify({'success': False, 'error': 'Server configuration error.'}), 500

    def clean(val):
        if val is None: return "N/A"
        s = str(val).strip()
        if s == "": return "N/A"
        return s

    user_info = session.get('user', {})
    discord_username = user_info.get('username', 'Unknown User')
    discord_id = user_info.get('id', 'Unknown ID')
    team_name = clean(data.get('team', 'General'))

    # 2. Build Base Embed
    embed = {
        "title": f"📝 New Application: {team_name}",
        "color": 5763719,
        "fields": [
            {"name": "Discord User", "value": f"{discord_username} (<@{discord_id}>)", "inline": True},
            {"name": "Hytale Username", "value": clean(data.get('hytale_name')), "inline": True},
            {"name": "Age", "value": clean(data.get('age')), "inline": True},
            {"name": "Timezone", "value": clean(data.get('timezone')), "inline": True},
            {"name": "Availability", "value": clean(data.get('availability')), "inline": True},
            {"name": "Languages", "value": clean(data.get('languages')), "inline": False},
        ],
        "footer": {"text": "Majikku Staff Application System"}
    }

    # 3. Add Answers
    answers = data.get('answers', {})
    if isinstance(answers, dict): 
        for question, answer in answers.items():
            if not question or str(question).strip() == "": continue
            
            q_clean = str(question)[:256]
            a_clean = clean(answer)
            if len(a_clean) > 1024: a_clean = a_clean[:1021] + "..."

            embed['fields'].append({
                "name": q_clean,
                "value": a_clean,
                "inline": False
            })

    # 4. Construct Payload (FIXED FOR FORUM CHANNELS)
    payload = {
        "username": "Application Bot",
        "avatar_url": "https://i.imgur.com/AfFp7pu.png",
        "thread_name": f"App: {discord_username} - {team_name}", # REQUIRED for Forums
        "embeds": [embed]
    }

    # 5. Send
    try:
        response = requests.post(webhook_url, json=payload)
        
        if not response.ok:
            print(f"⚠️ Discord API Error [{response.status_code}]: {response.text}")
            return jsonify({'success': False, 'error': f"Discord Error: {response.text}"}), response.status_code
            
        response.raise_for_status() 
    except requests.exceptions.RequestException as e:
        print(f"❌ Connection Error: {e}")
        return jsonify({'success': False, 'error': 'Failed to connect to Discord.'}), 500

    return jsonify({'success': True, 'message': 'Application submitted successfully!'})

@app.route('/appeal')
def appeal():
    if 'user' not in session: return redirect(url_for('login'))
    hytale_data = get_hytale_profile(session['user']['id'])
    return render_template('appeal.html', user=session['user'], player=hytale_data)

@app.route('/submit-appeal', methods=['POST'])
def submit_appeal():
    return jsonify({'success': True})

@app.route('/report', methods=['GET', 'POST'])
def report():
    if 'user' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        # Collect Data
        report_type = request.form.get('report_type')
        target_name = request.form.get('target_name')
        server_origin = request.form.get('server_origin')
        reason = request.form.get('reason')
        evidence = request.form.get('evidence')
        is_anon = request.form.get('anonymous') == 'on'
        reporter_name = session['user']['username']
        reporter_id = session['user']['id']

        # Save to DB
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

        # Send to Discord
        send_report_bot_message(report_id, report_type, "WEBSITE", reporter_name, target_name, server_origin, reason, evidence, is_anon)
        return redirect(url_for('report_success', report_id=report_id))
    
    return render_template('report.html', user=session['user'])

@app.route('/report/success/<int:report_id>')
def report_success(report_id):
    if 'user' not in session: return redirect(url_for('login'))
    return render_template('report_success.html', user=session['user'], report_id=report_id)

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),'favicon.ico', mimetype='image/vnd.microsoft.icon')

if __name__ == '__main__':
    app.run(debug=True)