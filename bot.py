import discord
from discord.ext import commands
import os
import json

OWNER_ID = 907180055615123456


def load_noprefix_users():
    if not os.path.exists("noprefix.json"):
        with open("noprefix.json", "w") as f:
            json.dump([], f)

    with open("noprefix.json", "r") as f:
        return json.load(f)


# ── Intents ───────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True   # prefix commands ke liye
intents.members = True           # on_member_join ke liye (welcome system)
intents.guilds = True            # guild info ke liye

bot = commands.Bot(
    command_prefix="?",
    intents=intents,
    help_command=None,
    owner_id=OWNER_ID
)


async def load_all_cogs():
    if not os.path.exists("./cogs"):
        os.makedirs("./cogs")

    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
                print(f"[COG] Loaded: {filename}")
            except Exception as e:
                print(f"[COG ERROR] {filename}: {e}")


@bot.event
async def setup_hook():
    await load_all_cogs()

    try:
        synced = await bot.tree.sync()
        print(f"[SLASH] Synced {len(synced)} commands")
    except Exception as e:
        print(f"[SLASH ERROR] {e}")


@bot.event
async def on_ready():
    print("-" * 50)
    print(f"Logged in as {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print("-" * 50)


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    np_users = load_noprefix_users()

    if message.author.id in np_users:
        if message.content:
            command_name = message.content.split()[0].lower()

            if bot.get_command(command_name):
                message.content = f"?{message.content}"

    await bot.process_commands(message)

bot.run("MTUxMzQ1ODIwMTEzMDA0NTUxMA.G1wGD_.156JNSQZW6VMJOMj11I4HJRAfVGJOblrWpkFmw")