import discord
from pathlib import Path
from datetime import datetime as dt
from dotenv import load_dotenv
import json

load_dotenv("../creds/.env")

perma_config = json.load(open("./bot_util/bot_config_perma.json", "r"))

_DEV_BOT_ID = perma_config["testing_bot_id"]
_PROD_BOT_ID = perma_config["production_bot_id"]

IS_DEV_BUILD = perma_config["is_dev_build"]

version = perma_config["version"]
admin_account_ids = perma_config["admin_account_ids"]
bot_ids = [_DEV_BOT_ID, _PROD_BOT_ID]
wov_bot_id: str = perma_config["wov_bot_id"]
testing_guild_id = perma_config["testing_guild_id"]
main_guild_id = perma_config["main_guild_id"]
telegram_chat_id: list[int] = perma_config["telegram_chat_ids"]


class CustomEmojis:
    empty = "<:empty:906884148336148490>"
    question_mark = "<:Question_Mark_fixed:944588141405282335>"
    spinning_coin = "<a:spinning_coin:898938296955207781>"
    single_rose = "<:single_rose:1027129510824513556>"
    rerequest = "<:rerequest:1028621247594110976>"
    loading = "<a:loading:1034472194941665391>"
    checkmark_button = "<:checkmark:1035669378173239346>"
    crossmark_button = "<:crossmark:1035669461392433305>"
    progress_down = "<:arrowDown:907730161556938762>"
    progress_up = "<:arrowUp:907730161498218596>"
    patron = "<:patron:906886393433841734>"
    belarus_wrw = "<:flag_belaruswrw:1094640810802303108>"
    ru_wbw = "<:flag_ruwbw:1094640813759266898>"
    east_turk = "<:flag_eastturk:1094642530957656144>"
    lichess = "<:lichess:1094643348062601266>"
    inaccuracy = "<:inaccuracy:1106975468718141522>"
    mistake = "<:mistake:1106965586547843072>"
    blunder = "<:blunder:1106975472945987624>"
    gray_no_entry_sign = "<:gray_no_entry_sign:1223222302162812971>"
    chess_staff = "<:CDC_staff:1223226765783072808>"
    chess_mod = "<:CDC_mod:1223227292352905216>"
    twitch_logo = "<:twitch:1223378528934953060>"


language_emojis = {"en": "🇬🇧", "uk": "🇺🇦"}


class CustomColors:
    cyan = discord.Color.from_rgb(0, 255, 255)
    red = discord.Color.from_rgb(255, 0, 0)
    saffron = discord.Color.from_rgb(245, 220, 59)
    dark_red = discord.Color.dark_red()
    green = discord.Color.from_rgb(0, 255, 0)


class Chess:
    default_avatar_url = "https://i.ibb.co/K0VHbFT/user-image-007dad08.png"


wov_season_resets = [
    dt(2024, 3, 17, 3),
    dt(2024, 4, 29, 3),
]


class LogFiles:
    wolvesville_log = Path("bot_logs/", "Wolvesville.log")
    functions_log = Path("bot_logs/", "functions.log")
    main_log = Path("bot_logs/", "main.log")
    account_system_log = Path("bot_logs/", "accountSystem.log")
    chess_log = Path("bot_logs/", "chess.log")
    s_games_log = Path("bot_logs/", "smallGames.log")
    database_main_log = Path("bot_logs/", "database.log")
    adventure_log = Path("bot_logs/", "adventure.log")
    gf_log = Path("bot_logs/", "gf.log")
    special_log = Path("bot_logs/", "special.log")
    telegram_log = Path("bot_logs/", "telegram.log")


launch_variables = {
    "local_db": False,
    "rewrite_userdata": False,
    "telegram_bot": True,
}
