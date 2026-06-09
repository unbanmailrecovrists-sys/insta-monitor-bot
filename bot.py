import os
import asyncio
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- FLASK WEB SERVER ---
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "Bot is running 24/7!", 200

# --- CONFIGURATION ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "AAPKA_TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID", "AAPKI_CHAT_ID")
INSTA_USER = os.environ.get("INSTA_USER", "AAPKA_INSTAGRAM_USERNAME")
INSTA_PASS = os.environ.get("INSTA_PASS", "AAPKA_INSTAGRAM_PASSWORD")

monitored_accounts = []  
status_tracker = {}  

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

# --- ASYNC BACKGROUND MONITORING LOOP ---
async def background_monitor(app):
    print("Background Monitoring Loop Started...")
    while True:
        if monitored_accounts:
            for username in list(monitored_accounts):
                try:
                    # Async function ke andar loop ko block hone se bachane ke liye run_in_executor use karenge
                    loop = asyncio.get_event_loop()
                    profile = await loop.run_in_executor(None, instaloader.Profile.from_username, L.context, username)
                    
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
                        await app.bot.send_photo(chat_id=CHAT_ID, photo=screenshot_img, caption=msg, parse_mode="Markdown")
                        status_tracker[username] = True
                except instaloader.exceptions.ProfileNotExistsException:
                    if status_tracker.get(username):
                        status_tracker[username] = False
                except Exception as e:
                    print(f"Loop error for {username}: {e}")
        await asyncio.sleep(60)  # Non-blocking sleep

# --- MAIN ASYNC FUNCTION ---
async def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("add", add_account))
    app.add_handler(CommandHandler("remove", remove_account))
    app.add_handler(CommandHandler("list", list_accounts))
    app.add_handler(CommandHandler("status", check_status))

    # Flask ko bina thread block kiye background me start karne ke liye hypercorn/werkzeug setup ki jagah standard threading background me daalenge jo event loop se alag ho
    import threading
    port = int(os.environ.get("PORT", 10000))
    flask_thread = threading.Thread(target=lambda: app_flask.run(host="0.0.0.0", port=port, use_reloader=False))
    flask_thread.daemon = True
    flask_thread.start()

    # Bot initialized aur background task register ho raha hai
    await app.initialize()
    await app.start()
    
    # Background monitor task ko loop me chalu karna
    asyncio.create_task(background_monitor(app))
    
    print("Telegram Bot & Flask Server are running perfectly...")
    await app.updater.start_polling()
    
    # Bot ko continuously chalte rehne dene ke liye sleep loop
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    # Naye python versions ke liye clean asyncio run
    asyncio.run(main())
