import discord
from pathlib import Path
from datetime import datetime as datetimefix

version = "0.3"
admin_account_ids = [835883093662761000,884407684693110795]
bot_ids = [925520778408103977, 873133022973665290]
testing_guild_id = 925749115252523069

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
    empty = "<:empty:906884148336148490>"
    patron = "<:patron:906886393433841734>"
    belarus_wrw = "<:flag_belaruswrw:1094640810802303108>"
    ru_wbw = "<:flag_ruwbw:1094640813759266898>"
    east_turk = "<:flag_eastturk:1094642530957656144>"
    lichess = "<:lichess:1094643348062601266>"
    inaccuracy = "<:inaccuracy:1106975468718141522>"
    mistake = "<:mistake:1106965586547843072>"
    blunder = "<:blunder:1106975472945987624>"

language_emojis = {"en": "🇬🇧", "uk": "🇺🇦"}

class CustomColors:
    cyan = discord.Color.from_rgb(0,255,255)
    red = discord.Color.from_rgb(255, 0, 0)
    saffron = discord.Color.from_rgb(245, 220, 59)
    dark_red = discord.Color.dark_red()

wov_season_resets = [datetimefix(2022,10,18,3),datetimefix(2022,11,30,3), datetimefix(2023,7,3,3)]

class LogFiles:
    wolvesville_log = Path('bot_logs/', 'Wolvesville.log')
    functions_log = Path('bot_logs/', 'functions.log')
    main_log = Path('bot_logs/', 'main.log')
    account_system_log = Path('bot_logs/', 'accountSystem.log')
    chess_log = Path('bot_logs/', 'chess.log')
    s_games_log = Path('bot_logs/', 'smallGames.log')
    database_main_log = Path('bot_logs/', 'database.log')
    adventure_log = Path('bot_logs/', 'adventure.log')
    gf_log = Path('bot_logs/', 'gf.log')
    special_log = Path('bot_logs/', 'special.log')

launch_variables = {
    "local_db": False,
    "rewrite_userdata": False
}
