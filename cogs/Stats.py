import discord
import random
import asyncio
import json
from discord.ext import commands
from functions import *

class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    async def cog_load(self):
        print("Stats cog loaded successfully!")
    
    @commands.command(aliases=['bstats'])
    async def botstats(self, ctx, member: discord.Member = None):
        if member is None:
            member = ctx.author
        
        checks = local_checks(member)
        if checks == False:
            if member == ctx.author:
                await ctx.send("You don't have an account yet. You can register by using command `register`")
            else:
                await ctx.send(format(member.mention)+" has no account yet")
            return
        database_info = get_user_by_id(member.id, "nickname")
        info = get_json(member, False)
        embed = discord.Embed(
            title=database_info[0]['nickname'],
            description="Bot usage statistics",
            colour=member.colour
        )
        embed.set_thumbnail(url=member.avatar.url)
        embed.add_field(
            name="Total commands used",
            value=info['commandsUsed'],
            inline=False
        )
        embed.add_field(
            name="Number guessing game",
            value=f"**Wins:**" \
                f"\n· easy: {info['ngWins']['easy']}" \
                f"\n· medium: {info['ngWins']['medium']}" \
                f"\n· hard: {info['ngWins']['hard']}" 
        )
        embed.add_field(
            name="Hangman game",
            value=f"**Wins:** {info['hangman']['Wins']} \n**Losses:** {info['hangman']['Losses']}",
            inline=False
        )
        embed.add_field(
            name="Bulls and Cows",
            value=f"**Wins:** {info['bulls']['number']['wins']} \n**Losses:** {info['bulls']['number']['losses']}",)
        embed.add_field(
            name="Bagels",
            value=f"** · Fast:** {info['bulls']['pfb']['fast']['wins']} Wins/{info['bulls']['pfb']['fast']['losses']} Losses/{info['bulls']['pfb']['fast']['abandoned']} Abandoned\n" \
                f"** · Classic:** {info['bulls']['pfb']['classic']['wins']} Wins/{info['bulls']['pfb']['classic']['losses']} Losses/{info['bulls']['pfb']['classic']['abandoned']} Abandoned\n" \
                f"** · Long:** {info['bulls']['pfb']['long']['wins']} Wins/{info['bulls']['pfb']['long']['losses']} Losses/{info['bulls']['pfb']['long']['abandoned']} Abandoned\n" \
                f"** · Hard:** {info['bulls']['pfb']['hard']['wins']} Wins/{info['bulls']['pfb']['hard']['losses']} Losses/{info['bulls']['pfb']['hard']['abandoned']} Abandoned",)
        try:
            embed.add_field(
                name="Rickroll",
                value=f"**Got rickrolled:** {info['rickroll']['themselves']} \n**Rickrolled someone else:** {info['rickroll']['others']}",
                inline=False
            )
        except:
            pass
        
        await ctx.send(embed=embed)
        add_command_stats(ctx.message.author)

async def setup(bot):
    await bot.add_cog(Stats(bot))
