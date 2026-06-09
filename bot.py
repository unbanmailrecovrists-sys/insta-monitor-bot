import os
import threading
import time
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import instaloader

# --- FLASK WEB SERVER FOR RENDER FREE PLAN ---
# Render ki Web Service ko active rakhne ke liye dummy server
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "Bot is running 24/7!", 200

def run_flask():
    # Render automatically PORT environment variable deta hai, default 10000 use karenge
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host="0.0.0.0", port=port)

# --- CONFIGURATION ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "AAPKA_TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID", "AAPKI_CHAT_ID")
INSTA_USER = os.environ.get("INSTA_USER", "AAPKA_INSTAGRAM_USERNAME")
INSTA_PASS = os.environ.get("INSTA_PASS", "AAPKA_INSTAGRAM_PASSWORD")

monitored_accounts = []  
status_tracker = {}  

# Instaloader Setup
L = instaloader.Instaloader()
try:
    print("Instagram me login ho raha hai...")
    L.login(INSTA_USER, INSTA_PASS)
    print("Instagram Login Successful!")
except Exception as e:
    print(f"Instagram Login Failed: {e}")

# --- HELPER FUNCTION FOR SCREENSHOT ---
def get_screenshot_url(username):
    target_url = f"https://www.instagram.com/{username}/"
    return f"https://api.apiflash.com/v1/urltoimage?access_key=7b7a136e9d6d4ba4bc7e4c7ba98797b5&url={target_url}&width=1280&height=1080&fresh=true"

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

async def check_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not monitored_accounts:
        await update.message.reply_text("📭 Pehle koi account add karein bhai! Use `/add <username>`")
        return
    await update.message.reply_text("🔄 Sabhi accounts ka live status aur cards fetch ho rahe hain...")
    for username in monitored_accounts:
        try:
            profile = instaloader.Profile.from_username(L.context, username)
            status_tracker[username] = True
            screenshot_img = get_screenshot_url(username)
            msg = (
                f"🟢 *@{username} is ACTIVE!*\n\n"
                f"👤 *Name:* {profile.full_name}\n"
                f"📝 *Bio:* {profile.biography if profile.biography else 'No Bio'}\n"
                f"📊 *Posts:* {profile.mediacount} | *Followers:* {profile.followers} | *Following:* {profile.followees}\n"
                f"🔗 [Profile Link](https://instagram.com/{username})"
            )
            await update.message.reply_photo(photo=screenshot_img, caption=msg, parse_mode="Markdown")
        except instaloader.exceptions.ProfileNotExistsException:
            status_tracker[username] = False
            await update.message.reply_text(f"🔴 `@{username}` abhi bhi Banned/Inactive hai.")
        except Exception as e:
            await update.message.reply_text(f"⚠️ Error checking `@{username}`: {e}")

# --- BACKGROUND MONITORING LOOP ---
def background_monitor(app):
    print("Background Monitoring Loop Started...")
    while True:
        if monitored_accounts:
            for username in list(monitored_accounts):
                try:
                    profile = instaloader.Profile.from_username(L.context, username)
                    if not status_tracker.get(username):
                        screenshot_img = get_screenshot_url(username)
                        msg = (
                            f"✅ *Username unbanned!*\n\n"
                            f"@{profile.username} is now active again — [View Profile](https://instagram.com/{username})\n\n"
                            f"👤 *Name:* {profile.full_name}\n"
                            f"📊 *Stats:*\n"
                            f"▪️ *Posts:* {profile.mediacount}\n"
                            f"▪️ *Followers:* {profile.followers}\n"
                            f"▪️ *Following:* {profile.followees}"
                        )
                        app.bot.send_photo(chat_id=CHAT_ID, photo=screenshot_img, caption=msg, parse_mode="Markdown")
                        status_tracker[username] = True
                except instaloader.exceptions.ProfileNotExistsException:
                    if status_tracker.get(username):
                        status_tracker[username] = False
                except Exception as e:
                    print(f"Loop error for {username}: {e}")
        time.sleep(60)

# --- MAIN FUNCTION ---
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("add", add_account))
    app.add_handler(CommandHandler("remove", remove_account))
    app.add_handler(CommandHandler("list", list_accounts))
    app.add_handler(CommandHandler("status", check_status))

    # 1. Background Bot Thread chalu karein
    monitor_thread = threading.Thread(target=background_monitor, args=(app,))
    monitor_thread.daemon = True
    monitor_thread.start()

    # 2. Flask Web Server ko alag thread me chalu karein Render ke liye
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    print("Telegram Bot & Flask Server are running...")
    app.run_polling()

if __name__ == "__main__":
    main()
