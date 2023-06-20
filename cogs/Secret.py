import asyncio
import base64
import json
import random
from io import BytesIO
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import discord
from discord.ext import commands

from datetime import datetime as dt

import GameFunctions as GF
from util.bot_functions import *
from get_sheets import SheetsData
from db_data import database_main
from db_data.mysql_main import DatabaseFunctions as DF
from db_data.mysql_main import JsonOperating as JO
from db_data.mysql_main import LichessTables as LT


class Secret(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        print("Secret cog loaded successfully!")

    @commands.command(pass_context=True)
    async def dan(self, ctx: commands.Context):
        emoji = discord.utils.get(self.bot.emojis, name="dan")
        await ctx.send(str(emoji))
        await ctx.message.delete()

    @commands.command()
    async def test(self, ctx: commands.Context):
        pass


async def setup(bot):
    await bot.add_cog(Secret(bot))
