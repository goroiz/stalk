import os
import time
import requests
from datetime import datetime, timezone

# === CONFIG dari Environment Variables ===
ROBLOX_USER_ID = os.getenv("ROBLOX_USER_ID")          # isi di Koyeb: 7689970445
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")  # isi di Koyeb: webhook discord
POLL_INTERVAL_SEC = int(os.getenv("POLL_INTERVAL_SEC", "60"))  # default 60 detik

SESSION = requests.Session()
SESSION.headers.update({
    "Accept": "application/json",
    "User-Agent": "roblox-status-watcher/1.0"
})

# cache sederhana biar gak spam webhook
last_presence = None   # dict dengan keys: type, placeId, lastLocation
last_description = None

PRESENCE_MAP = {
    0: "Offline",
    1: "Online",
    2: "In-Game",
    3: "In-Studio"
}

def now_utc_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def get_presence(user_id: str):
    url = "https://presence.roblox.com/v1/presence/users"
    resp = SESSION.post(url, json={"userIds": [int(user_id)]}, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    pres_list = data.get("userPresences", [])
    if not pres_list:
        return {"type": "Unknown", "placeId": None, "lastLocation": None}

    p = pres_list[0]
    ptype = PRESENCE_MAP.get(p.get("userPresenceType", -1), "Unknown")
    return {
        "type": ptype,
        "placeId": p.get("placeId"),
        "lastLocation": p.get("lastLocation"),
    }

def get_profile(user_id: str):
    url = f"https://users.roblox.com/v1/users/{int(user_id)}"
    resp = SESSION.get(url, timeout=15)
    resp.raise_for_status()
    j = resp.json()
    return {
        "name": j.get("name"),
        "displayName": j.get("displayName"),
        "description": j.get("description") or ""
    }

def send_discord(content=None, embed=None):
    payload = {}
    if content:
        payload["content"] = content
    if embed:
        payload["embeds"] = [embed]

    if not DISCORD_WEBHOOK_URL:
        print("⚠️ DISCORD_WEBHOOK_URL not set")
        return

    r = SESSION.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
    if r.status_code // 100 != 2:
        print(f"[{now_utc_iso()}] Webhook failed {r.status_code}: {r.text[:200]}")

def build_presence_embed(profile, presence):
    title = f"{profile['displayName']} (@{profile['name']})"
    desc_lines = [f"**Presence**: {presence['type']}"]
    if presence.get("lastLocation"):
        desc_lines.append(f"**Location**: {presence['lastLocation']}")
    if presence.get("placeId"):
        place = presence["placeId"]
        desc_lines.append(f"[Open Place](https://www.roblox.com/games/{place})")

    embed = {
        "title": title,
        "description": "\n".join(desc_lines),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": "Roblox Status Watcher"},
        "color": 5814783
    }
    return embed

def build_description_embed(profile, old_desc, new_desc):
    title = f"{profile['displayName']} (@{profile['name']}) updated About"
    embed = {
        "title": title,
        "fields": [
            {"name": "Old", "value": old_desc if old_desc.strip() else "_(empty)_", "inline": False},
            {"name": "New", "value": new_desc if new_desc.strip() else "_(empty)_", "inline": False},
        ],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": "stop ganbi dont be crazy😭"},
        "color": 15105570
    }
    return embed

def main_loop():
    global last_presence, last_description

    if not ROBLOX_USER_ID or not DISCORD_WEBHOOK_URL:
        raise SystemExit("Set env ROBLOX_USER_ID & DISCORD_WEBHOOK_URL")

    try:
        profile = get_profile(ROBLOX_USER_ID)
        presence = get_presence(ROBLOX_USER_ID)
        last_presence = presence
        last_description = profile["description"]
        send_discord(embed={
            "title": f"Watcher started for {profile['displayName']} (@{profile['name']})",
            "description": f"Initial presence: **{presence['type']}**",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "color": 3447003
        })
    except Exception as e:
        print(f"[{now_utc_iso()}] Init error: {e}")

    while True:
        try:
            profile = get_profile(ROBLOX_USER_ID)
            presence = get_presence(ROBLOX_USER_ID)

            if last_presence is None or (
                presence["type"] != last_presence["type"]
                or presence.get("placeId") != last_presence.get("placeId")
                or presence.get("lastLocation") != last_presence.get("lastLocation")
            ):
                send_discord(embed=build_presence_embed(profile, presence))
                last_presence = presence

            desc_now = profile["description"]
            if last_description is None or desc_now != last_description:
                if last_description is not None:
                    send_discord(embed=build_description_embed(profile, last_description, desc_now))
                last_description = desc_now

        except requests.HTTPError as http_err:
            print(f"[{now_utc_iso()}] HTTP error: {http_err}")
        except Exception as e:
            print(f"[{now_utc_iso()}] Loop error: {e}")

        time.sleep(POLL_INTERVAL_SEC)

if __name__ == "__main__":
    main_loop()
