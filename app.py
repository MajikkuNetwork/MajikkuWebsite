from flask import Flask, redirect, request, render_template, session, url_for, jsonify
import requests
import os
import time
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

# ID allowed to post Lore only
LEAD_STORYTELLER_ID = "1452004814375616765"

# --- OLD HARDCODED WIKI DATA (For seeding DB only) ---
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

# --- DATABASE CONNECTION HELPER ---
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DB"),
        collation='utf8mb4_general_ci'  # <--- ADD THIS LINE
    )

# --- DATABASE SETUP (MYSQL) ---
def init_mysql_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Announcements Table
        # Note: Using LONGTEXT for content to handle large HTML blocks
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
        
        # Wiki Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wiki (
                slug VARCHAR(255) PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                category VARCHAR(255) NOT NULL,
                content LONGTEXT NOT NULL
            )
        ''')
        
        conn.commit()
        cursor.close()
        conn.close()
        print("Database tables checked/initialized.")
    except mysql.connector.Error as err:
        print(f"Error initializing database: {err}")

# --- SEED WIKI DATA ---
def seed_wiki_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM wiki")
        count = cursor.fetchone()[0]
        
        if count == 0:
            print("Seeding Wiki Database...")
            for slug, data in INITIAL_WIKI_DATA.items():
                # MySQL uses %s as placeholder, not ?
                cursor.execute(
                    "INSERT INTO wiki (slug, title, category, content) VALUES (%s, %s, %s, %s)",
                    (slug, data['title'], data['category'], data['content'])
                )
            conn.commit()
        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        print(f"Error seeding database: {err}")

# Initialize DB on startup
init_mysql_db()
seed_wiki_db()

# --- HELPER: GET HYTALE INFO ---
def get_hytale_profile(discord_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True) 
        query = "SELECT username, hytale_uuid, time_played FROM players WHERE discord_id = %s LIMIT 1"
        cursor.execute(query, (discord_id,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result
    except Exception as e:
        print(f"MySQL Connection Error: {e}")
        return None

# --- STAFF PAGE CONFIGURATION ---
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
    if time.time() - staff_cache["timestamp"] < 300 and staff_cache["data"]:
        return staff_cache["data"]

    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    try:
        response = requests.get(f"{API_ENDPOINT}/guilds/{GUILD_ID}/members?limit=1000", headers=headers)
        if response.status_code != 200: return {}

        members = response.json()
        grouped_staff = {group["name"]: [] for group in STAFF_GROUPS}
        
        for member in members:
            user = member.get("user", {})
            user_roles = member.get("roles", [])
            avatar_url = f"https://cdn.discordapp.com/avatars/{user['id']}/{user['avatar']}.png" if user.get("avatar") else "https://cdn.discordapp.com/embed/avatars/0.png"

            for group in STAFF_GROUPS:
                found_title = None
                for role_def in group["roles"]:
                    if role_def["id"] in user_roles:
                        found_title = role_def["title"]
                        break
                if found_title:
                    grouped_staff[group["name"]].append({"name": member.get("nick") or user.get("username"), "avatar": avatar_url, "role": found_title})

        staff_cache["data"] = grouped_staff
        staff_cache["timestamp"] = time.time()
        return grouped_staff
    except: return {}

def check_is_admin(user_id):
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    try:
        response = requests.get(f"{API_ENDPOINT}/guilds/{GUILD_ID}/members/{user_id}", headers=headers)
        if response.status_code == 200:
            roles = response.json().get('roles', [])
            for role_id in roles:
                if role_id in ADMIN_ROLE_IDS: return True
    except: pass
    return False

def check_is_coordinator(user_id):
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    try:
        response = requests.get(f"{API_ENDPOINT}/guilds/{GUILD_ID}/members/{user_id}", headers=headers)
        if response.status_code == 200:
            if LEAD_COORDINATOR_ID in response.json().get('roles', []): return True
    except: pass
    return False

def check_is_storyteller(user_id):
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    try:
        response = requests.get(f"{API_ENDPOINT}/guilds/{GUILD_ID}/members/{user_id}", headers=headers)
        if response.status_code == 200:
            if LEAD_STORYTELLER_ID in response.json().get('roles', []): return True
    except: pass
    return False

# --- ROUTES ---

@app.route('/')
def home():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True) # dictionary=True is KEY for templates
    cursor.execute("SELECT * FROM announcements WHERE category='NEWS' ORDER BY id DESC")
    posts = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('home.html', user=session.get('user'), announcements=posts)

@app.route('/events')
def events():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM announcements WHERE category='EVENT' ORDER BY id DESC")
    posts = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('events.html', user=session.get('user'), announcements=posts)

@app.route('/lore')
def lore():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM announcements WHERE category='LORE' ORDER BY id DESC")
    posts = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('lore.html', user=session.get('user'), announcements=posts)

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
        
        session['user'] = user_data
        session['is_admin'] = check_is_admin(user_data['id'])
        session['is_coord'] = check_is_coordinator(user_data['id'])
        session['is_story'] = check_is_storyteller(user_data['id'])
        
    except Exception as e:
        return f"Login Error: {e}"
    
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# --- ADMIN ROUTES (ANNOUNCEMENTS) ---
@app.route('/admin')
def admin():
    if 'user' not in session: return redirect(url_for('login'))
    if not (session.get('is_admin') or session.get('is_coord') or session.get('is_story')):
        return render_template('base.html', content="<h1>Access Denied</h1>")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # 1. Fetch Announcements
    if session.get('is_admin'):
        cursor.execute('SELECT * FROM announcements ORDER BY id DESC')
        posts = cursor.fetchall()
    else:
        allowed = []
        if session.get('is_coord'): allowed.append("EVENT")
        if session.get('is_story'): allowed.append("LORE")
        
        if allowed:
            # Create parameterized query for safety
            format_strings = ','.join(['%s'] * len(allowed))
            cursor.execute(f"SELECT * FROM announcements WHERE category IN ({format_strings}) ORDER BY id DESC", tuple(allowed))
            posts = cursor.fetchall()
        else:
            posts = []
    
    # 2. Fetch Wiki Pages
    wiki_pages = []
    if session.get('is_admin') or session.get('is_story'):
        cursor.execute('SELECT * FROM wiki ORDER BY category, title')
        wiki_pages = cursor.fetchall()

    cursor.close()
    conn.close()
    return render_template('admin.html', user=session.get('user'), announcements=posts, wiki_pages=wiki_pages)

@app.route('/admin/post', methods=['POST'])
def admin_post():
    if 'user' not in session: return "Unauthorized", 403
    title = request.form['title']
    content = request.form['content']
    category = request.form.get('category')
    author = session['user']['username']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO announcements (title, content, category, author) VALUES (%s, %s, %s, %s)', 
        (title, content, category, author)
    )
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
        cursor.execute(
            "UPDATE announcements SET title = %s, content = %s WHERE id = %s", 
            (request.form['title'], request.form['content'], id)
        )
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

# --- ADMIN ROUTES (WIKI) ---
@app.route('/admin/wiki/new', methods=['GET', 'POST'])
def admin_wiki_new():
    if 'user' not in session or not (session.get('is_admin') or session.get('is_story')):
        return "Unauthorized", 403

    if request.method == 'POST':
        slug = request.form['slug'].lower().replace(" ", "-")
        title = request.form['title']
        category = request.form['category']
        content = request.form['content']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # MySQL syntax for replace
            cursor.execute(
                "REPLACE INTO wiki (slug, title, category, content) VALUES (%s, %s, %s, %s)", 
                (slug, title, category, content)
            )
            conn.commit()
        except Exception as e:
            print(f"DB Error: {e}")
        
        cursor.close()
        conn.close()
        return redirect(url_for('admin'))

    return render_template('edit_wiki.html', page=None, user=session.get('user'))

@app.route('/admin/wiki/edit/<slug>', methods=['GET', 'POST'])
def admin_wiki_edit(slug):
    if 'user' not in session or not (session.get('is_admin') or session.get('is_story')):
        return "Unauthorized", 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if request.method == 'POST':
            title = request.form['title']
            category = request.form['category']
            content = request.form['content']
            
            cursor.execute(
                "UPDATE wiki SET title=%s, category=%s, content=%s WHERE slug=%s", 
                (title, category, content, slug)
            )
            conn.commit()
            cursor.close()
            conn.close()
            return redirect(url_for('admin'))

        cursor.execute("SELECT * FROM wiki WHERE slug = %s", (slug,))
        page_data = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not page_data:
            return "Page not found", 404
        
        return render_template('edit_wiki.html', page=page_data, user=session.get('user'))
        
    except Exception as e:
        print(f"ERROR in Wiki Edit: {e}") 
        return f"Internal Error: {e}", 500

@app.route('/admin/wiki/delete/<slug>')
def admin_wiki_delete(slug):
    if 'user' not in session or not (session.get('is_admin') or session.get('is_story')):
        return "Unauthorized", 403
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM wiki WHERE slug=%s", (slug,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('admin'))

# --- HELPER: BUILD WIKI TREE ---
def build_wiki_tree(pages):
    tree = {}
    
    for page in pages:
        # Split "Lore > Races > Elves" into ['Lore', 'Races', 'Elves']
        # We strip whitespace to handle "Lore > Races" vs "Lore>Races"
        parts = [p.strip() for p in page['category'].split('>')]
        
        current_level = tree
        
        for i, part in enumerate(parts):
            # Create the category if it doesn't exist at this level
            if part not in current_level:
                current_level[part] = {
                    "subcategories": {}, 
                    "pages": []
                }
            
            # If this is the LAST part of the path, add the page here
            if i == len(parts) - 1:
                current_level[part]["pages"].append(page)
            
            # Move deeper into the tree for the next iteration
            current_level = current_level[part]["subcategories"]
            
    return tree

@app.route('/wiki')
def wiki_hub():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Get all pages
    cursor.execute("SELECT * FROM wiki ORDER BY category, title")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    # Build the nested tree structure
    wiki_tree = build_wiki_tree(rows)
    
    return render_template('wiki_hub.html', wiki_tree=wiki_tree, user=session.get('user'))

@app.route('/wiki/<slug>')
def wiki_page(slug):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM wiki WHERE slug=%s", (slug,))
    page = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not page: return "Page not found", 404
    return render_template('wiki_entry.html', page=page, user=session.get('user'))

@app.route('/legal/<doc_type>')
def legal_page(doc_type):
    doc = LEGAL_DATA.get(doc_type)
    if not doc: return "Document not found", 404
    return render_template('legal_doc.html', doc=doc, user=session.get('user'))

# --- APPLICATION ROUTES (Webhook Enabled) ---
@app.route('/apply')
def apply():
    if 'user' not in session: return redirect(url_for('login'))
    hytale_data = get_hytale_profile(session['user']['id'])
    return render_template('apply.html', user=session['user'], player=hytale_data)

@app.route('/submit', methods=['POST'])
def submit_application():
    if 'user' not in session: return jsonify({'error': 'Unauthorized'}), 401
    
    # ... Webhook logic here (use previously provided webhook code) ...
    # This part does not interact with DB, so no changes needed
    
    return jsonify({'success': True})

@app.route('/appeal')
def appeal():
    if 'user' not in session: return redirect(url_for('login'))
    hytale_data = get_hytale_profile(session['user']['id'])
    return render_template('appeal.html', user=session['user'], player=hytale_data)

@app.route('/submit-appeal', methods=['POST'])
def submit_appeal():
    # ... Webhook logic here (use previously provided webhook code) ...
    return jsonify({'success': True})

# --- REPORT ROUTES ---

# --- REPORT ROUTES ---
@app.route('/report', methods=['GET', 'POST'])
def report():
    if 'user' not in session: return redirect(url_for('login'))

    if request.method == 'POST':
        # 1. Get Form Data
        report_type = request.form.get('report_type')
        target_name = request.form.get('target_name')
        server_origin = request.form.get('server_origin')
        reason = request.form.get('reason')
        evidence = request.form.get('evidence')
        
        # Checkbox returns 'on' if checked, None if not
        is_anon = request.form.get('anonymous') == 'on'
        
        reporter_name = session['user']['username']
        reporter_id = session['user']['id']

        # 2. Save to Database (Keep your existing DB code here)
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                '''INSERT INTO reports 
                   (type, source, reporter_id, reported_name, server_origin, reason, evidence, is_anonymous) 
                   VALUES (%s, 'WEBSITE', %s, %s, %s, %s, %s, %s)''',
                (report_type, reporter_id, target_name, server_origin, reason, evidence, 1 if is_anon else 0)
            )
            conn.commit()
            report_id = cursor.lastrowid
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"DATABASE ERROR: {e}")
            return "Database Error", 500

        # 3. Send via Bot API (With Buttons)
        send_report_bot_message(
            report_id=report_id,
            report_type=report_type,
            source="WEBSITE",
            reporter_name=reporter_name,
            target_name=target_name,
            server=server_origin,
            reason=reason,
            evidence=evidence,
            is_anonymous=is_anon
        )

        # Pass the report_id to the template
        return render_template('report_success.html', user=session['user'], report_id=report_id)
    
    return render_template('report.html', user=session['user'])

# --- HELPER: WEBHOOK SENDER (FIXED) ---
# --- HELPER: BOT SENDER WITH BUTTONS ---
def send_report_bot_message(report_id, report_type, source, reporter_name, target_name, server, reason, evidence, is_anonymous):
    
    # 1. Select Channel ID & Color
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

    # 2. Build the Embed (Same as before)
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

    # 3. DEFINE THE BUTTONS (Components)
    # We send a "Action Row" containing one button: "Claim / Investigate"
    components = [
        {
            "type": 1, # Action Row
            "components": [
                {
                    "type": 2, # Button
                    "style": 1, # Primary (Blurple Color)
                    "label": "Claim / Investigate",
                    "emoji": {"name": "🔎", "id": None}, # 🔎 Emoji
                    "custom_id": f"claim_report_{report_id}" # CRITICAL: This sends the ID to your bot
                }
            ]
        }
    ]

    # 4. Send Request via BOT API (Not Webhook)
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {
        "Authorization": f"Bot {os.getenv('BOT_TOKEN')}",
        "Content-Type": "application/json"
    }
    
    data = {
        "embeds": [embed],
        "components": components # Attach the button here
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            print("Bot message sent with buttons.")
        else:
            print(f"BOT MESSAGE FAILED: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"BOT API EXCEPTION: {e}")

if __name__ == '__main__':
    app.run(debug=True)