from flask import Flask, redirect, request, render_template, session, url_for, jsonify
import requests
import os
import time
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(24))

# --- DISCORD CONFIG ---
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
BOT_TOKEN = os.getenv("BOT_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

REDIRECT_URI = "http://127.0.0.1:5000/callback" 
API_ENDPOINT = 'https://discord.com/api/v10'

# --- STAFF PAGE CONFIGURATION ---
# We define "Groups" (The Headers) and the "Roles" inside them (The Cards).
# The order here determines the order on the website.

# --- STAFF PAGE CONFIGURATION ---

STAFF_GROUPS = [
    # 1. LEADERSHIP
    {
        "name": "Leadership",
        "roles": [
            {"id": "1207778262378487918", "title": "Owner"},
            {"id": "1207778264819572836", "title": "Administrator"}
        ]
    },

    # 2. TEAM LEADS (The Summary Section)
    {
        "name": "Team Leads",
        "roles": [
            #{"id": "1207778271811346482", "title": "Staff Manager"},
            #{"id": "1452499232849268767", "title": "General Lead"},
            {"id": "1207778273166098502", "title": "Lead Developer"},
            {"id": "1207778274642759760", "title": "Lead Builder"},
            {"id": "1452499234103234690", "title": "Lead Modeler"},
            {"id": "1207778273791184927", "title": "Lead Coordinator"},
            {"id": "1392535920665690142", "title": "Lead Artist"},
            {"id": "1452004814375616765", "title": "Lead Storyteller"},
            {"id": "1392535925606715533", "title": "Lead Tester"}
        ]
    },

    # 3. DEPARTMENTS (Now including Leads at the top!)
    {
        "name": "Development Team",
        "roles": [
            {"id": "1207778273166098502", "title": "Lead Developer"}, # Added here
            {"id": "1207778264190292052", "title": "Developer"},
            {"id": "1392535924918714408", "title": "Jr. Developer"}
        ]
    },
    {
        "name": "Build Team",
        "roles": [
            {"id": "1207778274642759760", "title": "Lead Builder"}, # Added here#
            {"id": "1452499233591791777", "title": "Senior Builder"},
            {"id": "1207778275334553640", "title": "Builder"}
        ]
    },
    {
        "name": "Modeling Team",
        "roles": [
            {"id": "1452499234103234690", "title": "Lead Modeler"}, # Added here
            {"id": "1452499235332292801", "title": "Senior Modeler"},
            {"id": "1452499236091592806", "title": "Modeler"}
        ]
    },
    {
        "name": "Coordinator Team",
        "roles": [
            {"id": "1207778273791184927", "title": "Lead Coordinator"}, # Added here
            {"id": "1392535922331095051", "title": "Event Coordinator"},
            {"id": "1392535907965341806", "title": "Social Coordinator"}
        ]
    },
    {
        "name": "Art & Story",
        "roles": [
            {"id": "1392535920665690142", "title": "Lead Artist"},      # Added here
            {"id": "1452004814375616765", "title": "Lead Storyteller"}, # Added here
            {"id": "1392535921487908945", "title": "Artist"},
            {"id": "1452004927441342616", "title": "Storyteller"}
        ]
    },
    {
        "name": "Quality Assurance",
        "roles": [
            {"id": "1392535925606715533", "title": "Lead Tester"}, # Added here
            {"id": "1452499234720055316", "title": "Senior Tester"},
            {"id": "1392535923203379260", "title": "Tester"}
        ]
    },
    {
        "name": "Moderation Team",
        "roles": [
            {"id": "1207778265008439467", "title": "Senior Moderator"},
            {"id": "1207778265931055204", "title": "Moderator"},
            {"id": "1207778266572918904", "title": "Helper"}
        ]
    }
]

staff_cache = {"data": None, "timestamp": 0}

def get_staff_data():
    if time.time() - staff_cache["timestamp"] < 300 and staff_cache["data"]:
        return staff_cache["data"]

    headers = {"Authorization": f"Bot {BOT_TOKEN}"}
    response = requests.get(f"{API_ENDPOINT}/guilds/{GUILD_ID}/members?limit=1000", headers=headers)
    
    if response.status_code != 200:
        print(f"Error fetching staff: {response.text}")
        return {}

    members = response.json()
    
    # Prepare the result structure: {"Leadership": [], "Build Team": [], ...}
    grouped_staff = {group["name"]: [] for group in STAFF_GROUPS}
    
    for member in members:
        user = member["user"]
        user_roles = member["roles"] # The user's list of role IDs
        
        # Calculate avatar once
        avatar_url = "https://cdn.discordapp.com/embed/avatars/0.png"
        if user.get("avatar"):
            avatar_url = f"https://cdn.discordapp.com/avatars/{user['id']}/{user['avatar']}.png"

        # Check every Group to see if this user belongs in it
        for group in STAFF_GROUPS:
            
            # Check roles in order (Highest rank in the group takes priority)
            found_title_in_this_group = None
            
            for role_def in group["roles"]:
                if role_def["id"] in user_roles:
                    found_title_in_this_group = role_def["title"]
                    break # Stop checking this group (we found their highest rank here)
            
            if found_title_in_this_group:
                staff_member = {
                    "name": member.get("nick") or user["username"],
                    "avatar": avatar_url,
                    "role": found_title_in_this_group
                }
                grouped_staff[group["name"]].append(staff_member)

    staff_cache["data"] = grouped_staff
    staff_cache["timestamp"] = time.time()
    
    return grouped_staff

# --- ROUTES ---

@app.route('/')
def home():
    return render_template('home.html', user=session.get('user'))

@app.route('/info')
def info():
    return render_template('info.html', user=session.get('user'))

@app.route('/staff')
def staff():
    grouped_staff = get_staff_data()
    # We pass STAFF_GROUPS so the HTML knows the correct order to display sections
    return render_template('staff.html', staff_groups=grouped_staff, group_order=STAFF_GROUPS, user=session.get('user'))

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
    token_response = requests.post(f'{API_ENDPOINT}/oauth2/token', data=data, headers=headers)
    access_token = token_response.json().get('access_token')
    user_response = requests.get(f'{API_ENDPOINT}/users/@me', headers={'Authorization': f'Bearer {access_token}'})
    session['user'] = user_response.json()
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/apply')
def apply():
    if 'user' not in session: return redirect(url_for('login'))
    return render_template('apply.html', user=session['user'])

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
        "color": 10182117,
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

    payload = {
        "thread_name": f"APP - {team_name} - {data.get('hytale_name', user['username'])}",
        "embeds": [embed]
    }
    requests.post(DISCORD_WEBHOOK_URL, json=payload)
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True)