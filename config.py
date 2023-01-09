import discord
from pathlib import Path
from datetime import datetime as datetimefix

version = "0.2.3.1"
admin_account_ids = [884407684693110795, 835883093662761000]
bot_ids = [925520778408103977, 873133022973665290]
testing_guild_id = 925749115252523069

class CustomEmojis:
    empty = "<:empty:906884148336148490>"
    question_mark = "<:Question_Mark_fixed:944588141405282335>"
    spinning_coin = "<a:spinning_coin:898938296955207781>"
    single_rose = "<:single_rose:1027129510824513556>"
    rerequest = "<:rerequest:1028621247594110976>"
    loading = "<a:loading:1034472194941665391>"
    checkmark_button = "<:checkmark:1035669378173239346> "
    crossmark_button = "<:crossmark:1035669461392433305>"

class CustomColors:
    cyan = discord.Color.from_rgb(0,255,255)
    red = discord.Color.from_rgb(255, 0, 0)
    saffron = discord.Color.from_rgb(245, 220, 59)
    dark_red = discord.Color.dark_red()

wov_season_resets = [datetimefix(2022,10,18,3),datetimefix(2022,11,30,3)]

wolvesville_log_debug = Path('bot_logs/', 'Wolvesville.log')
functions_log = Path('bot_logs/', 'functions.log')
functions_log_debug = Path('bot_logs/', 'functions_debug.log')
main_log = Path('bot_logs/', 'main.log')
account_system_log = Path('bot_logs/', 'accountSystem.log')
chess_log = Path('bot_logs/', 'chess.log')
s_games_log_debug = Path('bot_logs/', 'smallGames.log')
