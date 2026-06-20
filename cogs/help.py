import discord
from discord.ext import commands
from discord import app_commands

EMBED_COLOR = 0xFFFFFF

SUPPORT_SERVER_URL = "https://discord.gg/Gfm2RXKNew"
WEBSITE_URL = "https://shouffle.vercel.app/docs.html"
YOUTUBE_URL = "https://drive.google.com/drive/folders/1fJjL-w0f9FEenJoiZCkRaq8NPHVWxIjw"


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def build_embed(self, bot: commands.Bot) -> discord.Embed:
        embed = discord.Embed(color=EMBED_COLOR)

        embed.add_field(
            name="<:white_star:1517423116421431428>  Welcome to Shouffle",
            value=(
                "Use `/` or ? for existing commands information. "
                "See all the commands on our official dashboard or visit our support server for any kind of guidance."
            ),
            inline=False,
        )

        embed.add_field(
            name="<:white_star:1517423116421431428> Additional Info",
            value=(
                f"> • [Command list - Website]({WEBSITE_URL})\n"
                f"> • [Beginner Tutorials]({YOUTUBE_URL})"
            ),
            inline=False,
        )

        if bot.user and bot.user.avatar:
            embed.set_thumbnail(url=bot.user.avatar.url)

        return embed

    def build_view(self) -> discord.ui.View:
        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label="Support Server",
                url=SUPPORT_SERVER_URL,
                style=discord.ButtonStyle.link,
                emoji="➡️",
            )
        )
        return view

    @commands.command(name="help")
    async def help_prefix(self, ctx: commands.Context):
        embed = self.build_embed(ctx.bot)
        view = self.build_view()
        await ctx.send(embed=embed, view=view)

    @app_commands.command(name="help", description="Learn how to use Shouffle")
    async def help_slash(self, interaction: discord.Interaction):
        embed = self.build_embed(interaction.client)
        view = self.build_view()
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))