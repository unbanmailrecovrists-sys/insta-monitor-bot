import os
import asyncio
import requests
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "Telegram Bot is running 24/7!", 200

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "AAPKA_TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID", "AAPKI_CHAT_ID")
SEARCHAPI_KEY = os.environ.get("SEARCHAPI_KEY", "")

monitored_accounts = []  
status_tracker = {}     

def fetch_instagram_data(username):
    """Direct absolute URL manipulation authentication bypass ke liye"""
    if not SEARCHAPI_KEY or SEARCHAPI_KEY == "AAPKI_SEARCHAPI_KEY":
        print("[ERROR] SearchApi Key set nahi hai Render dashboard par!")
        return {"active": False, "reason": "Missing API Key"}

    # Absolute query parameter mapping jo documentation me di gayi hai
    url = f"https://www.searchapi.io/api/v1/search?engine=instagram_profile&username={username}&api_key={SEARCHAPI_KEY}"
    
    try:
        response = requests.get(url, timeout=15)
        print(f"[LOG] Raw Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
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
            else:
                print(f"[LOG] Profile key nahi mili. Raw response: {data}")
        return {"active": False, "reason": f"Status {response.status_code}"}
    except Exception as e:
        print(f"[ERROR] Request exception: {e}")
        return {"active": False, "reason": "Exception"}

async def add_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Please provide a username. Example: `/add zuck`")
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
        await update.message.reply_text("❌ Please provide a username.")
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
        await update.message.reply_text("📭 Monitoring list abhi khaali hai.")
        return
    msg = "📋 *Current Monitored Accounts:*\n\n"
    for i, user in enumerate(monitored_accounts, 1):
        status = "🟢 Active" if status_tracker.get(user) else "🔴 Banned/Inactive"
        msg += f"{i}. `@{user}` — {status}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def check_single_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Username bhejye bhai. Example: `/check instagram`")
        return
    
    username = context.args[0].lower().replace("@", "")
    await update.message.reply_text(f"🔄 `@{username}` ka live data fetch ho raha hai...")
    
    loop = asyncio.get_event_loop()
    user_data = await loop.run_in_executor(None, fetch_instagram_data, username)
    
    if user_data.get("active"):
        status_tracker[username] = True
        msg = (
            f"🟢 *@{username} is ACTIVE!*\n\n"
            f"👤 *Name:* {user_data['name']}\n"
            f"📝 *Bio:* {user_data['bio']}\n"
            f"📊 *Posts:* {user_data['posts']} | *Followers:* {user_data['followers']} | *Following:* {user_data['following']}\n\n"
            f"🔗 [Profile Link](https://instagram.com/{username})"
        )
        try:
            if user_data["pfp"]:
                await update.message.reply_photo(photo=user_data["pfp"], caption=msg, parse_mode="Markdown")
            else:
                await update.message.reply_text(msg, parse_mode="Markdown")
        except:
            await update.message.reply_text(msg, parse_mode="Markdown")
    else:
        reason = user_data.get("reason", "Unknown")
        await update.message.reply_text(f"🔴 `@{username}` Active nahi mila.\n⚠️ Reason: {reason}\n*(Tip: Agar reason Status 401/403 hai toh Render par API key check karein)*")

async def check_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not monitored_accounts:
        await update.message.reply_text("📭 List khaali hai bhai!")
        return
    await update.message.reply_text("🔄 Status check ho raha hai...")
    for username in monitored_accounts:
        loop = asyncio.get_event_loop()
        user_data = await loop.run_in_executor(None, fetch_instagram_data, username)
        if user_data.get("active"):
            status_tracker[username] = True
            await update.message.reply_text(f"🟢 `@{username}` is ACTIVE!")
        else:
            status_tracker[username] = False
            await update.message.reply_text(f"🔴 `@{username}` Inactive/Banned.")

async def background_monitor(app):
    while True:
        if monitored_accounts:
            for username in list(monitored_accounts):
                loop = asyncio.get_event_loop()
                user_data = await loop.run_in_executor(None, fetch_instagram_data, username)
                if user_data.get("active") and not status_tracker.get(username):
                    msg = f"✅ *ALERT: @{username} unbanned!* — [View](https://instagram.com/{username})"
                    try:
                        await app.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
                    except: pass
                    status_tracker[username] = True
                elif not user_data.get("active") and status_tracker.get(username):
                    status_tracker[username] = False
        await asyncio.sleep(60)

async def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("add", add_account))
    app.add_handler(CommandHandler("remove", remove_account))
    app.add_handler(CommandHandler("list", list_accounts))
    app.add_handler(CommandHandler("status", check_status))
    app.add_handler(CommandHandler("check", check_single_account))

    import threading
    port = int(os.environ.get("PORT", 10000))
    flask_thread = threading.Thread(target=lambda: app_flask.run(host="0.0.0.0", port=port, use_reloader=False))
    flask_thread.daemon = True
    flask_thread.start()

    await app.initialize()
    await app.start()
    asyncio.create_task(background_monitor(app))
    await app.updater.start_polling()
    while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())