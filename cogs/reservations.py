"""
Reservation cog — handles all button interactions and slash commands.
"""
import datetime
import logging
import discord
from discord import app_commands
from discord.ext import commands

from config import TABLE_MAP, SLOT_MAP, TABLES, SLOTS, GUILD_ID
from database import (
    create_reservation,
    delete_reservation,
    admin_delete_reservation,
    get_reservation,
    get_day_reservations,
    get_user_reservations_for_date,
    update_confirmation,
    get_daily_post,
)
from embeds import make_table_embed, make_table_view, make_dm_embed, make_dm_view

log = logging.getLogger(__name__)


def _today() -> str:
    return datetime.date.today().isoformat()


async def refresh_table_message(bot: discord.Client, date_str: str, table_id: int):
    """Re-renders a table's thread message with current booking state."""
    daily = await get_daily_post(date_str)
    if not daily:
        return

    msg_id = daily["table_message_ids"].get(str(table_id))
    if not msg_id:
        return

    thread = bot.get_channel(daily["thread_id"])
    if thread is None:
        try:
            thread = await bot.fetch_channel(daily["thread_id"])
        except Exception:
            log.warning("Could not fetch thread %s", daily["thread_id"])
            return

    try:
        message = await thread.fetch_message(msg_id)
    except Exception:
        log.warning("Could not fetch table message %s", msg_id)
        return

    all_res = await get_day_reservations(date_str)
    table_res = {r["slot_id"]: r for r in all_res if r["table_id"] == table_id}

    table = TABLE_MAP[table_id]
    await message.edit(
        embed=make_table_embed(table, table_res),
        view=make_table_view(date_str, table_id, table_res),
    )


class ReservationsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Interaction router ────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component:
            return

        cid = interaction.data.get("custom_id", "")

        if cid.startswith("res:"):
            await self._handle_slot_button(interaction, cid)
        elif cid.startswith("cancel_yes:"):
            await self._handle_self_cancel(interaction, cid)
        elif cid.startswith("cancel_no:"):
            await interaction.response.edit_message(
                content="👍 Your reservation is still active.", view=None
            )
        elif cid.startswith("dm_confirm:"):
            await self._handle_dm_response(interaction, cid, confirmed=True)
        elif cid.startswith("dm_cancel:"):
            await self._handle_dm_response(interaction, cid, confirmed=False)

    # ── Slot button (book / cancel / show info) ───────────────────────────────

    async def _handle_slot_button(self, interaction: discord.Interaction, cid: str):
        _, date_str, table_id_s, slot_id_s = cid.split(":")
        table_id = int(table_id_s)
        slot_id  = int(slot_id_s)
        user     = interaction.user
        table    = TABLE_MAP[table_id]
        slot     = SLOT_MAP[slot_id]

        existing = await get_reservation(date_str, table_id, slot_id)

        # Treat a cancelled reservation as available
        is_available = existing is None or existing.get("confirmed") == 0

        if is_available:
            ok = await create_reservation(
                date_str, table_id, slot_id, user.id, user.display_name
            )
            if ok:
                await interaction.response.send_message(
                    f"✅ **{table['name']}** — **{slot['name']}** ({slot['time']}) booked!\n"
                    f"You'll get a DM reminder on the morning of your session.",
                    ephemeral=True,
                )
                await refresh_table_message(self.bot, date_str, table_id)
            else:
                await interaction.response.send_message(
                    f"❌ Just missed it — **{table['name']}** {slot['name']} was "
                    f"taken by someone else. Try another slot!",
                    ephemeral=True,
                )

        elif existing["user_id"] == user.id:
            # User owns this booking — offer to cancel
            view = discord.ui.View(timeout=60)
            view.add_item(discord.ui.Button(
                style=discord.ButtonStyle.danger,
                label="❌ Yes, cancel my reservation",
                custom_id=f"cancel_yes:{date_str}:{table_id}:{slot_id}",
            ))
            view.add_item(discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label="Keep my reservation",
                custom_id=f"cancel_no:{date_str}:{table_id}:{slot_id}",
            ))
            await interaction.response.send_message(
                f"You have **{table['name']}** booked for **{slot['name']}** "
                f"({slot['time']}) on {date_str}.\nWould you like to cancel it?",
                view=view,
                ephemeral=True,
            )

        else:
            await interaction.response.send_message(
                f"❌ **{table['name']}** {slot['name']} is booked by "
                f"**{existing['username']}**.",
                ephemeral=True,
            )

    # ── Self-cancel confirmation ───────────────────────────────────────────────

    async def _handle_self_cancel(self, interaction: discord.Interaction, cid: str):
        _, date_str, table_id_s, slot_id_s = cid.split(":")
        table_id = int(table_id_s)
        slot_id  = int(slot_id_s)
        table    = TABLE_MAP[table_id]
        slot     = SLOT_MAP[slot_id]

        removed = await delete_reservation(date_str, table_id, slot_id, interaction.user.id)
        if removed:
            await interaction.response.edit_message(
                content=f"✅ Your **{table['name']}** {slot['name']} reservation has been cancelled.",
                view=None,
            )
            await refresh_table_message(self.bot, date_str, table_id)
        else:
            await interaction.response.edit_message(
                content="⚠️ Could not find your reservation — it may already be cancelled.",
                view=None,
            )

    # ── DM confirm / cancel ───────────────────────────────────────────────────

    async def _handle_dm_response(
        self, interaction: discord.Interaction, cid: str, confirmed: bool
    ):
        parts     = cid.split(":")
        date_str  = parts[1]
        table_id  = int(parts[2])
        slot_id   = int(parts[3])
        table     = TABLE_MAP[table_id]
        slot      = SLOT_MAP[slot_id]

        existing = await get_reservation(date_str, table_id, slot_id)
        if not existing or existing["user_id"] != interaction.user.id:
            await interaction.response.edit_message(
                content="⚠️ This reservation no longer exists.", view=None
            )
            return

        if confirmed:
            await update_confirmation(date_str, table_id, slot_id, True)
            await interaction.response.edit_message(
                content=(
                    f"✔️ **Confirmed!** See you at **{table['name']}** "
                    f"({slot['name']}, {slot['time']}) — have a great game! 🎲"
                ),
                view=None,
            )
        else:
            await delete_reservation(date_str, table_id, slot_id, interaction.user.id)
            await interaction.response.edit_message(
                content=(
                    f"❌ **Cancelled.** Your **{table['name']}** {slot['name']} "
                    f"reservation has been freed up for someone else."
                ),
                view=None,
            )
            await refresh_table_message(self.bot, date_str, table_id)

    # ── Slash commands ────────────────────────────────────────────────────────

    @app_commands.command(name="my-reservations", description="Show your reservations for today")
    async def my_reservations(self, interaction: discord.Interaction):
        date_str = _today()
        rows = await get_user_reservations_for_date(date_str, interaction.user.id)

        if not rows:
            await interaction.response.send_message(
                "You have no reservations for today.", ephemeral=True
            )
            return

        lines = []
        for r in rows:
            t = TABLE_MAP[r["table_id"]]
            s = SLOT_MAP[r["slot_id"]]
            confirmed = r.get("confirmed")
            status = "⏳ Unconfirmed" if confirmed is None else ("✔️ Confirmed" if confirmed else "❌ Cancelled")
            lines.append(f"{t['emoji']} **{t['name']}** · {s['emoji']} {s['name']} ({s['time']}) — {status}")

        embed = discord.Embed(
            title=f"📋 Your Reservations — {date_str}",
            description="\n".join(lines),
            colour=discord.Colour.blurple(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="reserve", description="Book a table via slash command")
    @app_commands.describe(
        table="Which table to book",
        slot="Which time slot",
    )
    @app_commands.choices(
        table=[app_commands.Choice(name=f"{t['emoji']} {t['name']} ({t['size']} {t['type']})", value=t["id"]) for t in TABLES],
        slot=[app_commands.Choice(name=f"{s['emoji']} {s['name']} ({s['time']})", value=s["id"]) for s in SLOTS],
    )
    async def reserve(
        self,
        interaction: discord.Interaction,
        table: int,
        slot: int,
    ):
        date_str = _today()
        t = TABLE_MAP[table]
        s = SLOT_MAP[slot]

        ok = await create_reservation(date_str, table, slot, interaction.user.id, interaction.user.display_name)
        if ok:
            await interaction.response.send_message(
                f"✅ **{t['name']}** booked for **{s['name']}** ({s['time']}) today!",
                ephemeral=True,
            )
            await refresh_table_message(self.bot, date_str, table)
        else:
            existing = await get_reservation(date_str, table, slot)
            if existing and existing["user_id"] == interaction.user.id:
                await interaction.response.send_message(
                    f"You already have **{t['name']}** {s['name']} booked.", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"❌ **{t['name']}** {s['name']} is already taken.", ephemeral=True
                )

    @app_commands.command(name="admin-cancel", description="[Admin] Cancel any reservation")
    @app_commands.describe(
        table="Table to clear",
        slot="Slot to clear",
        date="Date (YYYY-MM-DD, defaults to today)",
    )
    @app_commands.choices(
        table=[app_commands.Choice(name=f"{t['emoji']} {t['name']}", value=t["id"]) for t in TABLES],
        slot=[app_commands.Choice(name=f"{s['emoji']} {s['name']}", value=s["id"]) for s in SLOTS],
    )
    @app_commands.default_permissions(manage_guild=True)
    async def admin_cancel(
        self,
        interaction: discord.Interaction,
        table: int,
        slot: int,
        date: str = "",
    ):
        date_str = date or _today()
        existing = await get_reservation(date_str, table, slot)
        if not existing:
            await interaction.response.send_message(
                "No reservation found for that table/slot.", ephemeral=True
            )
            return

        t = TABLE_MAP[table]
        s = SLOT_MAP[slot]
        removed = await admin_delete_reservation(date_str, table, slot)
        if removed:
            await interaction.response.send_message(
                f"✅ Cleared **{t['name']}** {s['name']} reservation "
                f"(was held by **{existing['username']}**).",
                ephemeral=True,
            )
            await refresh_table_message(self.bot, date_str, table)
        else:
            await interaction.response.send_message("Failed to remove reservation.", ephemeral=True)

    @app_commands.command(name="admin-post", description="[Admin] Manually trigger today's reservation post")
    @app_commands.default_permissions(manage_guild=True)
    async def admin_post(self, interaction: discord.Interaction):
        from cogs.scheduler import post_daily_reservations
        await interaction.response.defer(ephemeral=True)
        try:
            await post_daily_reservations(self.bot)
            await interaction.followup.send("✅ Daily reservation post created!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

    @app_commands.command(name="admin-send-dms", description="[Admin] Manually send confirmation DMs for today")
    @app_commands.default_permissions(manage_guild=True)
    async def admin_send_dms(self, interaction: discord.Interaction):
        from cogs.scheduler import send_confirmation_dms
        await interaction.response.defer(ephemeral=True)
        try:
            count = await send_confirmation_dms(self.bot)
            await interaction.followup.send(f"✅ Sent {count} confirmation DM(s).", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ReservationsCog(bot))
