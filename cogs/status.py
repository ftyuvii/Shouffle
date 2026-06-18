import discord
from discord.ext import commands, tasks


class Status(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.current_status = 0

        self.statuses = [
            discord.Activity(
                type=discord.ActivityType.listening,
                name="Made with Love and Safety"
            ),
            discord.Game(
                name="Bot with private Security layers"
            ),
            discord.Activity(
                type=discord.ActivityType.watching,
                name="Commands List /help "
            )
        ]

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.rotate_status.is_running():
            self.rotate_status.start()

        print("Status system loaded.")

    @tasks.loop(seconds=15)
    async def rotate_status(self):
        await self.bot.change_presence(
            status=discord.Status.online,
            activity=self.statuses[self.current_status]
        )

        self.current_status = (self.current_status + 1) % len(self.statuses)

    @rotate_status.before_loop
    async def before_rotate_status(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Status(bot))