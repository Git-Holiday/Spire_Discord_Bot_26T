import logging
import discord
from discord.ext import commands
from config import TOKEN, GUILD_ID
from database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


class SpireBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await init_db()
        await self.load_extension("cogs.reservations")
        await self.load_extension("cogs.scheduler")
        log.info("Extensions loaded")

        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("Slash commands synced to guild %s", GUILD_ID)
        else:
            await self.tree.sync()
            log.info("Slash commands synced globally")

    async def on_ready(self):
        log.info("Logged in as %s (ID: %s)", self.user, self.user.id)


def main():
    bot = SpireBot()
    bot.run(TOKEN)


if __name__ == "__main__":
    main()
