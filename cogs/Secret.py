import discord
import random
import json
import asyncio
from discord.ext import commands
from io import BytesIO
import base64
from functions import *
from sqlite_data import database_main
import GameFunctions as GF


class Secret(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        print("Secret cog loaded successfully!")

    @commands.command(pass_context=True)
    async def ussr(self, ctx):
        emoji = discord.utils.get(self.bot.emojis, name="notYours_Ours")
        await ctx.send(str(emoji))
        await ctx.message.delete()

    @commands.command(pass_context=True)
    async def dan(self, ctx):
        id = ctx.author.id

        if id == 835883093662761000:
            emoji = discord.utils.get(self.bot.emojis, name="dan")
            await ctx.send(str(emoji))
            await ctx.message.delete()

    
    @commands.command()
    async def test(self, ctx):
        # json_stats = get_json() 
        # print(json_stats)
        # print(type(json_stats[1]["json_stats->'$[0].botUsage.commandsUsed'"]))
        # add_command_stats(ctx.message.author)
        # await add_stats(ctx.message.author, "ngWins", "easy")
        # await add_stats(ctx.message.author, "bulls", "word", "wins")
        # await add_stats(ctx.message.author, "bulls", "pfb", "classic", "wins")
        # stat = get_json(ctx.message.author)
        # stat_dict = json.loads(stat['bot_stats'])
        # await ctx.send("omg", view=Buttons())
        # print("lala")
        # with open("Wov Cache/profileIcons.json", "r") as f:
        #     icons_dict = json.load(f)
        # icons_name = []
        # for ico in icons_dict:
        #     icons_name.append(ico['name'])
        # print(icons_name)
        # ! Alert! Code below might take a long time to finish
        
        # with open(Path('Wov Cache', 'personal_messages_wov.json'), "r") as js_f:
        #     pm_file = json.load(js_f)
        # for id in pm_file:
        #     temp_personal(id, pm_file[id]['personalMessage'])
        print(0)
        # await ctx.send(GF.get_coins(358))






async def setup(bot):
    await bot.add_cog(Secret(bot))
