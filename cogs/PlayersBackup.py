import os

import discord
import asyncpg
import shutil
from discord.ext import commands, tasks


class PlayersBackup(commands.Cog):
    def __init__(self, bot: commands.Bot):
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
            shutil.make_archive("databases", 'zip', 'db_data/databases/')
            files_to_upload = [discord.File("databases.zip")]
            if os.path.exists("vg_ext"):
                shutil.make_archive("vg_ext_databases", 'zip', 'vg_ext/database/')
                files_to_upload.append(discord.File("vg_ext_databases.zip"))
            await channel_to_upload_to.send(files=files_to_upload)
            print("Database file upload success")
        except Exception as e:
            print(f"Upload .zip package failed: {e}")
    
    @upload_json_to_discord.before_loop
    async def before_uploading(self):
        print('waiting...')
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(PlayersBackup(bot))
