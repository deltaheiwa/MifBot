from discord.ext import commands

from bot_util import bot_config
from bot_util.exceptions import NotAuthorizedError


def dev_command():
    def predicate(ctx):
        if ctx.message.author.id not in bot_config.admin_account_ids:
            raise NotAuthorizedError("You have no permissions to use this command")
        return True

    return commands.check(predicate)
