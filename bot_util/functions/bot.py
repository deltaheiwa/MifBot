import math

import discord
from functools import lru_cache

from db_data import database_main
from bot_util.misc import Logger
from bot_util import bot_config

logger = Logger(__name__, log_file_path=bot_config.LogFiles.functions_log)


async def determine_prefix(client: discord.Client, message: discord.Message) -> str:
    try:
        user_pref = await database_main.PrefixDatabase.return_prefix(
            _id=message.author.id, user=True
        )
        guild_pref = (
            await database_main.PrefixDatabase.return_prefix(_id=message.guild.id)
            if message.guild
            else None
        )
        if user_pref is None or user_pref != message.content[0 : len(user_pref)]:
            prefix = guild_pref or "."
        else:
            prefix = user_pref
        return prefix
    except Exception as e:
        logger.exception(f"Error in determine_prefix: {e}")
        await client.telegram_bot.send_automatic_exception(
            e,
            func=determine_prefix,
            line=e.__traceback__.tb_lineno,
            extra=f"Message: {message.content}",
        )
        return "."

@lru_cache(maxsize=None)
def coins_formula(day, multiplier):
    max_coins = 10000  # The asymptotic limit
    growth_rate = 0.1  # The rate of growth
    mid_point = 30  # The midpoint of the curve (the point of maximum growth, aka day)
    min_coins = 10  # The minimum number of coins that can be earned

    # logistic growth formula
    coins_bonus = max_coins / (1 + math.exp(-growth_rate * (day - mid_point)))

    # shift the curve down so that it starts at min_coins
    coins_bonus -= max_coins / (1 + math.exp(growth_rate * mid_point))

    # adjust based on multiplier and add min_coins
    coins_bonus = coins_bonus * multiplier + min_coins

    logger.debug(f"{round(coins_bonus)} day: {day}, m: {multiplier}")
    return coins_bonus
