import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio

# ── Storage helpers ──────────────────────────────────────────────────────────
DATA_FILE = "tempvc_data.json"

def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data: dict):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_guild_config(guild_id: int) -> dict | None:
    return load_data().get(str(guild_id))

def set_guild_config(guild_id: int, config: dict):
    data = load_data()
    data[str(guild_id)] = config
    save_data(data)

def get_temp_channels(guild_id: int) -> dict:
    """Returns {vc_channel_id: owner_id}"""
    data = load_data()
    return data.get(f"temp_{guild_id}", {})

def set_temp_channels(guild_id: int, channels: dict):
    data = load_data()
    data[f"temp_{guild_id}"] = channels
    save_data(data)


# ── Controller Panel View ─────────────────────────────────────────────────────
class VCControlPanel(discord.ui.View):
    """Persistent control panel — works across bot restarts."""

    def __init__(self):
        super().__init__(timeout=None)

    # ── helpers ──────────────────────────────────────────────────────────────
    async def _get_owner_vc(self, interaction: discord.Interaction) -> discord.VoiceChannel | None:
        """Return the temp VC owned by the interaction member, or None."""
        temp = get_temp_channels(interaction.guild_id)
        for ch_id, owner_id in temp.items():
            if owner_id == interaction.user.id:
                ch = interaction.guild.get_channel(int(ch_id))
                if ch:
                    return ch
        await interaction.response.send_message(
            "❌ You don't own a temporary voice channel right now.",
            ephemeral=True
        )
        return None

    # ── 🔒 Lock ───────────────────────────────────────────────────────────────
    @discord.ui.button(label="🔒 Lock", style=discord.ButtonStyle.danger,
                       custom_id="tvc:lock", row=0)
    async def lock(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = await self._get_owner_vc(interaction)
        if not vc:
            return
        overwrite = vc.overwrites_for(interaction.guild.default_role)
        overwrite.connect = False
        await vc.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message("🔒 Channel **locked**.", ephemeral=True)

    # ── 🔓 Unlock ─────────────────────────────────────────────────────────────
    @discord.ui.button(label="🔓 Unlock", style=discord.ButtonStyle.success,
                       custom_id="tvc:unlock", row=0)
    async def unlock(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = await self._get_owner_vc(interaction)
        if not vc:
            return
        overwrite = vc.overwrites_for(interaction.guild.default_role)
        overwrite.connect = True
        await vc.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message("🔓 Channel **unlocked**.", ephemeral=True)

    # ── 👻 Hide ───────────────────────────────────────────────────────────────
    @discord.ui.button(label="👻 Hide", style=discord.ButtonStyle.secondary,
                       custom_id="tvc:hide", row=0)
    async def hide(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = await self._get_owner_vc(interaction)
        if not vc:
            return
        overwrite = vc.overwrites_for(interaction.guild.default_role)
        overwrite.view_channel = False
        await vc.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message("👻 Channel **hidden**.", ephemeral=True)

    # ── 👁️ Reveal ─────────────────────────────────────────────────────────────
    @discord.ui.button(label="👁️ Reveal", style=discord.ButtonStyle.secondary,
                       custom_id="tvc:reveal", row=0)
    async def reveal(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = await self._get_owner_vc(interaction)
        if not vc:
            return
        overwrite = vc.overwrites_for(interaction.guild.default_role)
        overwrite.view_channel = True
        await vc.set_permissions(interaction.guild.default_role, overwrite=overwrite)
        await interaction.response.send_message("👁️ Channel **visible** to everyone.", ephemeral=True)

    # ── ✏️ Rename ──────────────────────────────────────────────────────────────
    @discord.ui.button(label="✏️ Rename", style=discord.ButtonStyle.primary,
                       custom_id="tvc:rename", row=1)
    async def rename(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = await self._get_owner_vc(interaction)
        if not vc:
            return
        modal = RenameModal(vc)
        await interaction.response.send_modal(modal)

    # ── 👥 Set Limit ───────────────────────────────────────────────────────────
    @discord.ui.button(label="👥 User Limit", style=discord.ButtonStyle.primary,
                       custom_id="tvc:limit", row=1)
    async def user_limit(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = await self._get_owner_vc(interaction)
        if not vc:
            return
        modal = LimitModal(vc)
        await interaction.response.send_modal(modal)

    # ── ➕ Permit User ─────────────────────────────────────────────────────────
    @discord.ui.button(label="✅ Permit", style=discord.ButtonStyle.success,
                       custom_id="tvc:permit", row=1)
    async def permit(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = await self._get_owner_vc(interaction)
        if not vc:
            return
        modal = PermitModal(vc, allow=True)
        await interaction.response.send_modal(modal)

    # ── ⛔ Reject User ─────────────────────────────────────────────────────────
    @discord.ui.button(label="⛔ Reject", style=discord.ButtonStyle.danger,
                       custom_id="tvc:reject", row=1)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = await self._get_owner_vc(interaction)
        if not vc:
            return
        modal = PermitModal(vc, allow=False)
        await interaction.response.send_modal(modal)

    # ── 👑 Transfer ────────────────────────────────────────────────────────────
    @discord.ui.button(label="👑 Transfer", style=discord.ButtonStyle.primary,
                       custom_id="tvc:transfer", row=2)
    async def transfer(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = await self._get_owner_vc(interaction)
        if not vc:
            return
        modal = TransferModal(vc, interaction.guild_id)
        await interaction.response.send_modal(modal)

    # ── 🔇 Mute All ───────────────────────────────────────────────────────────
    @discord.ui.button(label="🔇 Mute All", style=discord.ButtonStyle.danger,
                       custom_id="tvc:muteall", row=2)
    async def mute_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = await self._get_owner_vc(interaction)
        if not vc:
            return
        count = 0
        for member in vc.members:
            if member != interaction.user and not member.bot:
                try:
                    await member.edit(mute=True)
                    count += 1
                except Exception:
                    pass
        await interaction.response.send_message(
            f"🔇 Muted **{count}** member(s).", ephemeral=True
        )

    # ── 🔊 Unmute All ─────────────────────────────────────────────────────────
    @discord.ui.button(label="🔊 Unmute All", style=discord.ButtonStyle.success,
                       custom_id="tvc:unmuteall", row=2)
    async def unmute_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = await self._get_owner_vc(interaction)
        if not vc:
            return
        count = 0
        for member in vc.members:
            if not member.bot:
                try:
                    await member.edit(mute=False)
                    count += 1
                except Exception:
                    pass
        await interaction.response.send_message(
            f"🔊 Unmuted **{count}** member(s).", ephemeral=True
        )

    # ── 🗑️ Delete ──────────────────────────────────────────────────────────────
    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger,
                       custom_id="tvc:delete", row=2)
    async def delete_vc(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = await self._get_owner_vc(interaction)
        if not vc:
            return
        temp = get_temp_channels(interaction.guild_id)
        temp.pop(str(vc.id), None)
        set_temp_channels(interaction.guild_id, temp)
        await vc.delete(reason="Owner deleted via control panel.")
        await interaction.response.send_message("🗑️ Your channel has been deleted.", ephemeral=True)


# ── Modals ────────────────────────────────────────────────────────────────────
class RenameModal(discord.ui.Modal, title="✏️ Rename Your Voice Channel"):
    name = discord.ui.TextInput(label="New Channel Name", max_length=100,
                                placeholder="e.g. 🎮 Gaming Lounge")

    def __init__(self, vc: discord.VoiceChannel):
        super().__init__()
        self.vc = vc

    async def on_submit(self, interaction: discord.Interaction):
        await self.vc.edit(name=self.name.value)
        await interaction.response.send_message(
            f"✏️ Channel renamed to **{self.name.value}**.", ephemeral=True
        )


class LimitModal(discord.ui.Modal, title="👥 Set User Limit"):
    limit = discord.ui.TextInput(label="User Limit (0 = unlimited)", max_length=2,
                                 placeholder="e.g. 5")

    def __init__(self, vc: discord.VoiceChannel):
        super().__init__()
        self.vc = vc

    async def on_submit(self, interaction: discord.Interaction):
        try:
            val = int(self.limit.value)
            if not 0 <= val <= 99:
                raise ValueError
        except ValueError:
            return await interaction.response.send_message(
                "❌ Enter a number between 0 and 99.", ephemeral=True
            )
        await self.vc.edit(user_limit=val)
        label = f"**{val}**" if val else "**unlimited**"
        await interaction.response.send_message(f"👥 User limit set to {label}.", ephemeral=True)


class PermitModal(discord.ui.Modal):
    user_input = discord.ui.TextInput(label="Username or User ID",
                                      placeholder="e.g. CoolUser#1234 or 123456789")

    def __init__(self, vc: discord.VoiceChannel, allow: bool):
        title = "✅ Permit a User" if allow else "⛔ Reject a User"
        super().__init__(title=title)
        self.vc = vc
        self.allow = allow

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.user_input.value.strip()
        member = None
        if raw.isdigit():
            member = interaction.guild.get_member(int(raw))
        if not member:
            member = discord.utils.find(
                lambda m: str(m) == raw or m.name == raw or m.display_name == raw,
                interaction.guild.members
            )
        if not member:
            return await interaction.response.send_message("❌ User not found.", ephemeral=True)

        overwrite = self.vc.overwrites_for(member)
        if self.allow:
            overwrite.connect = True
            overwrite.view_channel = True
            action = f"✅ **{member.display_name}** can now join your channel."
        else:
            overwrite.connect = False
            action = f"⛔ **{member.display_name}** is now rejected from your channel."
            if member in self.vc.members:
                try:
                    await member.move_to(None)
                except Exception:
                    pass

        await self.vc.set_permissions(member, overwrite=overwrite)
        await interaction.response.send_message(action, ephemeral=True)


class TransferModal(discord.ui.Modal, title="👑 Transfer Ownership"):
    user_input = discord.ui.TextInput(label="New Owner (Username or User ID)",
                                      placeholder="e.g. CoolUser#1234 or 123456789")

    def __init__(self, vc: discord.VoiceChannel, guild_id: int):
        super().__init__()
        self.vc = vc
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.user_input.value.strip()
        member = None
        if raw.isdigit():
            member = interaction.guild.get_member(int(raw))
        if not member:
            member = discord.utils.find(
                lambda m: str(m) == raw or m.name == raw or m.display_name == raw,
                interaction.guild.members
            )
        if not member:
            return await interaction.response.send_message("❌ User not found.", ephemeral=True)
        if member.bot:
            return await interaction.response.send_message("❌ Cannot transfer to a bot.", ephemeral=True)

        temp = get_temp_channels(self.guild_id)
        temp[str(self.vc.id)] = member.id
        set_temp_channels(self.guild_id, temp)
        await interaction.response.send_message(
            f"👑 Ownership of **{self.vc.name}** transferred to **{member.display_name}**.",
            ephemeral=True
        )


# ── Default banner image — replace this URL with your own ────────────────────
DEFAULT_PANEL_IMAGE = "https://i.ibb.co/dsr5DvVf/file-00000000939c7207ad49279b063c85f6.png"


# ── Setup Modal ───────────────────────────────────────────────────────────────
class SetupModal(discord.ui.Modal, title="🎙️ Temporary VC Setup"):
    category_name = discord.ui.TextInput(
        label="Category Name",
        placeholder="e.g. 🔊 Voice Channels",
        default="🔊 Voice Channels",
        max_length=100
    )

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild

        # 1. Create or find category
        cat_name = self.category_name.value.strip()
        category = discord.utils.get(guild.categories, name=cat_name)
        if not category:
            category = await guild.create_category(cat_name)

        # 2. Create text channel for control panel
        chat_ch = discord.utils.get(guild.text_channels, name="audio-interface")
        if not chat_ch:
            chat_ch = await guild.create_text_channel(
                "audio-interface",
                category=category,
                topic="🎛️ Control your temporary voice channel here."
            )

        # 3. Create the ➕ Create VC voice channel
        create_vc = discord.utils.get(guild.voice_channels, name="➕ Create VC")
        if not create_vc:
            create_vc = await guild.create_voice_channel(
                "➕ Create VC",
                category=category
            )

        # 4. Save config
        set_guild_config(guild.id, {
            "category_id": category.id,
            "chat_channel_id": chat_ch.id,
            "create_vc_id": create_vc.id,
        })

        # 5. Post the control panel
        await self.cog.post_panel(chat_ch)

        await interaction.followup.send(
            f"✅ **Temporary VC system is live!**\n"
            f"📁 Category → `{category.name}`\n"
            f"💬 Control Panel → {chat_ch.mention}\n"
            f"🔊 Join-to-create → {create_vc.mention}",
            ephemeral=True
        )


# ── Main Cog ──────────────────────────────────────────────────────────────────
class TempVC(commands.Cog):
    """Temporary Voice Channel system with a beautiful control panel."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        # Re-register persistent view so buttons survive restarts
        self.bot.add_view(VCControlPanel())

    # ── Panel builder ──────────────────────────────────────────────────────────
    async def post_panel(self, channel: discord.TextChannel):
        """Send (or replace) the control panel embed in the given text channel."""
        # Clear old bot messages in that channel
        async for msg in channel.history(limit=20):
            if msg.author == self.bot.user:
                try:
                    await msg.delete()
                except Exception:
                    pass

        embed = discord.Embed(
            title="🎛️  Voice Channel Controller",
            description="Join **➕ Create VC** to get your own private room.\nUse the buttons below to manage your channel.",
            color=0xFFB6C1  # light pink
        )

        embed.set_image(url=DEFAULT_PANEL_IMAGE)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text="Your channel auto-deletes when empty.")

        await channel.send(embed=embed, view=VCControlPanel())

    # ── vcsetup — prefix ───────────────────────────────────────────────────────
    @commands.command(name="vcsetup")
    @commands.has_permissions(administrator=True)
    async def vcsetup_prefix(self, ctx: commands.Context):
        """Admin: set up the Temporary VC system."""
        modal_trigger = discord.ui.View()

        async def open_modal(interaction: discord.Interaction):
            await interaction.response.send_modal(SetupModal(self))

        btn = discord.ui.Button(label="⚙️ Open Setup", style=discord.ButtonStyle.primary)
        btn.callback = open_modal
        modal_trigger.add_item(btn)

        await ctx.send(
            "Click the button below to configure the Temporary VC system.",
            view=modal_trigger,
            delete_after=60
        )

    # ── /vcsetup — slash ───────────────────────────────────────────────────────
    @app_commands.command(name="vcsetup", description="Admin: set up the Temporary VC system.")
    @app_commands.default_permissions(administrator=True)
    async def vcsetup_slash(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SetupModal(self))

    # ── Voice state listener: create / delete temp VCs ─────────────────────────
    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ):
        config = get_guild_config(member.guild.id)
        if not config:
            return

        create_vc_id = config.get("create_vc_id")
        category_id = config.get("category_id")
        temp = get_temp_channels(member.guild.id)

        # ── Joined the "Create VC" trigger channel ────────────────────────────
        if after.channel and after.channel.id == create_vc_id:
            category = member.guild.get_channel(category_id)

            new_vc = await member.guild.create_voice_channel(
                name=f"🎙️ {member.display_name}'s Room",
                category=category,
                reason="Temporary VC created"
            )

            # Give the owner full control
            await new_vc.set_permissions(member,
                manage_channels=True,
                connect=True,
                speak=True,
                move_members=True,
                mute_members=True,
                deafen_members=True
            )

            # Move the member in
            try:
                await member.move_to(new_vc)
            except discord.HTTPException:
                pass

            # Record ownership
            temp[str(new_vc.id)] = member.id
            set_temp_channels(member.guild.id, temp)

        # ── Left a temp VC — auto-delete if empty ────────────────────────────
        if before.channel and str(before.channel.id) in temp:
            await asyncio.sleep(1)          # short grace period
            ch = member.guild.get_channel(before.channel.id)
            if ch and len(ch.members) == 0:
                temp = get_temp_channels(member.guild.id)  # reload
                temp.pop(str(ch.id), None)
                set_temp_channels(member.guild.id, temp)
                try:
                    await ch.delete(reason="Temporary VC empty — auto-deleted.")
                except discord.NotFound:
                    pass

    # ── /panel — refresh the control panel ────────────────────────────────────
    @app_commands.command(name="vcpanel", description="Resend the VC control panel (admin).")
    @app_commands.default_permissions(administrator=True)
    async def vcpanel_slash(self, interaction: discord.Interaction):
        config = get_guild_config(interaction.guild_id)
        if not config:
            return await interaction.response.send_message(
                "❌ Run `/vcsetup` first.", ephemeral=True
            )
        ch = interaction.guild.get_channel(config["chat_channel_id"])
        if not ch:
            return await interaction.response.send_message(
                "❌ Panel channel not found. Run `/vcsetup` again.", ephemeral=True
            )
        await self.post_panel(ch)
        await interaction.response.send_message("✅ Panel refreshed!", ephemeral=True)

    @commands.command(name="vcpanel")
    @commands.has_permissions(administrator=True)
    async def vcpanel_prefix(self, ctx: commands.Context):
        """Resend the VC control panel."""
        config = get_guild_config(ctx.guild.id)
        if not config:
            return await ctx.send("❌ Run `vcsetup` first.")
        ch = ctx.guild.get_channel(config["chat_channel_id"])
        if not ch:
            return await ctx.send("❌ Panel channel not found. Run `vcsetup` again.")
        await self.post_panel(ch)
        await ctx.send("✅ Panel refreshed!", delete_after=5)


# ── Cog loader ─────────────────────────────────────────────────────────────────
async def setup(bot: commands.Bot):
    await bot.add_cog(TempVC(bot))