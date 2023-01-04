from functools import cache
import discord
import logging
import random
import asyncio
import json
import requests
from discord.ext import commands
from datetime import datetime as datetimefix
import datetime as mainDatetime
from functions import *
import creds
import config
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.dates as mdates
import matplotlib as mpl
import jsonget as jg
import re
import pytz
import surrogates
import colorama as cl
import coloredlogs


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s:%(levelname)s --- %(message)s')
console_formatter = CustomFormatter()
stream_handler = logging.StreamHandler()
coloredlogs.install(level='DEBUG', logger=logger)
file_handler_debug = logging.FileHandler(config.wolvesville_log_debug)
file_handler_debug.setFormatter(formatter)
stream_handler.setFormatter(console_formatter)
logger.addHandler(file_handler_debug)

# class WovShop(discord.ui.View):
#     def __init__(self, *, timeout = 1800):
#         super().__init__(timeout=timeout)


class WovClan(discord.ui.View):
    def __init__(self, clan_json_data, embed_func, *, timeout=3600): # timeout = 1 hour
        super().__init__(timeout=timeout)
        self.json_data = clan_json_data
        self.embed_func = embed_func

    
    @discord.ui.button(label="", emoji=config.CustomEmojis.rerequest, style=discord.ButtonStyle.gray)
    async def repeat_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        time_diff = datetimefix.utcnow() - datetimefix.strptime(self.json_data['caching_data']['time_cached'], "%Y-%m-%dT%H:%M:%S.%fZ")
        time_diff = time_diff.total_seconds()
        button.disabled = True
        if time_diff < 3600:
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(content=f"Can't update information so frequently. Try again in **{pretty_time_delta(3600-time_diff)}**")
        else:
            self.json_data = await wov_api_call(req_info="clan", by_id=True, name_id=self.json_data['id'])
            member_list = await wov_api_call(name_id=self.json_data['id'], req_info="clan_members", by_id=True)
            description = self.json_data['description']
            json_caching("clan", self.json_data)
            json_caching("clan_members", member_list, self.json_data['id'])
            new_embed, file_thumbnail = self.embed_func(dict_clan=self.json_data, description=description)
            clan_leader_str = "**Leader:** "
            co_leader_str = "\n**---Co-leaders---**"
            co_leader_str2 = ""
            members_str = "\n**...Members...**"
            members_str2 = ""
            for clan_member in member_list:
                if clan_member['playerId'] == self.json_data['leaderId']:
                    clan_leader_str += f"{clan_member['level']} | **{clan_member['username']}** - *{clan_member['xp']:,}xp*"
                    member_list.remove(clan_member)
                if clan_member['isCoLeader'] is True:
                    # print(len(clan_leader_str + co_leader_str+f"\n{clan_member['level']} | **{clan_member['username']}** -*{clan_member['xp']:,}xp*"))
                    if len(clan_leader_str + co_leader_str+f"\n{clan_member['level']} | **{clan_member['username']}** - *{clan_member['xp']:,}xp*") > 1024:
                        co_leader_str2 += f"\n{clan_member['level']} | **{clan_member['username']}** - *{clan_member['xp']:,}xp*"
                    else:
                        co_leader_str += f"\n{clan_member['level']} | **{clan_member['username']}** - *{clan_member['xp']:,}xp*"
                    member_list.remove(clan_member)
            for clan_member in member_list:
                # print(len(clan_leader_str + co_leader_str+co_leader_str2+members_str+f"\n{clan_member['level']} | **{clan_member['username']}** - *{clan_member['xp']:,}xp*"))
                if co_leader_str2 != "" or len(clan_leader_str + co_leader_str+co_leader_str2+members_str+f"\n{clan_member['level']} | **{clan_member['username']}** - *{clan_member['xp']:,}xp*") > 1024:
                    members_str2 += f"\n{clan_member['level']} | **{clan_member['username']}** - *{clan_member['xp']:,}xp*"
                else: members_str += f"\n{clan_member['level']} | **{clan_member['username']}** - *{clan_member['xp']:,}xp*"
            if co_leader_str == "\n**---Co-leaders---**": co_leader_str = ""
            if members_str == "\n**...Members...**": members_str = ""
            if co_leader_str2 != "":
                new_embed.add_field(name="Members", value=clan_leader_str+co_leader_str, inline=False)
                new_embed.add_field(name=f"{config.CustomEmojis.empty}", value = co_leader_str2+members_str, inline=False)
            elif members_str2 != "":
                new_embed.add_field(name="Members", value=clan_leader_str+co_leader_str+members_str, inline=False)
                new_embed.add_field(name=f"{config.CustomEmojis.empty}", value = members_str2, inline=False)
            else: new_embed.add_field(name="Members", value=clan_leader_str+co_leader_str+members_str, inline=False)
            await interaction.response.edit_message(attachments=[file_thumbnail], embed=new_embed, view=self)
    
    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        
        await self.message.edit(view=self)

class WovPlayer(discord.ui.View):
    def __init__(self, embed_func, json_data, days, *, timeout=3600): # timeout = 1 hour
        super().__init__(timeout=timeout)
        self.embed_func = embed_func
        self.json_data = json_data
        self.days = days
    
    
    @discord.ui.button(label="SP graph", style=discord.ButtonStyle.blurple)
    async def sp_graph(self, interaction: discord.Interaction, button: discord.ui.Button):
        with open(Path('Wov Cache', 'old_player_cache.json'), "r") as f:
            old_player_cache = json.load(f)
        if self.json_data['id'] not in old_player_cache or len(old_player_cache[self.json_data['id']]) < 3:
            button.disabled = True
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(content="Not enough data for graph")
        else:
            fixed_tp = []
            sp_list = []
            graph_sp = []
            for time in old_player_cache[self.json_data['id']]:
                time_diff = datetimefix.utcnow() - datetimefix.strptime(time, "%Y-%m-%dT%H:%M:%S.%fZ")
                if time_diff > datetime.timedelta(days=self.days):
                    continue
                current_sp_data = old_player_cache[self.json_data['id']][time]['rankedSeasonSkill']
                fixed_tp.append(time)
                if current_sp_data < 0:
                    sp_list.append(1500)
                else: sp_list.append(current_sp_data)
                if fixed_tp.index(time) != 0:
                    times_rewinded = 1
                    previous_sp_data = graph_sp[fixed_tp.index(time)-times_rewinded]
                    while previous_sp_data == '':
                        times_rewinded += 1
                        previous_sp_data = graph_sp[fixed_tp.index(time)-times_rewinded]
                    if abs(int(current_sp_data)-int(previous_sp_data)) < 10:
                        graph_sp.append("")
                    else:
                        if current_sp_data < 0:
                            graph_sp.append(1500)
                        else: graph_sp.append(current_sp_data)
                else:
                    if current_sp_data < 0:
                        graph_sp.append(1500)
                    else: graph_sp.append(current_sp_data)
            fixed_tp.append(self.json_data['caching_data']['time_cached'])
            dates = mdates.num2date(mdates.datestr2num(fixed_tp))
            if self.json_data['rankedSeasonSkill'] < 0:
                sp_list.append(1500)
            else: sp_list.append(self.json_data['rankedSeasonSkill'])
            times_rewinded = 1
            previous_sp_data = graph_sp[fixed_tp.index(time)-times_rewinded]
            while previous_sp_data == '':
                times_rewinded += 1
                previous_sp_data = graph_sp[fixed_tp.index(time)-times_rewinded]
            if abs(int(self.json_data['rankedSeasonSkill'])-int(previous_sp_data)) < 10:
                graph_sp.append("")
            else:
                if self.json_data['rankedSeasonSkill'] < 0:
                    graph_sp.append(1500)
                else: graph_sp.append(self.json_data['rankedSeasonSkill'])
            milky_color = '#ededed'
            mpl.rc('text', color=milky_color)
            mpl.rc('axes', labelcolor=milky_color)
            mpl.rc('xtick', color=milky_color)
            mpl.rc('ytick', color=milky_color)
            fig, ax = plt.subplots()
            ax.plot(dates, sp_list, color="#cc2310")
            ax.set(title =f"{self.json_data['username']}' skill points over time",
                xlabel = 'Date',
                ylabel = 'Skill points')
            sp_size = 8
            amount_of_sp_obj = len(sp_list)
            while amount_of_sp_obj > 15 and sp_size != 4:
                sp_size -= 2
                amount_of_sp_obj -= 15
            for index in range(len(dates)):
                ax.text(dates[index], sp_list[index], graph_sp[index], size=sp_size)
            for reset_date in config.wov_season_resets:
                if datetimefix.strptime(fixed_tp[0], "%Y-%m-%dT%H:%M:%S.%fZ") < reset_date and datetimefix.strptime(fixed_tp[-1], "%Y-%m-%dT%H:%M:%S.%fZ") > reset_date:
                    plt.axvline(x=reset_date,ymin=0.05, ymax=0.95, color='#DCBB1E', label='Line - season reset')
                    plt.legend(loc='upper right', labelcolor=milky_color, fontsize=7, frameon=False, fancybox=False, shadow=False, framealpha=0.0)
            ax.set_facecolor('#1f2736')
            fig.set_facecolor('#080b0f')
            fig.autofmt_xdate()
            plt.setp(ax.get_xticklabels(), rotation=30, horizontalalignment='right')
            with BytesIO() as im_bin:
                plt.savefig(im_bin, format="png")
                im_bin.seek(0)
                attachment = discord.File(fp=im_bin, filename="plot.png")
            plt.close()
            button.disabled = True
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(file=attachment)

    
    @discord.ui.button(label="", emoji=config.CustomEmojis.rerequest, style=discord.ButtonStyle.gray)
    async def repeat_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        time_diff = datetimefix.utcnow() - datetimefix.strptime(self.json_data['caching_data']['time_cached'], "%Y-%m-%dT%H:%M:%S.%fZ")
        time_diff = time_diff.total_seconds()
        if time_diff < 1800:
            button.disabled = True
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(content=f"Can't update information so frequently. Try again in **{pretty_time_delta(3600-time_diff)}**")
        else:
            history_caching(self.json_data)
            self.json_data = await wov_api_call(by_id=True, name_id=self.json_data['id'])
            json_caching("user", self.json_data)
            embedP = await self.embed_func(self.json_data)
            await interaction.response.edit_message(attachments=[embedP[1]], embed=embedP[0], view=self)
    
    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        
        await self.message.edit(view=self)

class AvatarSelect(discord.ui.Select):
    def __init__(self, images: list, options, embed_names: list):
        super().__init__(options=options, placeholder="You can select an avatar...",min_values=1,max_values=1)
        self.embeds = {"All_avatars": None}
        self.attachments = images
        self.embed_names = embed_names
    
    async def callback(self, interaction: discord.Interaction):
        if self.embeds['All_avatars'] is None:
            for item in self.embed_names:
                self.embeds[item] = {"embed":discord.Embed(title=re.sub("_", " ", item), description="", color=config.CustomColors.cyan), "attachment": self.attachments[self.embed_names.index(item)]}
        with BytesIO() as im_bin:
            key = re.sub("\s", "_", self.values[0])
            self.embeds[key]['attachment'].save(im_bin, "PNG")
            im_bin.seek(0)
            attachment = discord.File(fp=im_bin, filename=f"{key}.png")
            self.embeds[key]["embed"].set_image(url=f"attachment://{key}.png")
        await interaction.response.edit_message(embed=self.embeds[key]["embed"], attachments=[attachment])

class WovPlayerAvatars(discord.ui.View):
    def __init__(self, images: list, select_options, embed_names:list, *, timeout=3600): # timeout = 1 hour
        super().__init__(timeout=timeout)
        self.add_item(AvatarSelect(images=images, options=select_options, embed_names=embed_names))
    
    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        
        await self.message.edit(view=self)

class Wolvesville(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_url = "https://api.wolvesville.com/"
    
    async def cog_load(self):
        print("Wolvesville cog loaded successfully!")
    
    # @commands.command(aliases=['avatars'])
    # async def avataritems(self, ctx):
    #     headers = {"Authorization": f"Bot {creds.WOV_API_TOKEN}"}
    #     response = requests.get(url = self.api_url+"/clans/1d8ea299-b4df-4255-bd97-f85dfc5e73c7/members", headers=headers)
    #     response = requests.post(url = self.api_url+"/items/redeemApiHat", data=[], headers=headers)
    #     print(response, response.json())
    #     // await ctx.send(response.json())
    #     jsonString = json.dumps(response.json())
    #     jsonFile = open("clan_members.json", "w")
    #     jsonFile.write(jsonString)
    #     jsonFile.close()
    #     print("l")
    

    @commands.command(aliases=['wov-clan', 'w-clan', 'wov-c', 'wovc', 'w-c'])
    async def wovclan(self, ctx, *, clan_name: str = None):
        if clan_name is None:
            embedErr = discord.Embed(title="Error", description="No clan name specified. Correct syntax: `.wov-clan {clan name}`", color=config.CustomColors.red)
            await ctx.send(embed=embedErr)
            return
        clan_name = surrogates.encode(clan_name)
        logger_clan_name = clan_name.encode("ascii", "ignore")
        logger_clan_name = logger_clan_name.decode()
        main_message = None
        if local_checks(ctx.message.author):
            add_command_stats(ctx.message.author)
        if cache_check("clan", "name", clan_name) is False:
            logger.info(f"Couldn't find \"{logger_clan_name}\" in cache. Making an API call.")
            clan_name_search = re.sub("\s", "%20", clan_name)
            clan_dict = await wov_api_call(clan_name_search, req_info="clan")
            if len(clan_dict) == 0 or clan_dict is None:
                embedErr = discord.Embed(title="Error", description="Couldn't find any clan with that name.", color=config.CustomColors.red)
                await ctx.send(embed=embedErr)
                logger.info(f"Couldn't find \"{logger_clan_name}\" using API")
                return
            # // cl_names = ""
            # // for cl in clan_dict: cl_names += f"{surrogates.encode(cl['name'])}, "
            # // cl_names = cl_names.encode("ascii", "ignore")
            # // cl_names = cl_names.decode()
            logger.debug(f"(Length - {len(clan_dict)}.)")
            if len(clan_dict) > 1:
                choose_embed = discord.Embed(title="Clans found", description="use `^.w-c {clan number}` in order to get information on the clan", color=config.CustomColors.cyan)
                for clan in clan_dict:
                    clan_desc = clan['description']
                    clan_desc = surrogates.encode(clan_desc)
                    clan_desc = surrogates.decode(clan_desc)
                    clan_desc_arr = clan_desc.split('\n')
                    clan_desc_oneline = ""
                    for i in range(len(clan_desc)):
                        if clan_desc_oneline != "":
                            break
                        clan_desc_oneline = clan_desc_arr[i]
                    if clan_desc_oneline == "":
                        clan_desc_oneline = "*No description*"
                    # // logger.debug(clan_desc_oneline)
                    # // clan_desc.encode(encoding="utf8").decode()
                    if 'tag' in clan:
                        c_tag = re.sub('u([0-9a-f]{4})',lambda m: chr(int(m.group(1),16)),clan['tag'])
                        c_tag = surrogates.decode(c_tag)
                    else: c_tag = ""
                    clan_name = re.sub('u([0-9a-f]{4})',lambda m: chr(int(m.group(1),16)),clan['name'])
                    clan_name = surrogates.decode(clan_name)
                    choose_embed.add_field(name=f"**{clan_dict.index(clan)+1}** `{c_tag}` | **{clan_name}** :flag_{clan['language'].lower()}:", value=clan_desc_oneline)
                main_message = await ctx.send(embed=choose_embed)
                try:
                    chose = await self.bot.wait_for(
                        "message", timeout=300, check=lambda m: m.author.id == ctx.message.author.id and m.channel.id == ctx.channel.id and m.content.startswith('^.w-c')
                    )
                except asyncio.TimeoutError:
                    embed_err = discord.Embed(title="Timeout error", description="No clan number received", color = config.colors['red'])
                    await ctx.send(embed=embed_err)
                    logger.info("\"Found Clans\" asyncio.TimeoutError:Exiting command function")
                    return
                content = chose.content.split(' ')
                try:
                    cl_number = int(content[1])
                except Exception as e:
                    embed_err = discord.Embed(title="Identification error", description="No clan number identificated.", color = config.CustomColors.red)
                    await ctx.send(embed=embed_err)
                    logger.error(f"\"Found Clans\" Identification_error:{e}")
                    return
                if cl_number > len(clan_dict):
                    embed_err = discord.Embed(title="Identification error", description="Clan number not identificated. ||*(OutOfBounds error)*||", color = config.CustomColors.red)
                    await ctx.send(embed=embed_err)
                    logger.error(f"\"Found Clans\" Identification_error:OutOfBounds")
                    return
                await chose.delete(delay=1)
                dict_clan = clan_dict[cl_number-1]
                logger_clan_name = dict_clan['name'].encode("ascii", "ignore")
                logger_clan_name = logger_clan_name.decode()
                logger.info(f"They chose {logger_clan_name}")
                description = dict_clan['description']
                json_caching("clan",dict_clan)
                time_cached = datetimefix.utcnow()
                iso = time_cached.isoformat() + "Z"
                dict_clan['caching_data'] = {}
                dict_clan['caching_data']['time_cached'] = str(iso)
            else:
                dict_clan = clan_dict[0]
                description = dict_clan['description']
                json_caching("clan", dict_clan)
                time_cached = datetimefix.utcnow()
                iso = time_cached.isoformat() + "Z"
                dict_clan['caching_data'] = {}
                dict_clan['caching_data']['time_cached'] = str(iso)
        else:
            logger.info(f"Found \"{logger_clan_name}\" in cache. Retrieving.")
            clan_dict = get_json("un:"+clan_name, table="wov_clans", raw=False)
            dict_clan, description = clan_dict[0], clan_dict[1]
        
        print(dict_clan)
        def embed_creation(dict_clan, description):
            clan_name = re.sub('u([0-9a-f]{4})',lambda m: chr(int(m.group(1),16)),dict_clan['name'])
            clan_name = surrogates.decode(clan_name)
            c_tag = re.sub('u([0-9a-f]{4})',lambda m: chr(int(m.group(1),16)),dict_clan['tag'])
            c_tag = surrogates.decode(c_tag)
            clan_desc = surrogates.encode(description)
            clan_desc = surrogates.decode(clan_desc)
            try: timestamp = timestamp = datetimefix.strptime(dict_clan['caching_data']['time_cached'], "%Y-%m-%dT%H:%M:%S.%fZ") 
            except: timestamp = datetimefix.utcnow()
            timestamp = timestamp.replace(tzinfo=pytz.UTC)
            embed_clan = discord.Embed(title=f"`{c_tag}` | {clan_name}", description=f"General clan information about \"{clan_name}\" on Wolvesville", color=discord.Color.from_str(dict_clan['iconColor']), timestamp=timestamp)
            file_thumbnail = discord.File("Images/wov_logo.png", filename="wov_logo.png")
            embed_clan.set_thumbnail(url="attachment://wov_logo.png")
            embed_clan.add_field(name="Description", value=clan_desc, inline=False)
            embed_clan.add_field(name="XP", value=f"**{dict_clan['xp']:,}**")
            match dict_clan['joinType']:
                case "PUBLIC":
                    join_type = "Public"
                case "JOIN_BY_REQUEST":
                    join_type = "Invite only"
                case "PRIVATE":
                    join_type = "Closed"
            embed_clan.add_field(name="Language", value=f":flag_{dict_clan['language'].lower()}:")
            embed_clan.add_field(name="Member count", value=f"**{dict_clan['memberCount']}/50**")
            try:
                creationDate = timestamp_calculate(dict_clan['creationTime'], "Creation Date") + " UTC"
            except KeyError:
                creationDate = "August 3, 2018 or before"
            embed_clan.add_field(name="Date created", value=f"{creationDate}")
            embed_clan.add_field(name="Join type", value=join_type)
            embed_clan.add_field(name="Minimum level to join", value=dict_clan['minLevel'])
            embed_clan.add_field(name="Quests", value=f"**{dict_clan['questHistoryCount']}**")
            
            return (embed_clan, file_thumbnail)
        
        first_embed, file_thumbnail = embed_creation(dict_clan, description)
        first_embed.add_field(name="Members", value=f"*loading...* {config.CustomEmojis.loading}", inline=False)
        
        if main_message is not None: await main_message.edit(attachments=[file_thumbnail], embed=first_embed)
        else: main_message = await ctx.send(file=file_thumbnail, embed=first_embed)
        
        if cache_check(type_of_search="id", what_to_search="clan_members", name=dict_clan['id']) is True:
            member_list = get_json(member="me:"+f"{dict_clan['id']}", raw=False, table="wov_clans")
        else: 
            await asyncio.sleep(2)
            member_list = await wov_api_call(name_id=dict_clan['id'], req_info="clan_members", by_id = True)
            json_caching(cache_type="clan_members", json_data=member_list, extra_data=dict_clan['id'])
        first_embed.remove_field(-1)
        clan_leader_str = "**Leader:** "
        co_leader_str = "\n**---Co-leaders---**"
        co_leader_str2 = ""
        members_str = "\n**...Members...**"
        members_str2 = ""
        # ! Курва йобана, не намагайтеся зрозуміти цей код
        for clan_member in member_list:
            if clan_member['playerId'] == dict_clan['leaderId']:
                clan_leader_str += f"{clan_member['level']} | **{clan_member['username']}** - *{clan_member['xp']:,}xp*"
                member_list.remove(clan_member)
            if clan_member['isCoLeader'] is True:
                # print(len(clan_leader_str + co_leader_str+f"\n{clan_member['level']} | **{clan_member['username']}** -*{clan_member['xp']:,}xp*"))
                if len(clan_leader_str + co_leader_str+f"\n{clan_member['level']} | **{clan_member['username']}** - *{clan_member['xp']:,}xp*") > 1024:
                    co_leader_str2 += f"\n{clan_member['level']} | **{clan_member['username']}** - *{clan_member['xp']:,}xp*"
                else:
                    co_leader_str += f"\n{clan_member['level']} | **{clan_member['username']}** - *{clan_member['xp']:,}xp*"
                member_list.remove(clan_member)
        for clan_member in member_list:
            # print(len(clan_leader_str + co_leader_str+co_leader_str2+members_str+f"\n{clan_member['level']} | **{clan_member['username']}** - *{clan_member['xp']:,}xp*"))
            if co_leader_str2 != "" or len(clan_leader_str + co_leader_str+co_leader_str2+members_str+f"\n{clan_member['level']} | **{clan_member['username']}** - *{clan_member['xp']:,}xp*") > 1024:
                members_str2 += f"\n{clan_member['level']} | **{clan_member['username']}** - *{clan_member['xp']:,}xp*"
            else: members_str += f"\n{clan_member['level']} | **{clan_member['username']}** - *{clan_member['xp']:,}xp*"
        if co_leader_str == "\n**---Co-leaders---**": co_leader_str = ""
        if members_str == "\n**...Members...**": members_str = ""
        if co_leader_str2 != "":
            first_embed.add_field(name="Members", value=clan_leader_str+co_leader_str, inline=False)
            first_embed.add_field(name=f"{config.CustomEmojis.empty}", value = co_leader_str2+members_str, inline=False)
        elif members_str2 != "":
            first_embed.add_field(name="Members", value=clan_leader_str+co_leader_str+members_str, inline=False)
            first_embed.add_field(name=f"{config.CustomEmojis.empty}", value = members_str2, inline=False)
        else: first_embed.add_field(name="Members", value=clan_leader_str+co_leader_str+members_str, inline=False)
        view = WovClan(clan_json_data=dict_clan, embed_func=embed_creation)
        view.message = await main_message.edit(embed=first_embed, view=view)
    
    @commands.command(aliases=['wov-player', 'w-player', 'wov-p', 'wovp', 'w-p'])
    async def wovplayer(self, ctx, username: str = None, arg: str = None):
        searching = True
        if username is None:
            embedErr = discord.Embed(title="Error", description="No username found. Correct syntax: `.wov-player {username}`", color=config.CustomColors.red)
            await ctx.send(embed=embedErr)
            searching = False
        elif len(username) < 3:
            embedErr = discord.Embed(title="Error", description="Username is too short. At least 3 characters required", color=config.CustomColors.red)
            await ctx.send(embed=embedErr)
            searching = False
        if searching == True:
            cache_cck = cache_check("user", "username", username)
            if cache_cck is False:
                print("Couldn\'t find player in cache. Making an API call...")
                player_dict = await wov_api_call(username)
                if player_dict is None:
                    embedErr = discord.Embed(title="Error", description="Couldn't find any user with that username. *Maybe they changed it?*", color=config.CustomColors.red)
                    await ctx.send(embed=embedErr)
                    return None
                bio_first = player_dict['personalMessage']
                json_caching("user", player_dict)
            else:
                player_dict = get_json("un:"+username, table="wov_players", raw=False)
                player_dict, bio_first = player_dict[0], player_dict[1]
            if (datetimefix.utcnow() - datetimefix.strptime(player_dict['caching_data']['time_cached'], "%Y-%m-%dT%H:%M:%S.%fZ")).days > 30: 
                history_caching(player_dict)
                player_dict = await wov_api_call(player_dict['id'], by_id=True)
                bio_first = player_dict['personalMessage']
                json_caching("user", player_dict)
            print(player_dict)
            if local_checks(ctx.message.author):
                add_command_stats(ctx.message.author)
            if arg in ["avatars", "avatar"]:
                select_options, embed_names, attachments, avatar_functs, av_urls = [], [], [], [], []
                avatar_embed = discord.Embed(title="All avatars", description="", color=config.CustomColors.cyan)
                for avatar in player_dict['avatars']:
                    if avatar['url'] in av_urls: 
                        av_urls.append(avatar['url']) 
                        continue
                    avatar_functs.append(avatar_rendering(image_URL=avatar['url'], rank=False))
                    av_urls.append(avatar['url'])
                time_before_rendering = datetimefix.now()
                attachments = await asyncio.gather(*avatar_functs)
                print(datetimefix.now()-time_before_rendering)
                all_avatars_file = await all_avatars_rendering(attachments,av_urls)
                attachments.insert(0, all_avatars_file)
                with BytesIO() as im_bin:
                    all_avatars_file.save(im_bin, "PNG")
                    im_bin.seek(0)
                    attachment = discord.File(fp=im_bin, filename="all_avatar.png")
                    avatar_embed.set_image(url="attachment://all_avatar.png")
                # // del av_bg, avatar, lvlfont, one_ts_lvl_font, draw, main_avatars, avatar_dict, image_font
                # // gc.collect()
                for avatar in attachments:
                    if attachments.index(avatar) == 0:
                        select_options.append(discord.SelectOption(label="All avatars"))
                        embed_names.append("All_avatars")
                    else:
                        select_options.append(discord.SelectOption(label=f"Avatar {attachments.index(avatar)}"))
                        embed_names.append(f"Avatar_{attachments.index(avatar)}")
                view = WovPlayerAvatars(images=attachments, select_options=select_options, embed_names=embed_names)
                view.message = await ctx.send(embed=avatar_embed, file=attachment, view=view)
            else:
                async def embed_creation(player_data):
                    statuses = {'PLAY': ["<:letsplay:1025841396751544441>", "Let's play"],
                                'DEFAULT': [":green_circle:", "Appears online"],
                                'DND': [":red_circle:", "Do not disturb"],
                                'OFFLINE': [":black_circle:", "Invisible"]}
                    try:
                        thumbnail = await avatar_rendering(player_data['equippedAvatar']['url'], player_data['level'])
                    except KeyError:
                        history_caching(player_data)
                        player_data = await wov_api_call(username)
                        json_caching("user", player_data)
                        thumbnail = await avatar_rendering(player_data['equippedAvatar']['url'], player_data['level'])
                    try: 
                        timestamp = datetimefix.strptime(player_data['caching_data']['time_cached'], "%Y-%m-%dT%H:%M:%S.%fZ") 
                    except: timestamp = datetimefix.utcnow()
                    timestamp = timestamp.replace(tzinfo=pytz.UTC)
                    embed_color = player_data['profileIconColor']
                    embedPlayer = discord.Embed(title=f"{player_data['username']}", description=f"Information I retrieved about {player_data['username']} on Wolvesville", color=discord.Color.from_str(embed_color),timestamp=timestamp)
                    with BytesIO() as im_bin:
                        thumbnail.save(im_bin, "PNG")
                        im_bin.seek(0)
                        attachment = discord.File(fp=im_bin, filename="image.png")
                        embedPlayer.set_thumbnail(url="attachment://image.png")
                    try:
                        bio = player_data['personal_message']
                    except KeyError:
                        if bio_first != '':
                            bio = bio_first
                        else: bio = '*No personal message found*'
                    embedPlayer.add_field(name="Personal Message", value=bio, inline=False)
                    embedPlayer.add_field(name="Level", value=f"**{player_data['level']}**")
                    embedPlayer.add_field(name="Status", value=f"{statuses[player_data['status']][0]} **{statuses[player_data['status']][1]}**")
                    LO_time_diff = datetimefix.utcnow() - datetimefix.strptime(player_data['lastOnline'], "%Y-%m-%dT%H:%M:%S.%fZ")
                    LO_time_diff = LO_time_diff.total_seconds()
                    if LO_time_diff < 420:
                        lastOnlineFlag = "Player is online"
                    else: lastOnlineFlag = pretty_date(player_data['lastOnline'])
                    embedPlayer.add_field(name="Last online", value=f"{lastOnlineFlag}")
                    try:
                        creationDate = timestamp_calculate(player_data['creationTime'], "Creation Date") + " UTC"
                    except KeyError:
                        creationDate = "August 3, 2018 or before"
                    embedPlayer.add_field(name="Date created", value=f"{creationDate}")
                    embedPlayer.add_field(name="Roses", value=f"Roses received: **{player_data['receivedRosesCount']}** {config.CustomEmojis.single_rose}\nRoses sent: **{player_data['sentRosesCount']}** {config.CustomEmojis.single_rose} \nDiff: **{player_data['receivedRosesCount'] - player_data['sentRosesCount']}**")
                    embedPlayer.add_field(name=f"{config.CustomEmojis.empty}", value=f"{config.CustomEmojis.empty}", inline=False)
                    ranked_keys = ["rankedSeasonSkill", "rankedSeasonMaxSkill", "rankedSeasonBestRank"]
                    for item in ranked_keys:
                        match item:
                            case "rankedSeasonSkill":
                                if player_data[item] < 0:
                                    current_sp = "*Didn't participate in current season*"
                                else: current_sp = f"**{player_data[item]}**"
                            case "rankedSeasonMaxSkill":
                                if player_data[item] < 0:
                                    max_sp = "*Didn't participate in any season yet*"
                                else: max_sp = f"**{player_data[item]}**"
                            case "rankedSeasonBestRank":
                                if player_data[item] < 0:
                                    best_rank = "*Didn't participate in any season yet*"
                                else: best_rank = f"**{player_data[item]}**"
                    embedPlayer.add_field(name=f"Ranked stats", value=f"Current sp: {current_sp}\nOverall best sp: {max_sp}\nBest season final rank: {best_rank}\nSeasons participated in: **{player_data['rankedSeasonPlayedCount']}**")
                    all_games = player_data['gameStats']['totalWinCount'] + player_data['gameStats']['totalLoseCount'] + player_data['gameStats']['totalTieCount'] + player_data['gameStats']['exitGameBySuicideCount']
                    gen_percentages = {"totalWinCount": 0, "totalLoseCount": 0, "totalTieCount": 0, "exitGameBySuicideCount": 0}
                    for perc in gen_percentages:
                        gen_percentages[perc] = round(percentage_calc(all_games, player_data['gameStats'][perc]), 2)
                    total_playtime = datetime.timedelta(minutes=player_data['gameStats']['totalPlayTimeInMinutes'])
                    total_playtime = total_playtime.total_seconds()/3600
                    general_stats = f"Total games played: **{player_data['gameStats']['totalWinCount']+player_data['gameStats']['totalLoseCount']+player_data['gameStats']['totalTieCount']}**" \
                                    f"\nTotal wins: **{player_data['gameStats']['totalWinCount']} ({gen_percentages['totalWinCount']}%)**" \
                                    f"\nTotal defeats: **{player_data['gameStats']['totalLoseCount']} ({gen_percentages['totalLoseCount']}%)**" \
                                    f"\nTotal ties: **{player_data['gameStats']['totalTieCount']} ({gen_percentages['totalTieCount']}%)**" \
                                    f"\nFlee count: **{player_data['gameStats']['exitGameBySuicideCount']} ({gen_percentages['exitGameBySuicideCount']}%)**" \
                                    f"\nTotal playtime: **{round(total_playtime, 2)}h**"
                    role_percentages = {"solo": 0,"voting": 0,"village": 0,"werewolf": 0}
                    for perc in role_percentages:
                        total_role_games = player_data['gameStats'][f'{perc}WinCount'] + player_data['gameStats'][f'{perc}LoseCount']
                        role_percentages[perc] = round(percentage_calc(total_role_games, player_data['gameStats'][f'{perc}WinCount']), 2)
                    role_stats = f"Village: **{player_data['gameStats'][f'villageWinCount']}** Wins/**{player_data['gameStats'][f'villageLoseCount']}** Defeats  **({role_percentages['village']}% wr)**" \
                                f"\nWerewolves: **{player_data['gameStats'][f'werewolfWinCount']}** Wins/**{player_data['gameStats'][f'werewolfLoseCount']}** Defeats  **({role_percentages['werewolf']}% wr)**" \
                                f"\nSolo voting: **{player_data['gameStats'][f'votingWinCount']}** Wins/**{player_data['gameStats'][f'votingLoseCount']}** Defeats  **({role_percentages['voting']}% wr)**" \
                                f"\nSolo killer: **{player_data['gameStats'][f'soloWinCount']}** Wins/**{player_data['gameStats'][f'soloLoseCount']}** Defeats  **({role_percentages['solo']}% wr)**" 
                    embedPlayer.add_field(name=f"General stats", value=general_stats)
                    embedPlayer.add_field(name=f"Team stats", value=role_stats, inline=False)
                    try:
                        clan_id = player_data['clanId']
                    except KeyError:
                        clan_id = None
                    if clan_id is not None:
                        clan_check = cache_check("clan", "id", player_data['clanId'])
                        if clan_check is False:
                            logger.info("Couldn\'t find clan in cache. Making an API call...")
                            clan_dict = await wov_api_call(req_info="clan", name_id = player_data['clanId'], by_id=True)
                            clan_desc = clan_dict['description']
                            json_caching("clan", clan_dict)
                        else:
                            clan_dict = get_json("id:"+player_data['clanId'], raw=False, table="wov_clans")
                            clan_desc, clan_dict = clan_dict[1], clan_dict[0]
                        if (datetimefix.utcnow() - datetimefix.strptime(clan_dict['caching_data']['time_cached'], "%Y-%m-%dT%H:%M:%S.%fZ")).days > 30: 
                            clan_dict = await wov_api_call(player_data['clanId'], req_info="clan", by_id=True)
                            json_caching("clan", clan_dict)
                            clan_desc = clan_dict['description']
                        
                        clan_desc = surrogates.encode(clan_desc)
                        clan_desc = surrogates.decode(clan_desc)
                        clan_desc = clan_desc.split('\n')
                        clan_desc = clan_desc[0]
                        # // clan_desc.encode(encoding="utf8").decode()
                        c_tag = re.sub('u([0-9a-f]{4})',lambda m: chr(int(m.group(1),16)),clan_dict['tag'])
                        c_tag = surrogates.decode(c_tag)
                        clan_name = re.sub('u([0-9a-f]{4})',lambda m: chr(int(m.group(1),16)),clan_dict['name'])
                        clan_name = surrogates.decode(clan_name)
                        clan_info = f"`{c_tag}` | **{clan_name}** :flag_{clan_dict['language'].lower()}: \n{clan_desc}***...***\n*use `.wov-clan {clan_name}` for more information*"
                        print(clan_dict)
                    else:
                        clan_info = "No clan"
                    embedPlayer.add_field(name=f"Clan", value=clan_info,inline=False)
                    embedPlayer.add_field(name=f"Avatars", value=f"*Use `.wov-player {username} avatars` for avatars*")
                    try:
                        if player_data['caching_data']['previous_username'] is not None:
                            embedPlayer.add_field(name="Previous username", value=player_data['caching_data']['previous_username'])
                    except KeyError:
                        pass
                    objects_to_return = [embedPlayer, attachment]
                    return objects_to_return
                embedP = await embed_creation(player_dict)
                try:
                    if arg.isdigit():
                        if int(arg) <= 30:
                            days = int(arg)
                        else: days = 30
                    else: days = 30
                except:
                    days = 30
                view = WovPlayer(embed_func=embed_creation, json_data=player_dict, days=days)
                view.message = await ctx.send(file=embedP[1], embed=embedP[0], view=view)
    
    
    
    # @commands.command(aliases=["w-s", "wov-s", "w-shop", "wov-shop"])
    # async def wovshop(self, ctx):
    #     shop_offers = await wov_api_call(name_id=None, req_info="shop")
    #     print(shop_offers)
        



async def setup(bot):
    await bot.add_cog(Wolvesville(bot))



