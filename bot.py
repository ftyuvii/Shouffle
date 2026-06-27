import discord
from discord.ext import commands
import os
import json

OWNER_ID = 10000000000000
COGS_DIR = "./cogs"
NOPREFIX_FILE = "data/noprefix.json"


def load_noprefix_users() -> list:
    if not os.path.exists(NOPREFIX_FILE):
        with open(NOPREFIX_FILE, "w") as f:
            json.dump([], f)
    with open(NOPREFIX_FILE, "r") as f:
        return json.load(f)


intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True


def get_prefix(bot: commands.Bot, message: discord.Message):
    return commands.when_mentioned_or("?")(bot, message)


class Shouffle(commands.Bot):

    def __init__(self):
        super().__init__(
            command_prefix=get_prefix,
            intents=intents,
            help_command=None,
            owner_id=OWNER_ID,
            case_insensitive=True,
        )

    async def setup_hook(self):
        await self._load_cogs()
        try:
            synced = await self.tree.sync()
            print(f"[SLASH] Synced {len(synced)} commands")
        except Exception as e:
            print(f"[SLASH ERROR] {e}")

    async def _load_cogs(self):
        os.makedirs(COGS_DIR, exist_ok=True)
        loaded, failed = 0, 0
        for filename in sorted(os.listdir(COGS_DIR)):
            if not filename.endswith(".py"):
                continue
            ext = f"cogs.{filename[:-3]}"
            try:
                await self.load_extension(ext)
                print(f"[COG] ✓ {filename}")
                loaded += 1
            except Exception as e:
                print(f"[COG] ✗ {filename}: {e}")
                failed += 1
        print(f"[COG] Loaded {loaded} | Failed {failed}")

    async def on_ready(self):
        print("-" * 50)
        print(f"  Bot  : {self.user}")
        print(f"  ID   : {self.user.id}")
        print(f"  Guilds: {len(self.guilds)}")
        print("-" * 50)

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        noprefix_users = load_noprefix_users()

        if message.author.id in noprefix_users and message.content:
            first_word = message.content.split()[0]
            if not first_word.startswith("?"):
                command_name = first_word.lower()
                if self.get_command(command_name):
                    message.content = f"?{message.content}"

        await self.process_commands(message)


bot = Shouffle()
bot.run("TOKEN")