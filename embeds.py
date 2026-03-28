"""
Helpers for building Discord embeds and button views.
"""
import datetime
import discord
from config import TABLES, SLOTS, TABLE_MAP, SLOT_MAP
from typing import Optional


# ── Single daily post embed ───────────────────────────────────────────────────

def _slot_status(res: Optional[dict]) -> str:
    if res is None or res.get("confirmed") == 0:
        return "✅ Available"
    confirmed = res.get("confirmed")
    name = res["username"]
    return f"⏳ {name}" if confirmed is None else f"✔️ {name}"


def make_single_post_embed(date: datetime.date, all_reservations: list) -> discord.Embed:
    day_str = date.strftime("%A, %d %B %Y")

    # Build lookup: {table_id: {slot_id: reservation}}
    res_map: dict[int, dict] = {}
    for r in all_reservations:
        if r.get("confirmed") != 0:          # exclude cancelled
            res_map.setdefault(r["table_id"], {})[r["slot_id"]] = r

    type_labels = {
        "Standard": "8×4 Standard",
        "Raised":   "6×4 Raised",
        "Low":      "6×4 Low",
        "Hobby":    "Small workspace",
    }

    embed = discord.Embed(
        title=f"📅 Table Reservations — {day_str}",
        description=(
            "Use the dropdown below to book a slot. "
            "You'll get a DM confirmation on the morning of your session."
        ),
        colour=discord.Colour.blurple(),
    )

    for table in TABLES:
        table_res = res_map.get(table["id"], {})
        lines = []
        for slot in SLOTS:
            status = _slot_status(table_res.get(slot["id"]))
            lines.append(f"{slot['emoji']} **{slot['name']}** ({slot['time']}):  {status}")

        embed.add_field(
            name=f"{table['emoji']} {table['name']}  ·  {type_labels.get(table['type'], table['type'])}",
            value="\n".join(lines),
            inline=False,
        )

    embed.set_footer(text="Green = available  ·  ⏳ = unconfirmed  ·  ✔️ = confirmed")
    return embed


# ── Booking select (dropdown) ─────────────────────────────────────────────────

def make_booking_select(date_str: str, all_reservations: list) -> discord.ui.View:
    """
    Dropdown showing all available slots to book, plus a 'manage' option.
    custom_id = "book_select:{date}" — caught by on_interaction in reservations.py.
    """
    taken: dict[tuple, dict] = {}
    for r in all_reservations:
        if r.get("confirmed") != 0:
            taken[(r["table_id"], r["slot_id"])] = r

    type_short = {"Standard": "8×4 Std", "Raised": "6×4 Raised", "Low": "6×4 Low", "Hobby": "Small"}

    options: list[discord.SelectOption] = []
    for table in TABLES:
        for slot in SLOTS:
            if (table["id"], slot["id"]) not in taken:
                options.append(discord.SelectOption(
                    label=f"{table['name']} — {slot['name']} ({slot['time']})",
                    value=f"book:{table['id']}:{slot['id']}",
                    emoji=table["emoji"],
                    description=type_short.get(table["type"], table["type"]),
                ))

    if not options:
        options.append(discord.SelectOption(
            label="No tables available — check back later",
            value="none",
            emoji="😴",
        ))

    options.append(discord.SelectOption(
        label="Cancel one of my reservations",
        value="manage",
        emoji="🗑️",
        description="View and cancel your existing bookings",
    ))

    # Discord hard cap: 25 options
    if len(options) > 25:
        options = options[:24] + [options[-1]]   # keep manage at end

    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Select(
        placeholder="📋  Choose a table and time slot to book...",
        options=options,
        custom_id=f"book_select:{date_str}",
    ))
    return view


# ── DM confirmation embed + view ─────────────────────────────────────────────

def make_dm_embed(table: dict, slot: dict, date: datetime.date) -> discord.Embed:
    day_str = date.strftime("%A, %d %B %Y")
    type_labels = {"Standard": "Standard", "Raised": "Raised", "Low": "Low", "Hobby": "Hobby"}
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
