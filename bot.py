import os
import threading
import time
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import instaloader

# --- CONFIGURATION ---
# Render Environment Variables se values aayengi (Ya aap direct yahan string daal sakte hain)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "AAPKA_TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID", "AAPKI_CHAT_ID")
INSTA_USER = os.environ.get("INSTA_USER", "AAPKA_INSTAGRAM_USERNAME")
INSTA_PASS = os.environ.get("INSTA_PASS", "AAPKA_INSTAGRAM_PASSWORD")

# Monitor karne wale accounts ki list aur unka current status
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
    """Instagram profile ka live screenshot generate karne ka url"""
    target_url = f"https://www.instagram.com/{username}/"
    # ApiFlash ki free key use kar rahe hain jo dynamic screenshot render karegi
    return f"https://api.apiflash.com/v1/urltoimage?access_key=7b7a136e9d6d4ba4bc7e4c7ba98797b5&url={target_url}&width=1280&height=1080&fresh=true"

# --- TELEGRAM COMMAND HANDLERS ---

# 1. /add username
async def add_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❌ Please provide a username. Example: `/add zuck`",
            parse_mode="Markdown",
        )
        return

    username = context.args[0].lower().replace("@", "")

    if username in monitored_accounts:
        await update.message.reply_text(f"⚠️ `@{username}` pehle se list me hai.")
    else:
        monitored_accounts.append(username)
        status_tracker[username] = False  
        await update.message.reply_text(
            f"✅ `@{username}` ko monitoring list me add kar diya gaya hai!"
        )

# 2. /remove username
async def remove_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "❌ Please provide a username. Example: `/remove zuck`",
            parse_mode="Markdown",
        )
        return

    username = context.args[0].lower().replace("@", "")

    if username in monitored_accounts:
        monitored_accounts.remove(username)
        if username in status_tracker:
            del status_tracker[username]
        await update.message.reply_text(
            f"❌ `@{username}` ko list se hata diya gaya hai."
        )
    else:
        await update.message.reply_text(f"⚠️ `@{username}` list me nahi hai.")

# 3. /list
async def list_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not monitored_accounts:
        await update.message.reply_text(
            "📭 Monitoring list abhi khaali hai. Use `/add <username>`"
        )
        return

    msg = "📋 *Current Monitored Accounts:*\n\n"
    for i, user in enumerate(monitored_accounts, 1):
        status = "🟢 Active" if status_tracker.get(user) else "🔴 Banned/Inactive"
        msg += f"{i}. `@{user}` — {status}\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

# 4. /status (Ab yeh text ke saath real profile screenshot bhejega)
async def check_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not monitored_accounts:
        await update.message.reply_text(
            "📭 Pehle koi account add karein bhai! Use `/add <username>`"
        )
        return

    await update.message.reply_text("🔄 Sabhi accounts ka live status aur cards fetch ho rahe hain...")

    for username in monitored_accounts:
        try:
            profile = instaloader.Profile.from_username(L.context, username)
            status_tracker[username] = True
            
            # Live card screenshot URL nikalna
            screenshot_img = get_screenshot_url(username)

            msg = (
                f"🟢 *@{username} is ACTIVE!*\n\n"
                f"👤 *Name:* {profile.full_name}\n"
                f"📝 *Bio:* {profile.biography if profile.biography else 'No Bio'}\n"
                f"📊 *Posts:* {profile.mediacount} | *Followers:* {profile.followers} | *Following:* {profile.followees}\n"
                f"🔗 [Profile Link](https://instagram.com/{username})"
            )
            
            # Image bhej rahe hain text caption ke saath
            await update.message.reply_photo(photo=screenshot_img, caption=msg, parse_mode="Markdown")

        except instaloader.exceptions.ProfileNotExistsException:
            status_tracker[username] = False
            await update.message.reply_text(
                f"🔴 `@{username}` abhi bhi Banned/Inactive hai."
            )
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

                    # Agar pehle inactive/banned tha aur ab active ho gaya (Unban Alert!)
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
                        
                        # Background alert me card photo bhej rahe hain
                        app.bot.send_photo(chat_id=CHAT_ID, photo=screenshot_img, caption=msg, parse_mode="Markdown")
                        status_tracker[username] = True

                except instaloader.exceptions.ProfileNotExistsException:
                    if status_tracker.get(username):
                        status_tracker[username] = False
                except Exception as e:
                    print(f"Loop error for {username}: {e}")

        # Har 60 seconds me check karega
        time.sleep(60)

# --- MAIN FUNCTION ---
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Commands register ho rahe hain standard '/' ke saath
    app.add_handler(CommandHandler("add", add_account))
    app.add_handler(CommandHandler("remove", remove_account))
    app.add_handler(CommandHandler("list", list_accounts))
    app.add_handler(CommandHandler("status", check_status))

    monitor_thread = threading.Thread(target=background_monitor, args=(app,))
    monitor_thread.daemon = True
    monitor_thread.start()

    print("Telegram Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()

