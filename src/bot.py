import argparse
import logging
from datetime import timedelta
from os import environ as environ

import hikari
import uvicorn
from howblox_lib import load_modules, execute_deferred_module_functions, get_environment, Environment
from howblox_lib.database import redis

from resources.howblox import howblox
from config import CONFIG

# Load a few modules
from resources.commands import handle_interaction, sync_commands
from resources.constants import MODULES
from web.webserver import application


parser = argparse.ArgumentParser()
parser.add_argument(
    "-s", "--sync-commands",
    action="store_true",
    help="sync commands and bypass the cooldown",
    required=False,
    default=False)
parser.add_argument(
    "-c", "--clear-redis",
    action="store_true",
    help="local only, clears redis",
    required=False,
    default=False)
parser.add_argument(
    "-d", "--debug",
    action="store_true",
    help="enable debug logging format",
    required=False,
    default=False)
args = parser.parse_args()

if args.debug:
    logging.basicConfig(level=logging.DEBUG, force=True, format="%(asctime)s:%(levelname)s:%(name)s:%(message)s")


@application.on_start
async def handle_start(_):
    """Start the howblox and sync commands"""

    await howblox.start()

    execute_deferred_module_functions()

    # only sync commands once every hour unless the --sync-commands flag is passed
    if args.sync_commands or not await redis.get("synced_commands"):
        await redis.set("synced_commands", "true", expire=timedelta(hours=1))
        await sync_commands()
    else:
        logging.info("Skipping command sync. Run with --sync-commands or -s to force sync.")

    if get_environment() == Environment.LOCAL and args.clear_redis:
        await redis.flushall()
        logging.info("Cleared redis. Run with --clear-redis or -c to force clear.")


@application.on_stop
async def handle_stop(_):
    """Executes when the howblox is stopped"""

    await howblox.close()


# cannot be in __main__ or the reload won't load the commands and modules
for interaction_type in (hikari.CommandInteraction, hikari.ComponentInteraction, hikari.AutocompleteInteraction, hikari.ModalInteraction):
    howblox.interaction_server.set_listener(interaction_type, handle_interaction)

load_modules(*MODULES, starting_path="src/", execute_deferred_modules=False)

# Initialize the howblox http web server
# IMPORTANT NOTE: blacksheep expects a trailing /
# in the URL that is given to discord because this is a mount.
# Example: "example.org/bot/" works, but "example.org/bot" does not (this results in a 307 reply, which discord doesn't honor).
application.mount("/bot", howblox)

if __name__ == "__main__":
    uvicorn.run(
        "web.webserver:application",
        host=env.get("HOST", CONFIG.HOST),
        port=int(env.get("PORT", CONFIG.PORT)),
        # lifespan="on",
        # log_level="info",
        reload=get_environment() == Environment.LOCAL,
        reload_dirs=["src"]
    )