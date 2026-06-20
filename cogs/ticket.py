import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio
import io
from datetime import datetime

PANELS_FILE = "data/ticket_panels.json"
TICKETS_FILE = "data/tickets.json"


def load_json(path):
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump({}, f)
    with open(path, "r") as f:
        return json.load(f)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=4)


def get_panels():
    return load_json(PANELS_FILE)


def save_panels(data):
    save_json(PANELS_FILE, data)


def get_tickets():
    return load_json(TICKETS_FILE)


def save_tickets(data):
    save_json(TICKETS_FILE, data)


def build_panel_embed(panel_data):
    embed = discord.Embed(
        title=panel_data.get("panel_title", "Support"),
        description=panel_data.get("panel_description", "Click below to open a ticket."),
        color=panel_data.get("color", 0x5865F2),
        timestamp=datetime.utcnow()
    )
    if panel_data.get("thumbnail_url"):
        embed.set_thumbnail(url=panel_data["thumbnail_url"])
    embed.set_footer(text=panel_data.get("footer_text", "Ticket System"))
    return embed


def build_config_embed(panel_id, panel_data, guild):
    category = guild.get_channel(panel_data.get("category_id", 0))
    role = guild.get_role(panel_data.get("support_role_id", 0))
    log_ch_id = panel_data.get("log_channel_id")
    color = panel_data.get("color", 0x5865F2)

    embed = discord.Embed(
        title=f"⚙️  Panel Config",
        color=color,
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Panel ID", value=f"`{panel_id}`", inline=False)
    embed.add_field(name="📌 Title", value=panel_data.get("panel_title", "N/A"), inline=True)
    embed.add_field(name="🎫 Button", value=panel_data.get("button_label", "N/A"), inline=True)
    embed.add_field(name="📂 Category", value=category.mention if category else "❌ Not found", inline=True)
    embed.add_field(name="🛡️ Support Role", value=role.mention if role else "❌ Not found", inline=True)
    embed.add_field(name="📋 Log Channel", value=f"<#{log_ch_id}>" if log_ch_id else "Not set", inline=True)
    embed.add_field(name="🎨 Color", value=f"`#{hex(color)[2:].upper()}`", inline=True)
    embed.add_field(name="📝 Footer", value=panel_data.get("footer_text", "N/A"), inline=True)

    if panel_data.get("channel_id") and panel_data.get("message_id"):
        link = f"https://discord.com/channels/{panel_data['guild_id']}/{panel_data['channel_id']}/{panel_data['message_id']}"
        embed.add_field(name="🔗 Panel Message", value=f"[Jump to panel]({link})", inline=False)

    return embed


async def ask(bot, ctx, prompt_embed, timeout=60):
    msg = await ctx.send(embed=prompt_embed)

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        reply = await bot.wait_for("message", check=check, timeout=timeout)
        try:
            await reply.delete()
        except Exception:
            pass
        return reply.content.strip()
    except asyncio.TimeoutError:
        await msg.edit(embed=discord.Embed(description="⏳ Timed out. Run the command again.", color=0xED4245))
        return None


def q(title, desc, step, total, color=0x5865F2):
    e = discord.Embed(title=f"Step {step}/{total} — {title}", description=desc, color=color)
    e.set_footer(text="Type your answer below • Type 'skip' to skip optional fields")
    return e


class TicketOpenView(discord.ui.View):
    def __init__(self, panel_id, button_label="Open a Ticket"):
        super().__init__(timeout=None)
        self.add_item(TicketOpenButton(panel_id, button_label))


class TicketOpenButton(discord.ui.Button):
    def __init__(self, panel_id, label):
        super().__init__(
            label=label,
            style=discord.ButtonStyle.primary,
            emoji="🎫",
            custom_id=f"ticket_open:{panel_id}"
        )
        self.panel_id = panel_id

    async def callback(self, interaction: discord.Interaction):
        panels = get_panels()
        panel = panels.get(self.panel_id)
        if not panel:
            return await interaction.response.send_message("❌ Panel not found.", ephemeral=True)

        tickets = get_tickets()
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)
        key = f"{guild_id}_{user_id}"

        if key in tickets and tickets[key].get("open"):
            ch = interaction.guild.get_channel(tickets[key]["channel_id"])
            if ch:
                return await interaction.response.send_message(
                    f"❌ You already have an open ticket: {ch.mention}", ephemeral=True
                )

        category = interaction.guild.get_channel(panel["category_id"])
        support_role = interaction.guild.get_role(panel["support_role_id"])

        if not category:
            return await interaction.response.send_message("❌ Ticket category not found. Contact an admin.", ephemeral=True)

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                read_message_history=True, attach_files=True, embed_links=True
            ),
            interaction.guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                manage_channels=True, read_message_history=True, manage_messages=True
            )
        }
        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                read_message_history=True, manage_messages=True
            )

        ticket_count = sum(1 for k in tickets if k.startswith(guild_id))
        channel_name = f"ticket-{interaction.user.name.lower().replace(' ', '-')}-{ticket_count + 1}"

        await interaction.response.defer(ephemeral=True)

        channel = await interaction.guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            reason=f"Ticket opened by {interaction.user}"
        )

        tickets[key] = {
            "open": True,
            "channel_id": channel.id,
            "panel_id": self.panel_id,
            "opened_at": datetime.utcnow().isoformat(),
            "opened_by": interaction.user.id,
            "ticket_number": ticket_count + 1
        }
        save_tickets(tickets)

        welcome_embed = discord.Embed(
            title=f"🎫  Ticket #{ticket_count + 1}",
            description=(
                f"Hey {interaction.user.mention}, welcome! 👋\n\n"
                f"Please describe your issue and our support team will assist you shortly.\n\n"
                f"**Opened:** <t:{int(datetime.utcnow().timestamp())}:F>\n"
                f"**Panel:** {panel['panel_title']}"
            ),
            color=panel.get("color", 0x5865F2),
            timestamp=datetime.utcnow()
        )
        welcome_embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        if panel.get("thumbnail_url"):
            welcome_embed.set_thumbnail(url=panel["thumbnail_url"])
        welcome_embed.set_footer(
            text=panel.get("footer_text", "Ticket System"),
            icon_url=interaction.guild.icon.url if interaction.guild.icon else None
        )

        mention_str = interaction.user.mention
        if support_role:
            mention_str += f" | {support_role.mention}"

        view = TicketControlView(self.panel_id, interaction.user.id)
        await channel.send(content=mention_str, embed=welcome_embed, view=view)

        log_channel_id = panel.get("log_channel_id")
        if log_channel_id:
            log_ch = interaction.guild.get_channel(log_channel_id)
            if log_ch:
                log_embed = discord.Embed(title="📂 Ticket Opened", color=0x57F287, timestamp=datetime.utcnow())
                log_embed.add_field(name="User", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=True)
                log_embed.add_field(name="Channel", value=channel.mention, inline=True)
                log_embed.add_field(name="Panel", value=panel["panel_title"], inline=True)
                log_embed.set_thumbnail(url=interaction.user.display_avatar.url)
                log_embed.set_footer(text=f"Ticket #{ticket_count + 1}")
                await log_ch.send(embed=log_embed)

        await interaction.followup.send(f"✅ Ticket created: {channel.mention}", ephemeral=True)


class TicketControlView(discord.ui.View):
    def __init__(self, panel_id, opener_id):
        super().__init__(timeout=None)
        self.add_item(TicketCloseButton(panel_id, opener_id))
        self.add_item(TicketClaimButton(panel_id))
        self.add_item(TicketTranscriptButton(panel_id))


class TicketCloseButton(discord.ui.Button):
    def __init__(self, panel_id, opener_id):
        super().__init__(
            label="Close Ticket",
            style=discord.ButtonStyle.danger,
            emoji="🔒",
            custom_id=f"ticket_close:{panel_id}:{opener_id}"
        )
        self.panel_id = panel_id
        self.opener_id = int(opener_id)

    async def callback(self, interaction: discord.Interaction):
        panels = get_panels()
        panel = panels.get(self.panel_id, {})
        support_role = interaction.guild.get_role(panel.get("support_role_id", 0))

        is_staff = (support_role and support_role in interaction.user.roles) or interaction.user.guild_permissions.administrator
        is_opener = interaction.user.id == self.opener_id

        if not (is_staff or is_opener):
            return await interaction.response.send_message("❌ You don't have permission to close this ticket.", ephemeral=True)

        embed = discord.Embed(
            title="🔒 Close this ticket?",
            description=f"Requested by {interaction.user.mention}\n\nThis will save a transcript and delete the channel.",
            color=0xED4245,
            timestamp=datetime.utcnow()
        )
        await interaction.response.send_message(
            embed=embed,
            view=TicketCloseConfirmView(self.panel_id, self.opener_id)
        )


class TicketCloseConfirmView(discord.ui.View):
    def __init__(self, panel_id, opener_id):
        super().__init__(timeout=60)
        self.panel_id = panel_id
        self.opener_id = opener_id

    @discord.ui.button(label="Confirm Close", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        panels = get_panels()
        panel = panels.get(self.panel_id, {})
        support_role = interaction.guild.get_role(panel.get("support_role_id", 0))

        is_staff = (support_role and support_role in interaction.user.roles) or interaction.user.guild_permissions.administrator
        is_opener = interaction.user.id == self.opener_id

        if not (is_staff or is_opener):
            return await interaction.response.send_message("❌ You can't do that.", ephemeral=True)

        tickets = get_tickets()
        guild_id = str(interaction.guild.id)
        opener_key = f"{guild_id}_{self.opener_id}"
        ticket_data = tickets.get(opener_key, {})

        lines = []
        async for message in interaction.channel.history(limit=500, oldest_first=True):
            if not message.author.bot:
                ts = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
                lines.append(f"[{ts}] {message.author.display_name}: {message.content}")

        transcript_text = "\n".join(lines) if lines else "No messages."

        closed_embed = discord.Embed(
            title="🔒 Ticket Closed",
            description=f"Closed by {interaction.user.mention}\nDeleting in **5 seconds**...",
            color=0xED4245,
            timestamp=datetime.utcnow()
        )
        closed_embed.set_footer(text=panel.get("footer_text", "Ticket System"))
        await interaction.response.edit_message(embed=closed_embed, view=None)

        log_channel_id = panel.get("log_channel_id")
        if log_channel_id:
            log_ch = interaction.guild.get_channel(log_channel_id)
            if log_ch:
                opener = interaction.guild.get_member(self.opener_id)
                log_embed = discord.Embed(title="🔒 Ticket Closed", color=0xED4245, timestamp=datetime.utcnow())
                log_embed.add_field(name="Closed By", value=interaction.user.mention, inline=True)
                log_embed.add_field(name="Opened By", value=f"<@{self.opener_id}>", inline=True)
                log_embed.add_field(name="Panel", value=panel.get("panel_title", "Unknown"), inline=True)

                opened_at = ticket_data.get("opened_at")
                if opened_at:
                    log_embed.add_field(
                        name="Opened At",
                        value=f"<t:{int(datetime.fromisoformat(opened_at).timestamp())}:F>",
                        inline=False
                    )
                if opener:
                    log_embed.set_thumbnail(url=opener.display_avatar.url)

                await log_ch.send(embed=log_embed)

                if lines:
                    await log_ch.send(
                        file=discord.File(fp=io.StringIO(transcript_text), filename=f"transcript-{interaction.channel.name}.txt")
                    )

        if opener_key in tickets:
            tickets[opener_key]["open"] = False
            save_tickets(tickets)

        await asyncio.sleep(5)
        await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="↩️ Cancelled.", embed=None, view=None)
        self.stop()


class TicketClaimButton(discord.ui.Button):
    def __init__(self, panel_id):
        super().__init__(
            label="Claim",
            style=discord.ButtonStyle.success,
            emoji="🙋",
            custom_id=f"ticket_claim:{panel_id}"
        )
        self.panel_id = panel_id

    async def callback(self, interaction: discord.Interaction):
        panels = get_panels()
        panel = panels.get(self.panel_id, {})
        support_role = interaction.guild.get_role(panel.get("support_role_id", 0))

        is_staff = (support_role and support_role in interaction.user.roles) or interaction.user.guild_permissions.administrator
        if not is_staff:
            return await interaction.response.send_message("❌ Only support staff can claim tickets.", ephemeral=True)

        embed = discord.Embed(
            description=f"✅ Ticket claimed by {interaction.user.mention}",
            color=0x57F287,
            timestamp=datetime.utcnow()
        )
        await interaction.response.send_message(embed=embed)
        self.label = f"Claimed by {interaction.user.display_name}"
        self.style = discord.ButtonStyle.secondary
        self.disabled = True
        await interaction.message.edit(view=self.view)


class TicketTranscriptButton(discord.ui.Button):
    def __init__(self, panel_id):
        super().__init__(
            label="Transcript",
            style=discord.ButtonStyle.secondary,
            emoji="📄",
            custom_id=f"ticket_transcript:{panel_id}"
        )
        self.panel_id = panel_id

    async def callback(self, interaction: discord.Interaction):
        panels = get_panels()
        panel = panels.get(self.panel_id, {})
        support_role = interaction.guild.get_role(panel.get("support_role_id", 0))

        is_staff = (support_role and support_role in interaction.user.roles) or interaction.user.guild_permissions.administrator
        if not is_staff:
            return await interaction.response.send_message("❌ Only support staff can pull transcripts.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        lines = []
        async for msg in interaction.channel.history(limit=500, oldest_first=True):
            if not msg.author.bot:
                ts = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
                lines.append(f"[{ts}] {msg.author.display_name}: {msg.content}")

        text = "\n".join(lines) if lines else "No messages."
        await interaction.followup.send(
            file=discord.File(fp=io.StringIO(text), filename=f"transcript-{interaction.channel.name}.txt"),
            ephemeral=True
        )


class TicketConfigView(discord.ui.View):
    def __init__(self, ctx, panel_id, panel_data):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.panel_id = panel_id
        self.panel_data = panel_data

    @discord.ui.button(label="Edit Panel", style=discord.ButtonStyle.primary, emoji="✏️")
    async def edit_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("Not your config session.", ephemeral=True)
        await interaction.response.send_message(
            embed=discord.Embed(description="✏️ Starting edit session in chat...", color=0x5865F2),
            ephemeral=True
        )
        await run_setup(self.ctx, edit_panel_id=self.panel_id)
        self.stop()

    @discord.ui.button(label="Delete Panel", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("Not your config session.", ephemeral=True)
        confirm_view = DeleteConfirmView(self.ctx, self.panel_id, self.panel_data)
        await interaction.response.send_message(
            embed=discord.Embed(
                title="⚠️ Delete Panel?",
                description="This will remove the panel and delete the posted message. This cannot be undone.",
                color=0xED4245
            ),
            view=confirm_view,
            ephemeral=True
        )
        self.stop()


class DeleteConfirmView(discord.ui.View):
    def __init__(self, ctx, panel_id, panel_data):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.panel_id = panel_id
        self.panel_data = panel_data

    @discord.ui.button(label="Yes, Delete", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("Not your config session.", ephemeral=True)
        panels = get_panels()
        panel = panels.get(self.panel_id)
        if panel:
            ch = interaction.guild.get_channel(panel.get("channel_id", 0))
            if ch and panel.get("message_id"):
                try:
                    msg = await ch.fetch_message(panel["message_id"])
                    await msg.delete()
                except Exception:
                    pass
            del panels[self.panel_id]
            save_panels(panels)
        await interaction.response.edit_message(
            embed=discord.Embed(description="✅ Panel deleted.", color=0x57F287),
            view=None
        )
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=discord.Embed(description="↩️ Cancelled.", color=0x5865F2),
            view=None
        )
        self.stop()


class InteractionCtxWrapper:
    def __init__(self, interaction: discord.Interaction):
        self.interaction = interaction
        self.author = interaction.user
        self.channel = interaction.channel
        self.guild = interaction.guild
        self.bot = interaction.client
        self._responded = False

    async def send(self, *args, **kwargs):
        if not self._responded:
            self._responded = True
            await self.interaction.response.send_message(*args, **kwargs)
            return await self.interaction.original_response()
        else:
            return await self.interaction.followup.send(*args, **kwargs)


async def run_setup(ctx, edit_panel_id=None):
    bot = ctx.bot
    guild = ctx.guild
    total = 9

    existing = {}
    if edit_panel_id:
        panels = get_panels()
        existing = panels.get(edit_panel_id, {})

    async def ask_step(title, desc, step, timeout=60, color=0x5865F2):
        embed = discord.Embed(
            title=f"Step {step}/{total} — {title}",
            description=desc,
            color=color
        )
        embed.set_footer(text="Type 'cancel' to stop setup • Type 'skip' for optional fields")
        msg = await ctx.send(embed=embed)

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            reply = await bot.wait_for("message", check=check, timeout=timeout)
            try:
                await reply.delete()
            except Exception:
                pass
            await msg.delete()
            if reply.content.strip().lower() == "cancel":
                await ctx.send(embed=discord.Embed(description="❌ Setup cancelled.", color=0xED4245))
                return None
            return reply.content.strip()
        except asyncio.TimeoutError:
            await msg.delete()
            await ctx.send(embed=discord.Embed(description="⏳ Timed out. Run the command again.", color=0xED4245))
            return None

    panel_title = await ask_step(
        "Panel Title",
        f"What should the **title** of your ticket panel be?\n\n"
        f"{'> Current: `' + existing.get('panel_title', '') + '`' if existing else '> Example: `Support Center`'}",
        1
    )
    if panel_title is None:
        return
    if panel_title.lower() == "skip" and existing.get("panel_title"):
        panel_title = existing["panel_title"]

    panel_description = await ask_step(
        "Panel Description",
        f"What should the **description** say? This appears on the panel embed.\n\n"
        f"{'> Current: `' + existing.get('panel_description', '')[:60] + '...`' if existing else '> Example: `Click below to open a support ticket.`'}",
        2
    )
    if panel_description is None:
        return
    if panel_description.lower() == "skip" and existing.get("panel_description"):
        panel_description = existing["panel_description"]

    button_label = await ask_step(
        "Button Label",
        f"What should the **open ticket button** say?\n\n"
        f"{'> Current: `' + existing.get('button_label', '') + '`' if existing else '> Example: `Open a Ticket` or `Create Support Ticket`'}",
        3
    )
    if button_label is None:
        return
    if button_label.lower() == "skip" and existing.get("button_label"):
        button_label = existing["button_label"]

    category_val = await ask_step(
        "Ticket Category",
        "**Mention or paste the ID** of the category where tickets should be created.\n\n"
        "> Right-click the category → Copy ID\n"
        "> Or just paste the raw number",
        4
    )
    if category_val is None:
        return

    category_id = None
    cat_id_str = category_val.strip().replace("<#", "").replace(">", "")
    if cat_id_str.isdigit():
        cat = guild.get_channel(int(cat_id_str))
        if cat and isinstance(cat, discord.CategoryChannel):
            category_id = cat.id
    if not category_id:
        await ctx.send(embed=discord.Embed(description="❌ Couldn't find that category. Make sure it's a category, not a channel.", color=0xED4245))
        return

    role_val = await ask_step(
        "Support Role",
        "**Mention or paste the ID** of your support/staff role.\n\n"
        "> Mention it like `@Support` or paste the role ID",
        5
    )
    if role_val is None:
        return

    support_role_id = None
    role_str = role_val.strip().replace("<@&", "").replace(">", "")
    if role_str.isdigit():
        role = guild.get_role(int(role_str))
        if role:
            support_role_id = role.id
    if not support_role_id:
        await ctx.send(embed=discord.Embed(description="❌ Couldn't find that role. Try mentioning it or use the role ID.", color=0xED4245))
        return

    log_val = await ask_step(
        "Log Channel (Optional)",
        "**Mention the channel** where ticket logs should be sent.\n\n"
        "> Example: `#ticket-logs`\n> Type `skip` to skip this",
        6
    )
    if log_val is None:
        return

    log_channel_id = existing.get("log_channel_id")
    if log_val.lower() != "skip":
        log_str = log_val.strip().replace("<#", "").replace(">", "")
        if log_str.isdigit():
            lch = guild.get_channel(int(log_str))
            if lch:
                log_channel_id = lch.id

    color_val = await ask_step(
        "Embed Color (Optional)",
        "Send a **hex color code** for the panel embed.\n\n"
        "> Example: `#5865F2` or `FF0000`\n> Type `skip` to use default",
        7
    )
    if color_val is None:
        return

    color = existing.get("color", 0x5865F2)
    if color_val.lower() != "skip":
        try:
            color = int(color_val.strip().lstrip("#"), 16)
        except ValueError:
            await ctx.send(embed=discord.Embed(description="⚠️ Invalid color, using default blue.", color=0x5865F2))

    footer_val = await ask_step(
        "Footer Text (Optional)",
        "What should the **footer** say on embeds?\n\n"
        f"{'> Current: `' + existing.get('footer_text', '') + '`' if existing else '> Example: `Ticket System • Server Name`'}\n> Type `skip` to keep default",
        8
    )
    if footer_val is None:
        return

    footer_text = existing.get("footer_text", "Ticket System")
    if footer_val.lower() != "skip":
        footer_text = footer_val

    thumbnail_val = await ask_step(
        "Thumbnail Image URL (Optional)",
        "Paste an **image URL** to show as thumbnail on the panel.\n\n"
        "> Type `skip` to not use one",
        9
    )
    if thumbnail_val is None:
        return

    thumbnail_url = existing.get("thumbnail_url", "")
    if thumbnail_val.lower() != "skip":
        thumbnail_url = thumbnail_val

    panel_data = {
        "guild_id": guild.id,
        "panel_title": panel_title,
        "panel_description": panel_description,
        "button_label": button_label,
        "category_id": category_id,
        "support_role_id": support_role_id,
        "log_channel_id": log_channel_id,
        "color": color,
        "footer_text": footer_text,
        "thumbnail_url": thumbnail_url,
        "channel_id": existing.get("channel_id"),
        "message_id": existing.get("message_id")
    }

    preview_embed = build_panel_embed(panel_data)
    await ctx.send(
        embed=discord.Embed(
            title="✅ Setup Complete — Preview",
            description="Here's how your panel will look. Click **Post Panel** to send it here, or **Cancel** to abort.",
            color=color
        )
    )
    panel_preview = await ctx.send(embed=preview_embed)

    confirm_view = PostConfirmView(ctx, edit_panel_id, panel_data, panel_preview)
    await ctx.send(view=confirm_view)


class PostConfirmView(discord.ui.View):
    def __init__(self, ctx, edit_panel_id, panel_data, preview_msg):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.edit_panel_id = edit_panel_id
        self.panel_data = panel_data
        self.preview_msg = preview_msg

    @discord.ui.button(label="Post Panel", style=discord.ButtonStyle.success, emoji="📨")
    async def post(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("Not your setup.", ephemeral=True)

        panels = get_panels()

        if self.edit_panel_id and self.edit_panel_id in panels:
            panel_id = self.edit_panel_id
            old = panels[panel_id]
            if old.get("channel_id") and old.get("message_id"):
                ch = interaction.guild.get_channel(old["channel_id"])
                if ch:
                    try:
                        old_msg = await ch.fetch_message(old["message_id"])
                        await old_msg.delete()
                    except Exception:
                        pass
        else:
            panel_id = f"{interaction.guild.id}_{int(datetime.utcnow().timestamp())}"

        embed = build_panel_embed(self.panel_data)
        view = TicketOpenView(panel_id, self.panel_data["button_label"])
        sent = await interaction.channel.send(embed=embed, view=view)

        self.panel_data["channel_id"] = interaction.channel.id
        self.panel_data["message_id"] = sent.id
        panels[panel_id] = self.panel_data
        save_panels(panels)

        try:
            await self.preview_msg.delete()
        except Exception:
            pass

        await interaction.response.edit_message(
            content=None,
            embed=discord.Embed(
                description=f"✅ Panel posted! ID: `{panel_id}`",
                color=0x57F287
            ),
            view=None
        )
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("Not your setup.", ephemeral=True)
        try:
            await self.preview_msg.delete()
        except Exception:
            pass
        await interaction.response.edit_message(
            embed=discord.Embed(description="❌ Setup cancelled.", color=0xED4245),
            view=None
        )
        self.stop()


class Ticket(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        panels = get_panels()
        for panel_id, panel_data in panels.items():
            self.bot.add_view(TicketOpenView(panel_id, panel_data.get("button_label", "Open a Ticket")))

        tickets = get_tickets()
        for key, ticket in tickets.items():
            if ticket.get("open"):
                self.bot.add_view(TicketControlView(ticket.get("panel_id", ""), ticket.get("opened_by", 0)))

    @commands.command(name="ticketsetup")
    @commands.has_permissions(administrator=True)
    async def ticket_setup(self, ctx):
        intro = discord.Embed(
            title="🎫  Ticket Panel Setup",
            description=(
                "Let's set up your ticket panel step by step.\n\n"
                "I'll ask you **9 quick questions** in chat.\n"
                "Just type your answers — no copying IDs in a rush!\n\n"
                "> Type `cancel` at any step to stop.\n"
                "> Type `skip` on optional fields to skip them."
            ),
            color=0x5865F2,
            timestamp=datetime.utcnow()
        )
        intro.set_footer(text=f"Started by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=intro)
        await asyncio.sleep(1)
        await run_setup(ctx)

    @app_commands.command(name="ticketsetup", description="Set up a ticket panel (step-by-step)")
    @app_commands.default_permissions(administrator=True)
    async def ticket_setup_slash(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🎫  Ticket Panel Setup",
                description=(
                    "Let's set up your ticket panel step by step.\n\n"
                    "I'll ask you **9 quick questions** in chat.\n"
                    "Just type your answers — no copying IDs in a rush!\n\n"
                    "> Type `cancel` at any step to stop.\n"
                    "> Type `skip` on optional fields to skip them."
                ),
                color=0x5865F2,
                timestamp=datetime.utcnow()
            )
        )
        await asyncio.sleep(1)
        ctx = InteractionCtxWrapper(interaction)
        await run_setup(ctx)

    @commands.command(name="ticketconfig")
    @commands.has_permissions(administrator=True)
    async def ticket_config(self, ctx, panel_id: str = None):
        panels = get_panels()
        guild_panels = {k: v for k, v in panels.items() if v.get("guild_id") == ctx.guild.id}

        if not guild_panels:
            return await ctx.send(embed=discord.Embed(
                description="❌ No panels found. Use `?ticketsetup` to create one.",
                color=0xED4245
            ))

        if not panel_id:
            embed = discord.Embed(
                title="⚙️  Ticket Config",
                description="Use `?ticketconfig <panel_id>` to manage a panel.\n\n**Your panels:**",
                color=0x5865F2,
                timestamp=datetime.utcnow()
            )
            for pid, pdata in guild_panels.items():
                ch_id = pdata.get("channel_id")
                embed.add_field(
                    name=pdata.get("panel_title", "Untitled"),
                    value=f"ID: `{pid}`\nChannel: {f'<#{ch_id}>' if ch_id else 'Not set'}",
                    inline=True
                )
            return await ctx.send(embed=embed)

        panel = guild_panels.get(panel_id)
        if not panel:
            return await ctx.send(embed=discord.Embed(
                description=f"❌ Panel `{panel_id}` not found in this server.",
                color=0xED4245
            ))

        embed = build_config_embed(panel_id, panel, ctx.guild)
        view = TicketConfigView(ctx, panel_id, panel)
        await ctx.send(embed=embed, view=view)

    @app_commands.command(name="ticketconfig", description="View or manage a ticket panel")
    @app_commands.describe(panel_id="Panel ID to manage (leave blank to list all)")
    @app_commands.default_permissions(administrator=True)
    async def ticket_config_slash(self, interaction: discord.Interaction, panel_id: str = None):
        panels = get_panels()
        guild_panels = {k: v for k, v in panels.items() if v.get("guild_id") == interaction.guild.id}

        if not guild_panels:
            return await interaction.response.send_message(embed=discord.Embed(
                description="❌ No panels found. Use `/ticketsetup` to create one.",
                color=0xED4245
            ), ephemeral=True)

        if not panel_id:
            embed = discord.Embed(
                title="⚙️  Ticket Config",
                description="Use `/ticketconfig <panel_id>` to manage a panel.\n\n**Your panels:**",
                color=0x5865F2,
                timestamp=datetime.utcnow()
            )
            for pid, pdata in guild_panels.items():
                ch_id = pdata.get("channel_id")
                embed.add_field(
                    name=pdata.get("panel_title", "Untitled"),
                    value=f"ID: `{pid}`\nChannel: {f'<#{ch_id}>' if ch_id else 'Not set'}",
                    inline=True
                )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        panel = guild_panels.get(panel_id)
        if not panel:
            return await interaction.response.send_message(embed=discord.Embed(
                description=f"❌ Panel `{panel_id}` not found in this server.",
                color=0xED4245
            ), ephemeral=True)

        embed = build_config_embed(panel_id, panel, interaction.guild)
        ctx = InteractionCtxWrapper(interaction)
        view = TicketConfigView(ctx, panel_id, panel)
        await interaction.response.send_message(embed=embed, view=view)

    @commands.command(name="ticketclose")
    async def ticket_close(self, ctx):
        tickets = get_tickets()
        ticket_entry = None

        for key, data in tickets.items():
            if data.get("channel_id") == ctx.channel.id and data.get("open"):
                ticket_entry = data
                break

        if not ticket_entry:
            return await ctx.send(embed=discord.Embed(description="❌ This is not an active ticket channel.", color=0xED4245))

        panel_id = ticket_entry.get("panel_id", "")
        panels = get_panels()
        panel = panels.get(panel_id, {})
        support_role = ctx.guild.get_role(panel.get("support_role_id", 0))

        is_staff = (support_role and support_role in ctx.author.roles) or ctx.author.guild_permissions.administrator
        is_opener = ctx.author.id == ticket_entry.get("opened_by")

        if not (is_staff or is_opener):
            return await ctx.send(embed=discord.Embed(description="❌ You don't have permission to close this ticket.", color=0xED4245))

        embed = discord.Embed(
            title="🔒 Close this ticket?",
            description=f"Requested by {ctx.author.mention}",
            color=0xED4245,
            timestamp=datetime.utcnow()
        )
        view = TicketCloseConfirmView(panel_id, ticket_entry.get("opened_by"))
        await ctx.send(embed=embed, view=view)

    @app_commands.command(name="ticketclose", description="Close the current ticket channel")
    async def ticket_close_slash(self, interaction: discord.Interaction):
        tickets = get_tickets()
        ticket_entry = None

        for key, data in tickets.items():
            if data.get("channel_id") == interaction.channel.id and data.get("open"):
                ticket_entry = data
                break

        if not ticket_entry:
            return await interaction.response.send_message(
                embed=discord.Embed(description="❌ This is not an active ticket channel.", color=0xED4245),
                ephemeral=True
            )

        panel_id = ticket_entry.get("panel_id", "")
        panels = get_panels()
        panel = panels.get(panel_id, {})
        support_role = interaction.guild.get_role(panel.get("support_role_id", 0))

        is_staff = (support_role and support_role in interaction.user.roles) or interaction.user.guild_permissions.administrator
        is_opener = interaction.user.id == ticket_entry.get("opened_by")

        if not (is_staff or is_opener):
            return await interaction.response.send_message(
                embed=discord.Embed(description="❌ You don't have permission to close this ticket.", color=0xED4245),
                ephemeral=True
            )

        embed = discord.Embed(
            title="🔒 Close this ticket?",
            description=f"Requested by {interaction.user.mention}",
            color=0xED4245,
            timestamp=datetime.utcnow()
        )
        view = TicketCloseConfirmView(panel_id, ticket_entry.get("opened_by"))
        await interaction.response.send_message(embed=embed, view=view)

    @commands.command(name="ticketadd")
    @commands.has_permissions(manage_channels=True)
    async def ticket_add(self, ctx, member: discord.Member):
        tickets = get_tickets()
        if not any(d.get("channel_id") == ctx.channel.id and d.get("open") for d in tickets.values()):
            return await ctx.send(embed=discord.Embed(description="❌ This is not an active ticket channel.", color=0xED4245))
        await ctx.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)
        await ctx.send(embed=discord.Embed(description=f"✅ {member.mention} added to this ticket.", color=0x57F287))

    @app_commands.command(name="ticketadd", description="Add a member to the current ticket")
    @app_commands.describe(member="Member to add")
    @app_commands.default_permissions(manage_channels=True)
    async def ticket_add_slash(self, interaction: discord.Interaction, member: discord.Member):
        tickets = get_tickets()
        if not any(d.get("channel_id") == interaction.channel.id and d.get("open") for d in tickets.values()):
            return await interaction.response.send_message(
                embed=discord.Embed(description="❌ This is not an active ticket channel.", color=0xED4245),
                ephemeral=True
            )
        await interaction.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)
        await interaction.response.send_message(
            embed=discord.Embed(description=f"✅ {member.mention} added to this ticket.", color=0x57F287)
        )

    @commands.command(name="ticketremove")
    @commands.has_permissions(manage_channels=True)
    async def ticket_remove(self, ctx, member: discord.Member):
        tickets = get_tickets()
        if not any(d.get("channel_id") == ctx.channel.id and d.get("open") for d in tickets.values()):
            return await ctx.send(embed=discord.Embed(description="❌ This is not an active ticket channel.", color=0xED4245))
        await ctx.channel.set_permissions(member, overwrite=None)
        await ctx.send(embed=discord.Embed(description=f"✅ {member.mention} removed from this ticket.", color=0xED4245))

    @app_commands.command(name="ticketremove", description="Remove a member from the current ticket")
    @app_commands.describe(member="Member to remove")
    @app_commands.default_permissions(manage_channels=True)
    async def ticket_remove_slash(self, interaction: discord.Interaction, member: discord.Member):
        tickets = get_tickets()
        if not any(d.get("channel_id") == interaction.channel.id and d.get("open") for d in tickets.values()):
            return await interaction.response.send_message(
                embed=discord.Embed(description="❌ This is not an active ticket channel.", color=0xED4245),
                ephemeral=True
            )
        await interaction.channel.set_permissions(member, overwrite=None)
        await interaction.response.send_message(
            embed=discord.Embed(description=f"✅ {member.mention} removed from this ticket.", color=0xED4245)
        )

    @commands.command(name="ticketlist")
    @commands.has_permissions(manage_channels=True)
    async def ticket_list(self, ctx):
        tickets = get_tickets()
        guild_id = str(ctx.guild.id)
        open_tickets = [d for k, d in tickets.items() if k.startswith(guild_id) and d.get("open")]

        if not open_tickets:
            return await ctx.send(embed=discord.Embed(description="📭 No open tickets right now.", color=0x5865F2))

        embed = discord.Embed(
            title=f"📋 Open Tickets — {len(open_tickets)}",
            color=0x5865F2,
            timestamp=datetime.utcnow()
        )
        for t in open_tickets[:25]:
            ch = ctx.guild.get_channel(t.get("channel_id", 0))
            opener = ctx.guild.get_member(t.get("opened_by", 0))
            opened_at = t.get("opened_at", "")
            ts = f"<t:{int(datetime.fromisoformat(opened_at).timestamp())}:R>" if opened_at else "Unknown"
            embed.add_field(
                name=ch.name if ch else "Unknown",
                value=f"By: {opener.mention if opener else 'Unknown'}\nOpened: {ts}",
                inline=True
            )
        await ctx.send(embed=embed)

    @app_commands.command(name="ticketlist", description="List all open tickets in this server")
    @app_commands.default_permissions(manage_channels=True)
    async def ticket_list_slash(self, interaction: discord.Interaction):
        tickets = get_tickets()
        guild_id = str(interaction.guild.id)
        open_tickets = [d for k, d in tickets.items() if k.startswith(guild_id) and d.get("open")]

        if not open_tickets:
            return await interaction.response.send_message(
                embed=discord.Embed(description="📭 No open tickets right now.", color=0x5865F2),
                ephemeral=True
            )

        embed = discord.Embed(
            title=f"📋 Open Tickets — {len(open_tickets)}",
            color=0x5865F2,
            timestamp=datetime.utcnow()
        )
        for t in open_tickets[:25]:
            ch = interaction.guild.get_channel(t.get("channel_id", 0))
            opener = interaction.guild.get_member(t.get("opened_by", 0))
            opened_at = t.get("opened_at", "")
            ts = f"<t:{int(datetime.fromisoformat(opened_at).timestamp())}:R>" if opened_at else "Unknown"
            embed.add_field(
                name=ch.name if ch else "Unknown",
                value=f"By: {opener.mention if opener else 'Unknown'}\nOpened: {ts}",
                inline=True
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ticket_setup.error
    @ticket_config.error
    async def admin_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(embed=discord.Embed(description="❌ You need **Administrator** permission for this.", color=0xED4245))


async def setup(bot):
    await bot.add_cog(Ticket(bot))
