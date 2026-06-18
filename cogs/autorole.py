import discord
from discord.ext import commands
import json
import os

class AutoRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.file = "autorole.json"

        if not os.path.exists(self.file):
            with open(self.file, "w") as f:
                json.dump({}, f)

    def load_data(self):
        with open(self.file, "r") as f:
            return json.load(f)

    def save_data(self, data):
        with open(self.file, "w") as f:
            json.dump(data, f, indent=4)

    @commands.command(name="autorole")
    @commands.has_permissions(administrator=True)
    async def autorole(self, ctx, role: discord.Role):
        data = self.load_data()
        data[str(ctx.guild.id)] = role.id
        self.save_data(data)

        await ctx.send(f"✅ Autorole set to {role.mention}")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        data = self.load_data()

        role_id = data.get(str(member.guild.id))
        if not role_id:
            return

        role = member.guild.get_role(role_id)
        if role:
            try:
                await member.add_roles(role, reason="Autorole")
            except discord.Forbidden:
                pass

async def setup(bot):
    await bot.add_cog(AutoRole(bot))