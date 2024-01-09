import json

from bot_util import bot_config
from bot_util.misc import Logger

logger = Logger("bot_util.functions.config")

def add_telegram_chat(chat_id: int):
    try:
        if chat_id not in bot_config.telegram_chat_id:
            bot_config.telegram_chat_id.append(chat_id)
            with open("bot_config_perma.json", "r") as f:
                json_file = json.load(f)
            json_file["telegram_chat_id"] = bot_config.telegram_chat_id
            with open("bot_config_perma.json", "w") as f:
                json.dump(json_file, f)
            logger.info(f"Chat id {chat_id} added")
            return True
        else:
            return False
    except Exception:
        logger.exception("Error in add_telegram_chat")
        return False

def remove_telegram_chat(chat_id: int):
    try:
        if chat_id in bot_config.telegram_chat_id:
            bot_config.telegram_chat_id.remove(chat_id)
            with open("bot_config_perma.json", "r") as f:
                json_file = json.load(f)
            json_file["telegram_chat_id"] = bot_config.telegram_chat_id
            with open("bot_config_perma.json", "w") as f:
                json.dump(json_file, f)
            logger.info(f"Chat id {chat_id} removed")
            return True
        else:
            return False
    except Exception:
        logger.exception("Error in remove_telegram_chat")
        return False

async def init_bot(bot):
    # if bot_config.launch_variables["rewrite_userdata"]:
    #     await mysql_main.DatabaseFunctions.iterate_userdata("json_stats")
    #     bot_config.launch_variables["rewrite_userdata"] = False
    if bot_config.launch_variables["telegram_bot"]:
        from telegram_helper.main import MifTelegramReporter

        bot.telegram_bot = MifTelegramReporter(bot.application_id)
        await bot.telegram_bot.run()



