"""
Scheduler cog — posts the daily reservation message and sends confirmation DMs.
"""
import datetime
import logging
import discord
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from config import (
    RESERVATIONS_CHANNEL_ID,
    TIMEZONE,
    DAILY_POST_HOUR,
    DAILY_POST_MINUTE,
    CONFIRMATION_HOUR,
    CONFIRMATION_MINUTE,
    TABLE_MAP,
    SLOT_MAP,
)
from database import (
    get_daily_post,
    save_daily_post,
    get_unconfirmed_reservations_for_date,
)
from embeds import make_single_post_embed, make_booking_select, make_dm_embed, make_dm_view

log = logging.getLogger(__name__)


async def post_daily_reservations(bot: discord.Client) -> None:
    """Post (or re-post) the single daily reservation message."""
    channel = bot.get_channel(RESERVATIONS_CHANNEL_ID)
    if channel is None:
        channel = await bot.fetch_channel(RESERVATIONS_CHANNEL_ID)

    today    = datetime.date.today()
    date_str = today.isoformat()

    existing = await get_daily_post(date_str)
    if existing:
        log.info("Daily post for %s already exists — skipping", date_str)
        return

    embed = make_single_post_embed(today, [])
    view  = make_booking_select(date_str, [])
    msg   = await channel.send(embed=embed, view=view)

    await save_daily_post(date_str, channel.id, msg.id)
    log.info("Daily reservation post created for %s (message %s)", date_str, msg.id)


async def send_confirmation_dms(bot: discord.Client) -> int:
    """DM every user with an unconfirmed reservation today. Returns count sent."""
    date_str = datetime.date.today().isoformat()
    today    = datetime.date.today()
    pending  = await get_unconfirmed_reservations_for_date(date_str)

    sent = 0
    for res in pending:
        table = TABLE_MAP[res["table_id"]]
        slot  = SLOT_MAP[res["slot_id"]]
        try:
            user = await bot.fetch_user(res["user_id"])
        except discord.NotFound:
            log.warning("User %s not found — skipping DM", res["user_id"])
            continue
        try:
            await user.send(
                embed=make_dm_embed(table, slot, today),
                view=make_dm_view(date_str, table["id"], slot["id"]),
            )
            sent += 1
            log.info("Confirmation DM → %s  (%s, %s)", user, table["name"], slot["name"])
        except discord.Forbidden:
            log.warning("Cannot DM %s — DMs disabled", user)
        except Exception as e:
            log.error("Error DMing %s: %s", user, e)

    return sent


class SchedulerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        tz = pytz.timezone(TIMEZONE)
        self.scheduler = AsyncIOScheduler(timezone=tz)
        self.scheduler.add_job(
            self._daily_post_job,
            CronTrigger(hour=DAILY_POST_HOUR, minute=DAILY_POST_MINUTE, timezone=tz),
            id="daily_post",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self._confirmation_dm_job,
            CronTrigger(hour=CONFIRMATION_HOUR, minute=CONFIRMATION_MINUTE, timezone=tz),
            id="confirmation_dms",
            replace_existing=True,
        )

    async def _daily_post_job(self):
        log.info("Scheduled: daily post")
        try:
            await post_daily_reservations(self.bot)
        except Exception as e:
            log.error("Daily post failed: %s", e)

    async def _confirmation_dm_job(self):
        log.info("Scheduled: confirmation DMs")
        try:
            count = await send_confirmation_dms(self.bot)
            log.info("Sent %d confirmation DM(s)", count)
        except Exception as e:
            log.error("Confirmation DMs failed: %s", e)

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.scheduler.running:
            self.scheduler.start()
            log.info(
                "Scheduler started — post at %02d:%02d, DMs at %02d:%02d (%s)",
                DAILY_POST_HOUR, DAILY_POST_MINUTE,
                CONFIRMATION_HOUR, CONFIRMATION_MINUTE,
                TIMEZONE,
            )

    def cog_unload(self):
        self.scheduler.shutdown(wait=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(SchedulerCog(bot))
