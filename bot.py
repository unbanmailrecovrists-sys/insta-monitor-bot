import os
import asyncio
import requests
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- FLASK WEB SERVER FOR RENDER ---
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "Telegram Bot is running 24/7!", 200

# --- CONFIGURATION ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "AAPKA_TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID", "AAPKI_CHAT_ID")
SEARCHAPI_KEY = os.environ.get("SEARCHAPI_KEY", "AAPKI_SEARCHAPI_KEY")

monitored_accounts = []  
status_tracker = {}     

# --- SEARCHAPI HELPER FUNCTION ---
def fetch_instagram_data(username):
    """SearchApi se raw data nikalna aur structure check karna"""
    url = "https://www.searchapi.io/api/v1/search"
    params = {
        "engine": "instagram_profile",
        "username": username,
        "api_key": SEARCHAPI_KEY
    }
    try:
        response = requests.get(url, params=params, timeout=15)
        print(f"[LOG] SearchApi Status for {username}: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            # Debugging ke liye logs me pura response print hoga
            print(f"[LOG] Response Data: {data}")
            
            # Agar direct 'profile' key milti hai
            if "profile" in data and data["profile"]:
                profile_data = data["profile"]
                return {
                    "active": True,
                    "name": profile_data.get("name") or profile_data.get("full_name") or username,
                    "posts": profile_data.get("posts") or profile_data.get("posts_count") or 0,
                    "followers": profile_data.get("followers") or profile_data.get("followers_count") or 0,
                    "following": profile_data.get("following") or profile_data.get("following_count") or 0,
                    "pfp": profile_data.get("profile_pic") or profile_data.get("profile_pic_url") or "",
                    "bio": profile_data.get("bio") or profile_data.get("biography") or "No Bio"
                }
        return {"active": False}
    except Exception as e:
        print(f"[ERROR] Fetch failed: {e}")
        return {"active": False}

# --- TELEGRAM COMMAND HANDLERS ---

async def add_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Please provide a username. Example: `/add zuck`", parse_mode="Markdown")
        return
    username = context.args[0].lower().replace("@", "")
    if username in monitored_accounts:
        await update.message.reply_text(f"⚠️ `@{username}` pehle se list me hai.")
    else:
        monitored_accounts.append(username)
        status_tracker[username] = False  
        await update.message.reply_text(f"✅ `@{username}` ko monitoring list me add kar diya gaya hai!")

async def remove_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Please provide a username. Example: `/remove zuck`", parse_mode="Markdown")
        return
    username = context.args[0].lower().replace("@", "")
    if username in monitored_accounts:
        monitored_accounts.remove(username)
        if username in status_tracker:
            del status_tracker[username]
        await update.message.reply_text(f"❌ `@{username}` ko list se hata diya gaya hai.")
    else:
        await update.message.reply_text(f"⚠️ `@{username}` list me nahi hai.")

async def list_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not monitored_accounts:
        await update.message.reply_text("📭 Monitoring list abhi khaali hai. Use `/add <username>`")
        return
    msg = "📋 *Current Monitored Accounts:*\n\n"
    for i, user in enumerate(monitored_accounts, 1):
        status = "🟢 Active" if status_tracker.get(user) else "🔴 Banned/Inactive"
        msg += f"{i}. `@{user}` — {status}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

# NAYI COMMAND: /check username (Instant single profile check karne ke liye)
async def check_single_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Username bhejye bhai. Example: `/check zuck`")
        return
    
    username = context.args[0].lower().replace("@", "")
    await update.message.reply_text(f"🔄 `@ {username}` ka live data fetch ho raha hai...")
    
    loop = asyncio.get_event_loop()
    user_data = await loop.run_in_executor(None, fetch_instagram_data, username)
    
    if user_data["active"]:
        msg = (
            f"🟢 *@{username} is ACTIVE!*\n\n"
            f"👤 *Name:* {user_data['name']}\n"
            f"📝 *Bio:* {user_data['bio']}\n"
            f"📊 *Posts:* {user_data['posts']} | *Followers:* {user_data['followers']} | *Following:* {user_data['following']}\n\n"
            f"🔗 [Profile Link](https://instagram.com/{username})"
        )
        if user_data["pfp"]:
            await update.message.reply_photo(photo=user_data["pfp"], caption=msg, parse_mode="Markdown")
        else:
            await update.message.reply_text(msg, parse_mode="Markdown")
    else:
        await update.message.reply_text(f"🔴 `@{username}` Banned hai ya SearchApi key configuration check karein.")

async def check_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not monitored_accounts:
        await update.message.reply_text("📭 Pehle koi account add karein bhai! Use `/add <username>`")
        return
    await update.message.reply_text("🔄 Sabhi accounts ka status check ho raha hai...")
    
    for username in monitored_accounts:
        loop = asyncio.get_event_loop()
        user_data = await loop.run_in_executor(None, fetch_instagram_data, username)
        
        if user_data["active"]:
            status_tracker[username] = True
            msg = (
                f"🟢 *@{username} is ACTIVE!*\n\n"
                f"👤 *Name:* {user_data['name']}\n"
                f"📊 *Posts:* {user_data['posts']} | *Followers:* {user_data['followers']}\n"
            )
            await update.message.reply_text(msg, parse_mode="Markdown")
        else:
            status_tracker[username] = False
            await update.message.reply_text(f"🔴 `@{username}` abhi bhi Banned ya Inactive hai.")

# --- ASYNC BACKGROUND MONITORING LOOP ---
async def background_monitor(app):
    print("Background Monitoring Loop Started...")
    while True:
        if monitored_accounts:
            for username in list(monitored_accounts):
                loop = asyncio.get_event_loop()
                user_data = await loop.run_in_executor(None, fetch_instagram_data, username)
                
                if user_data["active"] and not status_tracker.get(username):
                    msg = (
                        f"✅ *ALERT: Username unbanned!*\n\n"
                        f"@{username} ab active ho gaya hai!\n"
                        f"🔗 [View Profile](https://instagram.com/{username})"
                    )
                    try:
                        await app.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
                    except Exception as e:
                        print(f"Alert send failed: {e}")
                    status_tracker[username] = True
                elif not user_data["active"] and status_tracker.get(username):
                    status_tracker[username] = False
                    
        await asyncio.sleep(60)

async def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("add", add_account))
    app.add_handler(CommandHandler("remove", remove_account))
    app.add_handler(CommandHandler("list", list_accounts))
    app.add_handler(CommandHandler("status", check_status))
    app.add_handler(CommandHandler("check", check_single_account)) # /check register ho gayi

    import threading
    port = int(os.environ.get("PORT", 10000))
    flask_thread = threading.Thread(target=lambda: app_flask.run(host="0.0.0.0", port=port, use_reloader=False))
    flask_thread.daemon = True
    flask_thread.start()

    await app.initialize()
    await app.start()
    asyncio.create_task(background_monitor(app))
    
    print("Telegram Bot Running Perfectly...")
    await app.updater.start_polling()
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())