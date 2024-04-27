import os
import logging
import re
import shutil
from discord.ext.commands import Context
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, Application
import inspect
from .util.attributes import telegram_command
from .util.functions import is_command
from bot_util.misc import Logger


load_dotenv('../creds/.env')

logger = Logger('mif_telegram_bot', logging.INFO)


class MifTelegramReporter:
    """
    Main class for telegram bot

    REQUIREMENTS:
    - API_KEY environment variable must be set in .env file

    Functions that start with _ are not added as commands
    """
    instance = None  # Singleton instance
    app: Application

    def __new__(cls, *args, **kwargs):
        if not cls.instance:
            cls.instance = super().__new__(cls)
        return cls.instance

    def __init__(self, bot_id: str = None):
        self.__load_config()
        token = os.getenv('TELEGRAM_API_KEY') if bot_id == self.b_cfg._PROD_BOT_ID \
            else os.getenv('DEVELOPER_TELEGRAM_API_KEY')
        # assert token is not None, 'TELEGRAM_API_KEY is not set in .env file'
        self.app = ApplicationBuilder().token(token).build()

        for command in inspect.getmembers(self, predicate=inspect.ismethod):
            if is_command(command[1]):
                self.app.add_handler(CommandHandler(command[0], command[1]))
                print(f'Added command {command[0]}')

        logger.info('Telegram Bot ready')
        self.instance = self
    
    def __load_config(self):
        from bot_util import bot_config as b_cfg
        from bot_util.functions import config
        self.b_cfg = b_cfg
        self.ConfigFunctions = config

    async def run(self):
        logger.info('Running telegram bot')
        self.app.run_polling()
    
    async def close(self):
        logger.info('Closing telegram bot')
        await self.app.stop()
        await self.app.updater.stop()
        await self.app.shutdown()

    @telegram_command
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.info(f'User {update.effective_user.id} started bot')
        if update.effective_user.id not in self.b_cfg.admin_account_ids:
            return
        if update.effective_chat.id in self.b_cfg.telegram_chat_id:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm already running")
            return
        await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm ready, not sure if mentally though")
        self.ConfigFunctions.add_telegram_chat(update.effective_chat.id)

    @telegram_command
    async def stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.info(f'User {update.effective_user.id} stopped bot')
        if update.effective_user.id not in self.b_cfg.admin_account_ids:
            return
        if update.effective_chat.id not in self.b_cfg.telegram_chat_id:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm not running")
            return
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Bye.")
        self.ConfigFunctions.remove_telegram_chat(update.effective_chat.id)
    
    async def send_automatic_exception(self, exception: Exception, func: str = None, line: int = None, extra: str = None, ctx: Context = None):
        """Sends automatic exception to telegram chat

        Args:
            - exception (Exception): Exception that occurred
            - func (str, optional): Function in which that exception occurred. Defaults to None. Shouldn't be 'None' if no Context present
            - line (int, optional): Line where exception occurred. Defaults to None.
            - extra (str, optional): Extra info about exception. Defaults to None.
            - ctx (Context, optional): Context object if exception occurred in command. Defaults to None.
        """        ''''''
        if self.app.bot is None:
            return
        if ctx is not None:
            error_message = f'*Exception occurred:*\n`{exception}`\n*In command* `{ctx.command}` *which is in* `{ctx.cog.__cog_name__ if ctx.cog else "main"}` *on line* `{"Unknown" if not line else line}`\n{f"*Function:* {func}" if func else ""} \n*Message content:*\n`{ctx.message.content}`\n*Sent by* \n`{ctx.author}`'
        else:
            error_message = f'*Exception occurred:*\n`{exception}`\n*In function* `{func}` *on line* `{"Unknown" if not line else line}`'

        if extra:
            error_message += f'\n*Extra info:*\n`{extra}`'
        
        # replace '-' with '\-' to escape reserved character
        error_message = re.sub("-", "\\-", error_message)
        for chat_id in self.b_cfg.telegram_chat_id:
            await self.app.bot.send_message(chat_id=chat_id, parse_mode="MarkdownV2", text=error_message)
    
    async def send_message_report(self, message: str, *args):
        if self.app.bot is None:
            return
        for chat_id in self.b_cfg.telegram_chat_id:
            await self.app.bot.send_message(chat_id=chat_id, text=message + ("Args: " + str(args) if args else ""))

    @telegram_command
    async def logs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in self.b_cfg.admin_account_ids:
            return
        if update.effective_chat.id not in self.b_cfg.telegram_chat_id:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm not running")
            return
        
        shutil.make_archive("logs", 'zip', 'bot_logs/')
        await context.bot.send_document(chat_id=update.effective_chat.id, document=open("logs.zip", 'rb'), filename="logs.zip")
