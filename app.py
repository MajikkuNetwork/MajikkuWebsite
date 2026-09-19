from flask import Flask, redirect, request, render_template, session, url_for, jsonify, send_from_directory
import requests
import os
import time
import mysql.connector 
from dotenv import load_dotenv
import secrets
import hashlib
import base64
from urllib.parse import urlencode
from functools import wraps

# Load sensitive info from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(24))

# --- CONFIGURATION ---
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
BOT_TOKEN = os.getenv("BOT_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

# Shared Majikku identity/game database.
GENERAL_DB = os.getenv("MYSQL_GENERAL_DB", "majikkuo_general")

# Webhooks
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL") 
APPEALS_WEBHOOK_URL = os.getenv("APPEALS_WEBHOOK_URL") 

REDIRECT_URI = os.getenv("REDIRECT_URI")
API_ENDPOINT = 'https://discord.com/api/v10'
# --- HYTALE OAUTH ---
HYTALE_CLIENT_ID = os.getenv("HYTALE_CLIENT_ID")
HYTALE_CLIENT_SECRET = os.getenv("HYTALE_CLIENT_SECRET")
HYTALE_REDIRECT_URI = os.getenv(
    "HYTALE_REDIRECT_URI",
    "https://majikku.org/auth/hytale/callback"
)

HYTALE_ISSUER = "https://connect.accounts.hytale.com"
HYTALE_AUTH_URL = f"{HYTALE_ISSUER}/oauth2/auth"
HYTALE_TOKEN_URL = f"{HYTALE_ISSUER}/oauth2/token"
HYTALE_USERINFO_URL = f"{HYTALE_ISSUER}/userinfo"

HYTALE_SCOPES = [
    "openid",
    "hytale:profile",
    "account:game_ownership"
]

# --- ROLE IDS / WEBSITE PERMISSIONS ---
# These defaults match the Majikku Discord roles. Every value can be overridden in .env.
ROLE_IDS = {
    "owner": os.getenv("ROLE_OWNER", "1207778262378487918"),
    "sysadmin": os.getenv("ROLE_SYSADMIN", "1489438232042016999"),
    "staffmanager": os.getenv("ROLE_STAFF_MANAGER", "1207778271811346482"),
    "admin": os.getenv("ROLE_ADMIN", "1207778264819572836"),
    "lead": os.getenv("ROLE_LEAD", "1452499232849268767"),
    "leaddev": os.getenv("ROLE_LEAD_DEV", "1207778273166098502"),
    "leadcoord": os.getenv("ROLE_LEAD_COORD", "1207778273791184927"),
    "eventcoord": os.getenv("ROLE_EVENT_COORD", "1392535922331095051"),
    "socialcoord": os.getenv("ROLE_SOCIAL_COORD", "1392535907965341806"),
    "leadstory": os.getenv("ROLE_LEAD_STORY", "1452004814375616765"),
    "story": os.getenv("ROLE_STORY", "1452004927441342616"),
    "wikieditor": os.getenv("ROLE_WIKI_EDITOR", "1454631225309401269"),
    "dev": os.getenv("ROLE_DEV", "1207778264190292052"),
    "jrdev": os.getenv("ROLE_JR_DEV", "1392535924918714408"),
    "srmod": os.getenv("ROLE_SR_MOD", "1207778265008439467"),
    "mod": os.getenv("ROLE_MOD", "1207778265931055204"),
    "helper": os.getenv("ROLE_HELPER", "1207778266572918904"),
}

ALL_WEBSITE_PERMISSIONS = {
    "admin.access", "lookup.players", "lookup.reports", "lookup.applications",
    "lookup.appeals", "lookup.punishments", "content.announcements",
    "content.events", "wiki.edit", "wiki.publish", "wiki.review",
    "staff.view", "audit.view", "admin.settings", "admin.permissions"
}

ROLE_PERMISSIONS = {
    "owner": ALL_WEBSITE_PERMISSIONS,
    "sysadmin": ALL_WEBSITE_PERMISSIONS,
    "admin": ALL_WEBSITE_PERMISSIONS,
    "lead": {"admin.access","lookup.players","lookup.reports","lookup.applications","lookup.appeals","lookup.punishments","staff.view","audit.view"},
    "staffmanager": {"admin.access","lookup.players","lookup.reports","lookup.applications","lookup.appeals","lookup.punishments","staff.view","audit.view"},
    "srmod": {"admin.access","lookup.players","lookup.reports","lookup.applications","lookup.appeals","lookup.punishments"},
    "mod": {"admin.access","lookup.players","lookup.reports","lookup.appeals","lookup.punishments"},
    "helper": {"admin.access","lookup.players","lookup.reports"},
    "leadcoord": {"admin.access","lookup.applications","content.announcements","content.events"},
    "eventcoord": {"admin.access","content.events"},
    "socialcoord": {"admin.access","content.announcements"},
    "leadstory": {"admin.access","wiki.edit","wiki.publish","wiki.review"},
    "story": {"admin.access","wiki.edit"},
    "wikieditor": {"admin.access","wiki.edit"},
    "leaddev": {"admin.access","lookup.players","audit.view"},
    "dev": {"admin.access"},
    "jrdev": {"admin.access"},
}

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
    """
    Return the permanent Discord -> Hytale identity link for this user.

    account_links is the authoritative ownership bridge. core_players is used
    only to prefer the player's latest known in-game username when available.
    """
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(f"""
            SELECT
                al.hytale_uuid,
                COALESCE(cp.username, al.hytale_name) AS hytale_name
            FROM `{GENERAL_DB}`.`account_links` AS al
            LEFT JOIN `{GENERAL_DB}`.`core_players` AS cp
                ON cp.hytale_uuid = al.hytale_uuid
            WHERE al.discord_id = %s
            LIMIT 1
        """, (str(discord_id),))

        result = cursor.fetchone()

        if result:
            result["verified"] = True
            result["verification_source"] = "majikku"

        return result

    except Exception as e:
        print(f"HYTALE LINK LOOKUP ERROR: {e}")
        return None

    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def save_hytale_link(discord_user, hytale_uuid, hytale_name):
    """
    Persist a Hytale identity verified through Hytale OAuth.

    Refuse conflicting links instead of relying on ON DUPLICATE KEY UPDATE:
    one Discord account maps to one Hytale UUID and one Hytale UUID maps to
    one Discord account.
    """
    conn = None
    cursor = None

    discord_id = str(discord_user["id"])
    hytale_uuid = str(hytale_uuid)
    hytale_name = str(hytale_name)
    discord_username = discord_user.get("username")
    discord_display_name = (
        discord_user.get("global_name")
        or discord_username
    )

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(f"""
            SELECT id, hytale_uuid, discord_id
            FROM `{GENERAL_DB}`.`account_links`
            WHERE discord_id = %s OR hytale_uuid = %s
            FOR UPDATE
        """, (discord_id, hytale_uuid))

        existing = cursor.fetchall()

        for row in existing:
            existing_discord = str(row["discord_id"])
            existing_hytale = str(row["hytale_uuid"])

            if existing_discord == discord_id and existing_hytale != hytale_uuid:
                print("HYTALE LINK CONFLICT: Discord account is already linked to another Hytale UUID.")
                conn.rollback()
                return False

            if existing_hytale == hytale_uuid and existing_discord != discord_id:
                print("HYTALE LINK CONFLICT: Hytale UUID is already linked to another Discord account.")
                conn.rollback()
                return False

        same_link = next(
            (
                row for row in existing
                if str(row["discord_id"]) == discord_id
                and str(row["hytale_uuid"]) == hytale_uuid
            ),
            None
        )

        if same_link:
            cursor.execute(f"""
                UPDATE `{GENERAL_DB}`.`account_links`
                SET hytale_name = %s,
                    discord_username = %s,
                    discord_display_name = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (
                hytale_name,
                discord_username,
                discord_display_name,
                same_link["id"]
            ))
        else:
            cursor.execute(f"""
                INSERT INTO `{GENERAL_DB}`.`account_links`
                    (hytale_uuid, hytale_name, discord_id, discord_username, discord_display_name)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                hytale_uuid,
                hytale_name,
                discord_id,
                discord_username,
                discord_display_name
            ))

        conn.commit()
        return True

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"HYTALE LINK SAVE ERROR: {e}")
        return False

    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()


def create_pkce_pair():
    verifier = secrets.token_urlsafe(64)

    digest = hashlib.sha256(
        verifier.encode("ascii")
    ).digest()

    challenge = (
        base64.urlsafe_b64encode(digest)
        .rstrip(b"=")
        .decode("ascii")
    )

    return verifier, challenge


def get_application_hytale_identity():
    """
    Resolve the authenticated user's Hytale identity.

    Priority:
    1. Permanent Majikku account_links record.
    2. Hytale OAuth identity from this browser session.
    """

    if "user" not in session:
        return None

    # Existing Majikku account link wins.
    linked_profile = get_hytale_profile(
        session["user"]["id"]
    )

    if linked_profile:
        return linked_profile

    # Otherwise use the Hytale identity authenticated
    # during this session.
    oauth_profile = session.get("hytale_profile")

    if oauth_profile:
        return {
            "hytale_uuid": oauth_profile.get("hytale_uuid"),
            "hytale_name": oauth_profile.get("hytale_name"),
            "owns_hytale": oauth_profile.get("owns_hytale"),
            "verified": True,
            "verification_source": "hytale"
        }

    return None

# --- STAFF CACHE ---
STAFF_GROUPS = [
    {"name": "Leadership", "roles": [{"id": "1207778262378487918", "title": "Owner"}, {"id": "1207778264819572836", "title": "Administrator"}]},
    {"name": "Team Leads", "roles": [{"id": "1207778271811346482", "title": "Staff Manager"}, {"id": "1489438232042016999", "title": "System Administrator"}, {"id": "1207778273166098502", "title": "Lead Developer"}, {"id": "1207778274642759760", "title": "Lead Builder"}, {"id": "1452499234103234690", "title": "Lead Modeler"}, {"id": "1207778273791184927", "title": "Lead Coordinator"}, {"id": "1392535920665690142", "title": "Lead Artist"}, {"id": "1452004814375616765", "title": "Lead Storyteller"}, {"id": "1392535925606715533", "title": "Lead Tester"}, {"id": "1454631224592171099", "title": "Lead Wiki Editor"}]},
    {"name": "Development Team", "roles": [{"id": "1207778273166098502", "title": "Lead Developer"}, {"id": "1207778264190292052", "title": "Developer"}, {"id": "1392535924918714408", "title": "Jr. Developer"}]},
    {"name": "Moderation Team", "roles": [{"id": "1207778265008439467", "title": "Senior Moderator"}, {"id": "1207778265931055204", "title": "Moderator"}, {"id": "1207778266572918904", "title": "Helper"}]},
    {"name": "Build Team", "roles": [{"id": "1207778274642759760", "title": "Lead Builder"}, {"id": "1452499233591791777", "title": "Senior Builder"}, {"id": "1207778275334553640", "title": "Builder"}]},
    {"name": "Modeling Team", "roles": [{"id": "1452499234103234690", "title": "Lead Modeler"}, {"id": "1452499235332292801", "title": "Senior Modeler"}, {"id": "1452499236091592806", "title": "Modeler"}]},
    {"name": "Coordinator Team", "roles": [{"id": "1207778273791184927", "title": "Lead Coordinator"}, {"id": "1392535922331095051", "title": "Event Coordinator"}, {"id": "1392535907965341806", "title": "Social Coordinator"}]},
    {"name": "Story Team", "roles": [{"id": "1452004814375616765", "title": "Lead Storyteller"}, {"id": "1452004927441342616", "title": "Storyteller"}]},
    {"name": "Art Team", "roles": [{"id": "1392535920665690142", "title": "Lead Artist"}, {"id": "1392535921487908945", "title": "Artist"}]},
    {"name": "Wiki Team", "roles": [{"id": "1454631224592171099", "title": "Lead Wiki Editor"}, {"id": "1454631225309401269", "title": "Wiki Editor"}]},
    {"name": "Tester Team", "roles": [{"id": "1392535925606715533", "title": "Lead Tester"}, {"id": "1452499234720055316", "title": "Senior Tester"}, {"id": "1392535923203379260", "title": "Tester"}]}
]

staff_cache = {"data": None, "timestamp": 0}

def get_staff_data():
    if time.time() - staff_cache["timestamp"] < 300 and staff_cache["data"]:
        return staff_cache["data"]

    headers = {"Authorization": f"Bot {BOT_TOKEN}"}

    try:
        response = requests.get(
            f"{API_ENDPOINT}/guilds/{GUILD_ID}/members?limit=1000",
            headers=headers,
            timeout=10
        )

        if response.status_code != 200:
            return {}

        members = response.json()
        grouped = {group["name"]: [] for group in STAFF_GROUPS}

        # Load all Discord -> Hytale links once, rather than doing one SQL
        # query per staff card.
        hytale_by_discord = {}
        conn = None
        cursor = None

        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(f"""
                SELECT
                    al.discord_id,
                    COALESCE(cp.username, al.hytale_name) AS hytale_name
                FROM `{GENERAL_DB}`.`account_links` AS al
                LEFT JOIN `{GENERAL_DB}`.`core_players` AS cp
                    ON cp.hytale_uuid = al.hytale_uuid
            """)

            for row in cursor.fetchall():
                if row.get("discord_id"):
                    hytale_by_discord[str(row["discord_id"])] = row.get("hytale_name")

        except Exception as e:
            print(f"STAFF HYTALE LOOKUP ERROR: {e}")

        finally:
            if cursor:
                cursor.close()
            if conn and conn.is_connected():
                conn.close()

        for member in members:
            user = member.get("user", {})
            user_id = str(user.get("id", ""))
            user_roles = member.get("roles", [])

            avatar = (
                f"https://cdn.discordapp.com/avatars/{user_id}/{user['avatar']}.png"
                if user.get("avatar")
                else "https://cdn.discordapp.com/embed/avatars/0.png"
            )

            for group in STAFF_GROUPS:
                found = None

                for role in group["roles"]:
                    if role["id"] in user_roles:
                        found = role["title"]
                        break

                if found:
                    grouped[group["name"]].append({
                        "name": member.get("nick") or user.get("username"),
                        "avatar": avatar,
                        "role": found,
                        "hytale_name": hytale_by_discord.get(user_id)
                    })

        staff_cache["data"] = grouped
        staff_cache["timestamp"] = time.time()
        return grouped

    except Exception as e:
        print(f"STAFF DATA ERROR: {e}")
        return {}

# --- PERMISSION RESOLVER ---
def get_discord_roles(user_id):
    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    try:
        r = requests.get(f"{API_ENDPOINT}/guilds/{GUILD_ID}/members/{user_id}", headers=headers, timeout=8)
        if r.status_code == 200:
            return {str(role_id) for role_id in r.json().get("roles", [])}
    except requests.RequestException as exc:
        print(f"Discord role lookup failed: {exc}")
    return set()

def resolve_permissions(role_ids):
    role_ids = {str(x) for x in role_ids}
    role_names = {name for name, rid in ROLE_IDS.items() if rid and rid in role_ids}
    permissions = set()
    for role_name in role_names:
        permissions.update(ROLE_PERMISSIONS.get(role_name, set()))
    return role_names, permissions

def refresh_session_permissions(user_id):
    role_names, permissions = resolve_permissions(get_discord_roles(user_id))
    session["staff_roles"] = sorted(role_names)
    session["permissions"] = sorted(permissions)
    # Compatibility with existing templates while they are migrated.
    session["is_admin"] = bool({"owner","sysadmin","admin"} & role_names)
    session["is_coord"] = bool({"leadcoord","eventcoord","socialcoord"} & role_names)
    session["is_story"] = bool({"leadstory","story"} & role_names)
    session["is_wiki_lead"] = "leadstory" in role_names
    session["is_wiki_editor"] = "wikieditor" in role_names
    return permissions

def has_permission(permission):
    return permission in set(session.get("permissions", []))

@app.context_processor
def permission_template_helpers():
    return {"has_permission": has_permission}

def require_permission(permission):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if "user" not in session:
                return redirect(url_for("login"))
            if not has_permission(permission):
                return "Forbidden", 403
            return fn(*args, **kwargs)
        return wrapped
    return decorator

def check_role(user_id, role_ids):
    return bool(get_discord_roles(user_id) & {str(x) for x in role_ids})

# --- DISCORD MESSAGING ---
def send_report_bot_message(
    report_id,
    report_type,
    source,
    reporter_name,
    target_name,
    server_origin,
    reason,
    evidence,
    is_anon
):
    """Route PLAYER reports to Moderation and STAFF reports to Leadership."""

    PLAYER_REPORT_CHANNEL_ID = "1459994350401487143"
    STAFF_REPORT_CHANNEL_ID = "1459996700256243834"

    report_type = (report_type or "PLAYER").upper()

    if report_type == "STAFF":
        channel_id = STAFF_REPORT_CHANNEL_ID
        title = f"🚨 STAFF REPORT #{report_id}"
        color = 10181046  # Purple
    else:
        channel_id = PLAYER_REPORT_CHANNEL_ID
        title = f"⚠️ PLAYER REPORT #{report_id}"
        color = 15158332  # Red

    displayed_reporter = "Anonymous User" if is_anon else reporter_name

    fields = [
        {
            "name": "Reported User",
            "value": target_name or "Unknown",
            "inline": True
        },
        {
            "name": "Server/Origin",
            "value": server_origin or "Not specified",
            "inline": True
        },
        {
            "name": "Reported By",
            "value": displayed_reporter,
            "inline": True
        },
        {
            "name": "Reason / Incident",
            "value": (reason or "No reason provided.")[:1024],
            "inline": False
        },
        {
            "name": "Evidence",
            "value": (evidence or "No evidence provided.")[:1024],
            "inline": False
        }
    ]

    embed = {
        "title": title,
        "color": color,
        "fields": fields,
        "footer": {
            "text": f"Source: {source} | ID: {report_id} | Status: OPEN"
        }
    }

    # Extra warning on anonymous reports
    if is_anon:
        embed["description"] = (
            "🔴 **THIS USER WOULD LIKE TO REMAIN ANONYMOUS** 🔴\n"
            "Please handle this ticket with discretion."
        )

    # Claim / Investigate button
    components = [
        {
            "type": 1,
            "components": [
                {
                    "type": 2,
                    "style": 1,
                    "label": "🔎 Claim / Investigate",
                    "custom_id": f"claim_report_{report_id}"
                }
            ]
        }
    ]

    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"

    headers = {
        "Authorization": f"Bot {BOT_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json={
                "embeds": [embed],
                "components": components
            },
            timeout=10
        )

        if response.ok:
            print(
                f"Report #{report_id} sent to "
                f"{'Leadership' if report_type == 'STAFF' else 'Moderation'}."
            )
            return True

        print(
            f"REPORT DISCORD ERROR #{report_id}: "
            f"{response.status_code} - {response.text}"
        )
        return False

    except requests.exceptions.RequestException as e:
        print(f"REPORT DISCORD CONNECTION ERROR #{report_id}: {e}")
        return False

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
        
        # 5. Resolve Discord roles into website capabilities.
        refresh_session_permissions(user_data['id'])
        
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

@app.route("/auth/hytale")
def hytale_login():
    # Hytale linking only happens after Discord login.
    if "user" not in session:
        return redirect(url_for("login"))

    if not HYTALE_CLIENT_ID or not HYTALE_CLIENT_SECRET:
        print("HYTALE ERROR: Missing client ID or client secret.")
        return "Hytale authentication is not configured.", 500

    # OAuth CSRF protection.
    state = secrets.token_urlsafe(32)

    # OIDC replay protection.
    nonce = secrets.token_urlsafe(32)

    # PKCE protection.
    verifier, challenge = create_pkce_pair()

    session["hytale_oauth_state"] = state
    session["hytale_oauth_nonce"] = nonce
    session["hytale_code_verifier"] = verifier

    params = {
        "client_id": HYTALE_CLIENT_ID,
        "redirect_uri": HYTALE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(HYTALE_SCOPES),
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256"
    }

    return redirect(
        HYTALE_AUTH_URL + "?" + urlencode(params)
    )

@app.route("/auth/hytale/callback")
def hytale_callback():
    if "user" not in session:
        return redirect(url_for("login"))

    # User denied access or Hytale returned an OAuth error.
    oauth_error = request.args.get("error")

    if oauth_error:
        print(
            "HYTALE OAUTH ERROR:",
            oauth_error,
            request.args.get("error_description")
        )

        return redirect(url_for("apply"))

    code = request.args.get("code")
    returned_state = request.args.get("state")

    expected_state = session.pop(
        "hytale_oauth_state",
        None
    )

    verifier = session.pop(
        "hytale_code_verifier",
        None
    )

    # Make sure this callback belongs to the login
    # request that we started.
    if (
        not code
        or not returned_state
        or not expected_state
        or not verifier
        or not secrets.compare_digest(
            returned_state,
            expected_state
        )
    ):
        return (
            "Invalid or expired Hytale authentication request.",
            400
        )

    try:
        # Exchange the authorization code.
        token_response = requests.post(
            HYTALE_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": HYTALE_REDIRECT_URI,
                "code_verifier": verifier
            },
            auth=(
                HYTALE_CLIENT_ID,
                HYTALE_CLIENT_SECRET
            ),
            headers={
                "Content-Type":
                    "application/x-www-form-urlencoded"
            },
            timeout=10
        )

        token_response.raise_for_status()

        token_data = token_response.json()

        access_token = token_data.get("access_token")

        if not access_token:
            raise RuntimeError(
                "Hytale did not return an access token."
            )

        # Retrieve the selected profile claims.
        #
        # Hytale exposes UserInfo through its OIDC service.
        userinfo_response = requests.get(
            HYTALE_USERINFO_URL,
            headers={
                "Authorization":
                    f"Bearer {access_token}"
            },
            timeout=10
        )

        userinfo_response.raise_for_status()

        claims = userinfo_response.json()

        # Keep this during our first test.
        # It prints claim NAMES, not secrets/tokens.
        print(
            "HYTALE CLAIM KEYS:",
            list(claims.keys())
        )

        profile = claims.get("profile") or {}
        profile_uuid = profile.get("uuid")
        profile_username = profile.get("username")
        owns_hytale = claims.get("game_ownership")

        if not profile_uuid or not profile_username:
            print(
                "HYTALE ERROR: Profile claim missing."
            )

            return (
                "Hytale login succeeded, but no "
                "game profile was selected.",
                400
            )

        # IMPORTANT:
        # Do NOT store the Hytale access token.
        #
        # We only need the verified identity.
        session["hytale_profile"] = {
            "hytale_uuid": str(profile_uuid),
            "hytale_name": str(profile_username),
            "owns_hytale": owns_hytale
        }

        # Persist the verified Discord <-> Hytale relationship. After this,
        # future application visits can resolve the account directly from DB.
        if not save_hytale_link(session["user"], profile_uuid, profile_username):
            return (
                "Hytale was verified, but Majikku could not save the account link.",
                500
            )

        session.pop("hytale_profile", None)
        return redirect(url_for("apply"))

    except requests.RequestException as e:
        print(f"HYTALE HTTP ERROR: {e}")

        if getattr(e, "response", None) is not None:
            print(
                "HYTALE RESPONSE:",
                e.response.text
            )

        return "Hytale authentication failed.", 500

    except Exception as e:
        print(f"HYTALE AUTH ERROR: {e}")

        return "Hytale authentication failed.", 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# --- ADMIN PANEL ---
@app.route('/admin')
@require_permission("admin.access")
def admin():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    posts, wiki_pages, pending_submissions = [], [], []
    counts = {"reports": 0, "applications": 0, "appeals": 0, "wiki": 0}
    try:
        if has_permission("content.announcements") or has_permission("content.events"):
            cursor.execute("SELECT * FROM announcements ORDER BY id DESC LIMIT 50")
            posts = cursor.fetchall()
        if has_permission("wiki.edit"):
            cursor.execute("SELECT * FROM wiki ORDER BY category, title")
            wiki_pages = cursor.fetchall()
        if has_permission("wiki.review"):
            cursor.execute("SELECT * FROM wiki_submissions WHERE status='PENDING' ORDER BY created_at DESC")
            pending_submissions = cursor.fetchall()
        for key, table in (("reports","reports"),("applications","applications"),("appeals","appeals"),("wiki","wiki")):
            try:
                cursor.execute(f"SELECT COUNT(*) AS total FROM {table}")
                counts[key] = cursor.fetchone()["total"]
            except mysql.connector.Error:
                counts[key] = 0
    finally:
        cursor.close(); conn.close()
    return render_template("admin.html", user=session.get("user"), announcements=posts, wiki_pages=wiki_pages, pending_submissions=pending_submissions, counts=counts)

@app.route('/admin/lookup')
@require_permission("admin.access")
def admin_lookup():
    q = (request.args.get("q") or "").strip()
    kind = (request.args.get("kind") or "reports").lower()
    allowed = {
        "reports": "lookup.reports",
        "applications": "lookup.applications",
        "appeals": "lookup.appeals",
        "players": "lookup.players",
        "punishments": "lookup.punishments",
    }
    if kind not in allowed or not has_permission(allowed[kind]):
        return "Forbidden", 403
    results = []
    if q:
        conn = get_db_connection(); cur = conn.cursor(dictionary=True)
        try:
            like = f"%{q}%"
            if kind == "reports":
                cur.execute("SELECT * FROM reports WHERE CAST(id AS CHAR)=%s OR target_name LIKE %s OR reporter_name LIKE %s ORDER BY id DESC LIMIT 50", (q.lstrip('#'), like, like))
            elif kind == "applications":
                cur.execute("SELECT * FROM applications WHERE CAST(id AS CHAR)=%s OR discord_username LIKE %s OR hytale_name LIKE %s OR hytale_uuid LIKE %s ORDER BY id DESC LIMIT 50", (q.lstrip('#'), like, like, like))
            elif kind == "appeals":
                cur.execute("SELECT * FROM appeals WHERE CAST(id AS CHAR)=%s OR discord_username LIKE %s OR hytale_name LIKE %s OR hytale_uuid LIKE %s OR punishment_id LIKE %s ORDER BY id DESC LIMIT 50", (q.lstrip('#'), like, like, like, like))
            elif kind == "players":
                cur.execute(f"SELECT * FROM `{GENERAL_DB}`.`account_links` WHERE discord_id=%s OR hytale_uuid LIKE %s OR hytale_name LIKE %s OR discord_username LIKE %s LIMIT 50", (q, like, like, like))
            else:
                cur.execute(f"SELECT p.*, pt.name AS punishment_type FROM `{GENERAL_DB}`.`punishments` p LEFT JOIN `{GENERAL_DB}`.`punishment_types` pt ON pt.id=p.type_id WHERE CAST(p.id AS CHAR)=%s OR p.player_id LIKE %s ORDER BY p.id DESC LIMIT 50", (q.lstrip('#'), like))
            results = cur.fetchall()
        except mysql.connector.Error as exc:
            print(f"Lookup error: {exc}")
        finally:
            cur.close(); conn.close()
    return render_template("admin_lookup.html", user=session.get("user"), kind=kind, query=q, results=results)

# --- ADMIN ACTIONS ---
@app.route('/admin/post', methods=['POST'])
@require_permission("content.announcements")
def admin_post():
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

@app.route('/admin/delete/<int:id>', methods=['POST'])
@require_permission("content.announcements")
def admin_delete(id):
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
    if 'user' not in session:
        return redirect(url_for('login'))

    hytale_data = get_application_hytale_identity()

    return render_template(
        'apply.html',
        user=session['user'],
        player=hytale_data
    )

@app.route('/submit', methods=['POST'])
def submit_application():
    if 'user' not in session: 
        return jsonify({'error': 'Unauthorized'}), 401
    
    # 1. Get Data Safely
    data = request.get_json(silent=True) or {}
    user = session['user']
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL") 
    
    if not webhook_url:
        print("Error: No Application Webhook URL found.")
        return jsonify({'success': False, 'error': 'Server configuration error.'}), 500

    # HELPER: Clean data to ensure no crashes
    def clean(val):
        if val is None: return "N/A"
        s = str(val).strip()
        if s == "": return "N/A"
        return s

    # Resolve Hytale identity on the server. The browser may display/send these
    # values, but it is not trusted as the source of account ownership.
    hytale_identity = get_application_hytale_identity()
    if not hytale_identity or not hytale_identity.get("hytale_uuid"):
        return jsonify({
            'success': False,
            'error': 'A verified Hytale account is required before applying.'
        }), 403

    # 2. Prep Basic Info
    team_name = clean(data.get('team', 'General'))
    discord_username = user.get('username', 'Unknown')
    discord_id = user.get('id', 'Unknown')
    hytale_name = clean(hytale_identity.get('hytale_name'))
    hytale_uuid = clean(hytale_identity.get('hytale_uuid'))
    
    avatar_url = None
    if user.get("avatar"):
        avatar_url = f"https://cdn.discordapp.com/avatars/{user['id']}/{user['avatar']}.png"

    # --- STEP 3: CREATE THE THREAD ---
    # We send JUST the header info first. This guarantees the thread is created.
    
    header_embed = {
        "title": f"📝 New Application: {team_name}",
        "color": 10182117, # Green-ish (Matches your screenshot)
        "thumbnail": {"url": avatar_url} if avatar_url else {},
        "fields": [
            {"name": "Discord User", "value": f"<@{discord_id}> ({discord_username})", "inline": False},
            {"name": "Hytale Name", "value": hytale_name, "inline": True},
            {"name": "Hytale UUID", "value": hytale_uuid, "inline": False},
            {"name": "Age", "value": clean(data.get('age')), "inline": True},
            {"name": "Timezone", "value": clean(data.get('timezone')), "inline": True},
            {"name": "Availability", "value": clean(data.get('availability')), "inline": True},
            {"name": "Languages", "value": clean(data.get('languages')), "inline": False},
        ],
        "footer": {"text": "Majikku Network Application System"}
    }

    # IMPORTANT: ?wait=true tells Discord to return the message data (so we get the Thread ID)
    thread_start_url = f"{webhook_url}?wait=true"
    
    start_payload = {
        "thread_name": f"APP: {discord_username} - {team_name}", # Required for Forum Channels
        "embeds": [header_embed]
    }

    thread_id = None

    try:
        # Send the Header
        resp = requests.post(thread_start_url, json=start_payload, timeout=10)
        
        if not resp.ok:
            print(f"⚠️ Thread Creation Error: {resp.text}")
            return jsonify({'success': False, 'error': f"Discord Error: {resp.text}"}), resp.status_code
            
        # Get the Thread ID from the response (channel_id of the message IS the thread id)
        thread_id = resp.json().get('channel_id')

        # Store the application as the source of truth for status/lookup.
        conn = get_db_connection(); cur = conn.cursor()
        try:
            cur.execute("""INSERT INTO applications
                (discord_id, discord_username, hytale_uuid, hytale_name, team, status, discord_thread_id)
                VALUES (%s,%s,%s,%s,%s,'PENDING',%s)""",
                (discord_id, discord_username, hytale_uuid, hytale_name, team_name, str(thread_id)))
            conn.commit(); application_id = cur.lastrowid
        finally:
            cur.close(); conn.close()

        # Post persistent workflow buttons into the application thread.
        if thread_id and BOT_TOKEN:
            requests.post(f"{API_ENDPOINT}/channels/{thread_id}/messages", headers={"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}, json={
                "content": f"Application #{application_id} • Status: **PENDING**",
                "components": [{"type":1,"components":[
                    {"type":2,"style":1,"label":"Claim Review","custom_id":f"application_claim_{application_id}"},
                    {"type":2,"style":3,"label":"Accept","custom_id":f"application_accept_{application_id}"},
                    {"type":2,"style":4,"label":"Deny","custom_id":f"application_deny_{application_id}"}
                ]}]
            }, timeout=10)
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Connection Error: {e}")
        return jsonify({'success': False, 'error': 'Failed to connect to Discord.'}), 500

    # --- STEP 4: SEND ANSWERS (Batched) ---
    # Now we post the answers into the thread we just created using ?thread_id=
    
    if thread_id:
        followup_url = f"{webhook_url}?thread_id={thread_id}"
        
        answers = data.get('answers', {})
        current_fields = []
        current_char_count = 0
        
        # Function to send a batch of fields
        def send_batch(fields):
            if not fields: return
            payload = {"embeds": [{"color": 10182117, "fields": fields}]}
            try:
                requests.post(followup_url, json=payload, timeout=10)
                time.sleep(0.5) # Be nice to Discord API rate limits
            except Exception as e:
                print(f"Error sending batch: {e}")

        # Loop through every answer
        for question, answer in answers.items():
            if not question or str(question).strip() == "": continue
            
            # 1. Truncate if user wrote an entire novel (Discord Limit is 1024)
            val_str = clean(answer)
            if len(val_str) > 1024:
                val_str = val_str[:1021] + "..."
            
            # 2. Check Batch Limits (Max 25 fields OR Max 6000 chars per embed)
            # We use a safe buffer of 5000 chars to be sure.
            if len(current_fields) >= 25 or (current_char_count + len(val_str) > 5000):
                send_batch(current_fields)
                current_fields = []
                current_char_count = 0
            
            current_fields.append({
                "name": str(question)[:256], 
                "value": val_str, 
                "inline": False
            })
            current_char_count += len(val_str)

        # 3. Send whatever is left
        if current_fields:
            send_batch(current_fields)

    return jsonify({'success': True, 'message': 'Application submitted successfully!'})

@app.route('/appeal')
def appeal():
    if 'user' not in session: return redirect(url_for('login'))
    hytale_data = get_application_hytale_identity()
    return render_template('appeal.html', user=session['user'], player=hytale_data)

@app.route('/submit-appeal', methods=['POST'])
def submit_appeal():
    if 'user' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    hytale_identity = get_application_hytale_identity()
    if not hytale_identity or not hytale_identity.get("hytale_uuid"):
        return jsonify({'success': False, 'error': 'A verified Hytale account is required.'}), 403

    required = ['platform', 'type', 'ban_reason', 'appeal_text']
    missing = [field for field in required if not str(data.get(field, '')).strip()]
    if missing:
        return jsonify({'success': False, 'error': 'Please complete all required appeal fields.'}), 400

    webhook_url = APPEALS_WEBHOOK_URL
    if not webhook_url:
        return jsonify({'success': False, 'error': 'Appeal system is not configured.'}), 500

    user = session['user']
    def clean(value, limit=1000):
        value = str(value or 'N/A').strip() or 'N/A'
        return value[:limit]

    embed = {
        "title": "⚖️ New Punishment Appeal",
        "color": 6619135,
        "fields": [
            {"name": "Discord User", "value": f"<@{user.get('id')}> ({clean(user.get('username'), 200)})", "inline": False},
            {"name": "Hytale Name", "value": clean(hytale_identity.get('hytale_name'), 200), "inline": True},
            {"name": "Hytale UUID", "value": clean(hytale_identity.get('hytale_uuid'), 200), "inline": False},
            {"name": "Platform", "value": clean(data.get('platform'), 200), "inline": True},
            {"name": "Punishment Type", "value": clean(data.get('type'), 200), "inline": True},
            {"name": "Punishment ID", "value": clean(data.get('punishment_id'), 200), "inline": True},
            {"name": "Reason Given", "value": clean(data.get('ban_reason')), "inline": False},
            {"name": "Appeal Statement", "value": clean(data.get('appeal_text')), "inline": False}
        ],
        "footer": {"text": "Majikku Network Appeal System"}
    }

    try:
        # wait=true gives us the Discord message/channel IDs for durable lookup.
        sep = "&" if "?" in webhook_url else "?"
        resp = requests.post(webhook_url + sep + "wait=true", json={"embeds": [embed]}, timeout=10)
        if not resp.ok:
            print(f"Appeal webhook error: {resp.status_code} {resp.text}")
            return jsonify({'success': False, 'error': 'The appeal could not be delivered. Please try again.'}), 502
        message = resp.json()
        conn = get_db_connection(); cur = conn.cursor()
        try:
            cur.execute("""INSERT INTO appeals
                (discord_id, discord_username, hytale_uuid, hytale_name, punishment_id, platform, punishment_type, reason, appeal_text, status, discord_channel_id, discord_message_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'PENDING',%s,%s)""",
                (str(user.get('id')), clean(user.get('username'),200), clean(hytale_identity.get('hytale_uuid'),200), clean(hytale_identity.get('hytale_name'),200), clean(data.get('punishment_id'),200), clean(data.get('platform'),200), clean(data.get('type'),200), clean(data.get('ban_reason')), clean(data.get('appeal_text')), str(message.get('channel_id')), str(message.get('id'))))
            conn.commit(); appeal_id = cur.lastrowid
        finally:
            cur.close(); conn.close()
        if message.get('channel_id') and BOT_TOKEN:
            requests.post(f"{API_ENDPOINT}/channels/{message['channel_id']}/messages", headers={"Authorization": f"Bot {BOT_TOKEN}", "Content-Type":"application/json"}, json={
                "content": f"Appeal #{appeal_id} • Status: **PENDING**",
                "components": [{"type":1,"components":[
                    {"type":2,"style":1,"label":"Claim Appeal","custom_id":f"appeal_claim_{appeal_id}"},
                    {"type":2,"style":3,"label":"Accept Appeal","custom_id":f"appeal_accept_{appeal_id}"},
                    {"type":2,"style":4,"label":"Deny Appeal","custom_id":f"appeal_deny_{appeal_id}"}
                ]}]
            }, timeout=10)
    except requests.exceptions.RequestException as exc:
        print(f"Appeal webhook connection error: {exc}")
        return jsonify({'success': False, 'error': 'The appeal service is temporarily unavailable.'}), 502

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
    
    return render_template('report.html', user=session['user'], initial_type=request.args.get('type', 'PLAYER').upper())

@app.route('/report/success/<int:report_id>')
def report_success(report_id):
    if 'user' not in session: return redirect(url_for('login'))
    return render_template('report_success.html', user=session['user'], report_id=report_id)


# --- NAVIGATION / SUPPORT ENDPOINTS ---
@app.route('/support/general')
def support_general():
    return render_template('support_general.html', user=session.get('user'))

@app.route('/support/purchase')
def support_purchase():
    return redirect("https://store.majikku.org")

@app.route('/report/player')
def report_player():
    if 'user' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('report', type='PLAYER'))

@app.route('/report/bug')
def report_bug():
    if 'user' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('report', type='BUG'))

@app.route('/stats')
def player_stats():
    return render_template(
        'coming_soon.html',
        title='Player Stats',
        message='Player profiles and live network statistics are being connected to Majikku account data.',
        action_url='/',
        action_label='Return Home',
        user=session.get('user')
    )

@app.route('/leaderboards')
def leaderboards():
    return render_template(
        'coming_soon.html',
        title='Leaderboards',
        message='Majikku leaderboards are being prepared for the network launch.',
        action_url='/events',
        action_label='View Events',
        user=session.get('user')
    )

@app.route('/punishments/history')
def punishment_history():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template(
        'coming_soon.html',
        title='Punishment History',
        message='This account endpoint is ready. The final step is connecting it to the shared punishment database so players only see their own verified history.',
        action_url='/appeal',
        action_label='Appeal a Punishment',
        user=session.get('user')
    )

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),'favicon.ico', mimetype='image/vnd.microsoft.icon')

if __name__ == '__main__':
    app.run(debug=os.getenv("FLASK_DEBUG", "").lower() in {"1", "true", "yes"})