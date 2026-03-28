"""
Helpers for building Discord embeds and button views.
"""
import datetime
import discord
from config import TABLES, SLOTS, TABLE_MAP, SLOT_MAP
from typing import Optional


# ── Header embed (posted once per day in the channel) ────────────────────────

def make_header_embed(date: datetime.date) -> discord.Embed:
    day_str = date.strftime("%A, %d %B %Y")
    embed = discord.Embed(
        title=f"📅 Table Reservations — {day_str}",
        description=(
            "Reserve a gaming table for today by clicking into the thread below "
            "and pressing an available slot button.\n\n"
            "**⏱ Time Slots**\n"
            "🌅 **Morning** · 10:00–13:00\n"
            "☀️ **Afternoon** · 13:00–17:00\n"
            "🌆 **Evening** · 17:00–21:00\n\n"
            "**🗺 Tables**\n"
            "🟫 Tables 1–3 · 8×4 Standard\n"
            "🟦 Tables 4–5 · 6×4 Raised\n"
            "🟩 Table 6 · 6×4 Low\n"
            "🎨 Hobby Table · Small workspace at the back\n\n"
            "*You'll receive a DM confirmation on the morning of your reservation.*"
        ),
        colour=discord.Colour.blurple(),
    )
    embed.set_footer(text="Click a green slot to book · Click your own booking to cancel")
    return embed


# ── Per-table embed ───────────────────────────────────────────────────────────

def _slot_field_value(reservation: Optional[dict]) -> str:
    if reservation is None:
        return "✅ Available"
    confirmed = reservation.get("confirmed")
    name = reservation["username"]
    if confirmed is None:
        return f"⏳ {name}"
    if confirmed:
        return f"✔️ {name}"
    return "✅ Available"  # was cancelled


def make_table_embed(table: dict, reservations: dict) -> discord.Embed:
    """
    reservations: {slot_id (int): reservation dict | None}
    """
    type_labels = {
        "Standard": "Standard Gaming Table",
        "Raised":   "Raised Gaming Table",
        "Low":      "Low Gaming Table",
        "Hobby":    "Hobby / Painting Workspace",
    }
    label = type_labels.get(table["type"], table["type"])
    embed = discord.Embed(
        title=f"{table['emoji']} {table['name']} · {table['size']} {label}",
        colour=table["colour"],
    )
    for slot in SLOTS:
        res = reservations.get(slot["id"])
        embed.add_field(
            name=f"{slot['emoji']} {slot['name']} ({slot['time']})",
            value=_slot_field_value(res),
            inline=True,
        )
    return embed


# ── Per-table button view ─────────────────────────────────────────────────────

def make_table_view(date_str: str, table_id: int, reservations: dict) -> discord.ui.View:
    """
    reservations: {slot_id (int): reservation dict | None}
    Buttons with custom_id "res:{date}:{table_id}:{slot_id}" are caught by
    the on_interaction listener in cogs/reservations.py.
    """
    view = discord.ui.View(timeout=None)
    for slot in SLOTS:
        res = reservations.get(slot["id"])
        custom_id = f"res:{date_str}:{table_id}:{slot['id']}"

        # Cancelled reservations are treated as available
        is_available = res is None or res.get("confirmed") == 0

        if is_available:
            btn = discord.ui.Button(
                style=discord.ButtonStyle.success,
                label=f"{slot['emoji']} {slot['name']}",
                custom_id=custom_id,
            )
        else:
            # Show who booked it; the callback decides if the clicker can cancel
            uname = res["username"][:20]
            btn = discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label=f"👤 {uname}",
                custom_id=custom_id,
            )
        view.add_item(btn)
    return view


# ── DM confirmation embed + view ─────────────────────────────────────────────

def make_dm_embed(table: dict, slot: dict, date: datetime.date) -> discord.Embed:
    day_str = date.strftime("%A, %d %B %Y")
    type_labels = {
        "Standard": "Standard",
        "Raised":   "Raised",
        "Low":      "Low",
        "Hobby":    "Hobby",
    }
    embed = discord.Embed(
        title="🎲 Table Reservation — Confirm for Today",
        description=(
            f"Hey! You've got a gaming table reserved for **today**.\n\n"
            f"**{table['emoji']} {table['name']}** · {table['size']} "
            f"{type_labels.get(table['type'], table['type'])}\n"
            f"**{slot['emoji']} {slot['name']}** · {slot['time']}\n"
            f"**📅 {day_str}**\n\n"
            f"Please confirm below so we know you're coming, or cancel to free "
            f"the table for someone else."
        ),
        colour=table["colour"],
    )
    embed.set_footer(text="If you don't respond your reservation stays active.")
    return embed


def make_dm_view(date_str: str, table_id: int, slot_id: int) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(
        style=discord.ButtonStyle.success,
        label="✅ Confirm — I'll be there!",
        custom_id=f"dm_confirm:{date_str}:{table_id}:{slot_id}",
    ))
    view.add_item(discord.ui.Button(
        style=discord.ButtonStyle.danger,
        label="❌ Cancel — Free this table",
        custom_id=f"dm_cancel:{date_str}:{table_id}:{slot_id}",
    ))
    return view
