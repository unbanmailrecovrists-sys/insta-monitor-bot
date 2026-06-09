import os
import asyncio
import requests
from flask import Flask
import discord
from discord.ext import commands

app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "Discord Bot is running 24/7!", 200

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "AAPKA_DISCORD_BOT_TOKEN")
SEARCHAPI_KEY = os.environ.get("SEARCHAPI_KEY", "AAPKI_SEARCHAPI_KEY")

intents = discord.Intents.default()
intents.message_content = True  
bot = commands.Bot(command_prefix="!", intents=intents)

monitored_accounts = {}  
status_tracker = {}     

def fetch_instagram_data(username):
    url = "https://www.searchapi.io/api/v1/search"
    params = {
        "engine": "instagram_profile",
        "username": username,
        "api_key": SEARCHAPI_KEY
    }
    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            if "profile" in data:
                profile_data = data["profile"]
                return {
                    "active": True,
                    "name": profile_data.get("name", username),
                    "posts": profile_data.get("posts", 0),
                    "followers": profile_data.get("followers", 0),
                    "following": profile_data.get("following", 0),
                    "pfp": profile_data.get("profile_pic", ""),
                    "bio": profile_data.get("bio", "No Bio")
                }
        return {"active": False}
    except:
        return {"active": False}

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} with Official SearchApi Spec ✅")
    bot.loop.create_task(background_monitor())

@bot.command(name="monitor")
async def monitor_account(ctx, username: str):
    username = username.lower().replace("@", "")
    if username in monitored_accounts:
        await ctx.send(f"⚠️ `@{username}` pehle se list mein hai.")
        return
    monitored_accounts[username] = [ctx.channel.id, ctx.author.mention]
    status_tracker[username] = False
    await ctx.send(f"🟢 **Started monitoring `@{username}`**\nOnce it's unbanned, I'll send a premium card alert here!")

@bot.command(name="check")
async def check_account(ctx, username: str):
    username = username.lower().replace("@", "")
    await ctx.send("🔄 SearchApi se live profile data aur card fetch ho raha hai...")
    
    loop = asyncio.get_event_loop()
    user_data = await loop.run_in_executor(None, fetch_instagram_data, username)
    
    if user_data["active"]:
        status_tracker[username] = True
        embed = discord.Embed(title="Khof Monitor BOT", color=discord.Color.green())
        embed.add_field(name="Instagram Account", value=f"@{username}", inline=False)
        embed.add_field(name="Name", value=user_data["name"], inline=True)
        embed.add_field(name="Posts", value=str(user_data["posts"]), inline=True)
        embed.add_field(name="Followers", value=str(user_data["followers"]), inline=True)
        embed.add_field(name="Following", value=str(user_data["following"]), inline=True)
        embed.add_field(name="Status", value="✅ Account is Active", inline=False)
        if user_data["pfp"]:
            embed.set_thumbnail(url=user_data["pfp"])
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"❌ Account `@{username}` abhi bhi Banned ya Inactive hai.")

async def background_monitor():
    print("Background Monitoring Loop Started...")
    await bot.wait_until_ready()
    while not bot.is_closed():
        if monitored_accounts:
            for username, details in list(monitored_accounts.items()):
                channel_id, user_mention = details
                channel = bot.get_channel(channel_id)
                if not channel: continue
                    
                loop = asyncio.get_event_loop()
                user_data = await loop.run_in_executor(None, fetch_instagram_data, username)
                
                if user_data["active"] and not status_tracker.get(username):
                    embed = discord.Embed(title="Khof Monitor BOT", color=discord.Color.purple())
                    embed.description = f"{user_mention} **Aapka Instagram Account Unbanned Ho Gaya Hai!**"
                    embed.add_field(name="Instagram Account", value=f"@{username}", inline=False)
                    embed.add_field(name="Followers", value=str(user_data["followers"]), inline=True)
                    embed.add_field(name="Status", value="✅ Account is Active", inline=False)
                    if user_data["pfp"]:
                        embed.set_image(url=user_data["pfp"])
                    await channel.send(embed=embed)
                    status_tracker[username] = True
                    del monitored_accounts[username]
                elif not user_data["active"] and status_tracker.get(username):
                    status_tracker[username] = False
        await asyncio.sleep(60)

if __name__ == "__main__":
    import threading
    port = int(os.environ.get("PORT", 10000))
    flask_thread = threading.Thread(target=lambda: app_flask.run(host="0.0.0.0", port=port, use_reloader=False))
    flask_thread.daemon = True
    flask_thread.start()
    bot.run(DISCORD_TOKEN)
