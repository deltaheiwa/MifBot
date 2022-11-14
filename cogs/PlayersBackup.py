import discord
import random
import asyncio
import json
import asyncpg
from discord.ext import commands, tasks
from functions import *

class PlayersBackup(commands.Cog):
    def __init__(self, bot):
        self.index = 0
        self.bot = bot
        self.data = []
        self.upload_json_to_discord.add_exception_type(asyncpg.PostgresConnectionError)
    
    async def cog_load(self):
        print("PlayersBackup cog loaded successfully!")
        self.upload_json_to_discord.start()

    async def cog_unload(self):
        self.upload_json_to_discord.cancel()
    
        
    @tasks.loop(hours=24)
    async def upload_json_to_discord(self):
        channel_to_upload_to = self.bot.get_channel(928035142482681886)
        try:
            await channel_to_upload_to.send(file=discord.File("local.db"))
            print("Database file upload success")
        except Exception as e:
            print(f"Upload JSON failed: {e}")
    
    @upload_json_to_discord.before_loop
    async def before_uploading(self):
        print('waiting...')
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(PlayersBackup(bot))
