import calendar
from functools import cache
import discord
import logging
import asyncio
from io import BytesIO
import json
from discord.ext import commands
from datetime import datetime as dt, timedelta
from bot_util.bot_functions import (
    AsyncTranslator,
    CustomFormatter,
    APICaller,
    pretty_time_delta,
    pretty_date,
    percentage_calc,
    WovApiCall,
    WolvesvilleFunctions as WovFunc,
)
from db_data.mysql_main import DatabaseFunctions as DF, JsonOperating as JO
import bot_util.bot_config as cfg
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.dates as mdates
import matplotlib as mpl
import re
import pytz
import surrogates
import coloredlogs

WOV_CLAN_SEARCH = {}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s:%(levelname)s --- %(message)s")
console_formatter = CustomFormatter()
stream_handler = logging.StreamHandler()
coloredlogs.install(level="DEBUG", logger=logger)
file_handler_debug = logging.FileHandler(cfg.LogFiles.wolvesville_log)
file_handler_debug.setFormatter(formatter)
stream_handler.setFormatter(console_formatter)
logger.addHandler(file_handler_debug)


class WovClan(discord.ui.View):
    def __init__(
        self, clan_json_data, embed_func, api_caller, *, timeout=3600
    ):  # timeout = 1 hour
        super().__init__(timeout=timeout)
        self.json_data = clan_json_data
        self.embed_func = embed_func
        self.api_caller: APICaller = api_caller

    @discord.ui.button(
        label="", emoji=cfg.CustomEmojis.rerequest, style=discord.ButtonStyle.gray
    )
    async def repeat_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        time_diff = dt.utcnow() - dt.strptime(
            self.json_data["caching_data"]["time_cached"], "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        time_diff = time_diff.total_seconds()
        button.disabled = True
        async with AsyncTranslator(JO.get_lang_code(interaction.user.id)) as at:
            at.install()
            _ = at.gettext
            if time_diff < 3600:
                await interaction.response.edit_message(view=self)
                await interaction.followup.send(
                    content=_(
                        "Can't update information so frequently. Try again in **{timeleft}**"
                    ).format(timeleft=pretty_time_delta(3600 - time_diff))
                )
            else:
                self.json_data = await self.api_caller.add_to_queue(
                    WovApiCall.get_clan_by_id, self.json_data["id"]
                )
                self.json_data = await self.json_data
                member_list = await self.api_caller.add_to_queue(
                    WovApiCall.get_clan_members, self.json_data["id"]
                )
                member_list = await member_list
                description = self.json_data["description"]
                DF.json_caching("clan", self.json_data)
                DF.json_caching("clan_members", member_list, self.json_data["id"])
                new_embed, file_thumbnail = self.embed_func(
                    dict_clan=self.json_data, description=description
                )
                clan_leader_str = _("**Leader:** ")
                co_leader_str = _("\n**---Co-leaders---**")
                co_leader_str2 = ""
                members_str = _("\n**...Members...**")
                members_str2 = ""
                for clan_member in member_list:
                    if clan_member["playerId"] == self.json_data["leaderId"]:
                        clan_leader_str += f"{clan_member['level']} | **{clan_member['username']}** - *{clan_member['xp']:,}xp*"
                        member_list.remove(clan_member)
                    if clan_member["isCoLeader"] is True:
                        # print(len(clan_leader_str + co_leader_str+f"\n{clan_member['level']} | **{clan_member['username']}** -*{clan_member['xp']:,}xp*"))
                        if (
                            len(
                                clan_leader_str
                                + co_leader_str
                                + f"\n{clan_member['level']} | **{clan_member['username']}** - *{clan_member['xp']:,}xp*"
                            )
                            > 1024
                        ):
                            co_leader_str2 += f"\n{clan_member['level']} | **{clan_member['username']}** - *{clan_member['xp']:,}xp*"
                        else:
                            co_leader_str += f"\n{clan_member['level']} | **{clan_member['username']}** - *{clan_member['xp']:,}xp*"
                        member_list.remove(clan_member)
                for clan_member in member_list:
                    # print(len(clan_leader_str + co_leader_str+co_leader_str2+members_str+f"\n{clan_member['level']} | **{clan_member['username']}** - *{clan_member['xp']:,}xp*"))
                    if (
                        co_leader_str2 != ""
                        or len(
                            clan_leader_str
                            + co_leader_str
                            + co_leader_str2
                            + members_str
                            + f"\n{clan_member['level']} | **{clan_member['username']}** - *{clan_member['xp']:,}xp*"
                        )
                        > 1024
                    ):
                        members_str2 += f"\n{clan_member['level']} | **{clan_member['username']}** - *{clan_member['xp']:,}xp*"
                    else:
                        members_str += f"\n{clan_member['level']} | **{clan_member['username']}** - *{clan_member['xp']:,}xp*"
                if co_leader_str == _("\n**---Co-leaders---**"):
                    co_leader_str = ""
                if members_str == _("\n**...Members...**"):
                    members_str = ""
                if co_leader_str2 != "":
                    new_embed.add_field(
                        name=_("Members"),
                        value=clan_leader_str + co_leader_str,
                        inline=False,
                    )
                    new_embed.add_field(
                        name=f"{cfg.CustomEmojis.empty}",
                        value=co_leader_str2 + members_str,
                        inline=False,
                    )
                elif members_str2 != "":
                    new_embed.add_field(
                        name=_("Members"),
                        value=clan_leader_str + co_leader_str + members_str,
                        inline=False,
                    )
                    new_embed.add_field(
                        name=f"{cfg.CustomEmojis.empty}",
                        value=members_str2,
                        inline=False,
                    )
                else:
                    new_embed.add_field(
                        name=_("Members"),
                        value=clan_leader_str + co_leader_str + members_str,
                        inline=False,
                    )
                await interaction.response.edit_message(
                    attachments=[file_thumbnail], embed=new_embed, view=self
                )

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True

        await self.message.edit(view=self)


class WovPlayer(discord.ui.View):
    def __init__(
        self, embed_func, json_data, days, gettext, api_caller, *, timeout=3600
    ):  # timeout = 1 hour
        super().__init__(timeout=timeout)
        self.embed_func = embed_func
        self.json_data = json_data
        self.days = days
        self._ = gettext
        self.api_caller: APICaller = api_caller

    @discord.ui.button(label="SP graph", style=discord.ButtonStyle.blurple)
    async def sp_graph(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        with open(Path("WovCache", "old_player_cache.json"), "r") as f:
            old_player_cache = json.load(f)
        if (
            self.json_data["id"] not in old_player_cache
            or len(old_player_cache[self.json_data["id"]]) < 3
        ):
            button.disabled = True
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(content=self._("Not enough data for graph"))
        else:
            fixed_tp = []
            sp_list = []
            graph_sp = []
            for time in old_player_cache[self.json_data["id"]]:
                time_diff = dt.utcnow() - dt.strptime(time, "%Y-%m-%dT%H:%M:%S.%fZ")
                if time_diff > timedelta(days=self.days):
                    continue
                current_sp_data = old_player_cache[self.json_data["id"]][time]
                fixed_tp.append(time)
                if current_sp_data < 0:
                    sp_list.append(1500)
                else:
                    sp_list.append(current_sp_data)
                if fixed_tp.index(time) != 0:
                    times_rewinded = 1
                    previous_sp_data = graph_sp[fixed_tp.index(time) - times_rewinded]
                    while previous_sp_data == "":
                        times_rewinded += 1
                        previous_sp_data = graph_sp[
                            fixed_tp.index(time) - times_rewinded
                        ]
                    if abs(int(current_sp_data) - int(previous_sp_data)) < 10:
                        graph_sp.append("")
                    else:
                        if current_sp_data < 0:
                            graph_sp.append(1500)
                        else:
                            graph_sp.append(current_sp_data)
                else:
                    if current_sp_data < 0:
                        graph_sp.append(1500)
                    else:
                        graph_sp.append(current_sp_data)
            fixed_tp.append(self.json_data["caching_data"]["time_cached"])
            dates = mdates.num2date(mdates.datestr2num(fixed_tp))
            if self.json_data["rankedSeasonSkill"] < 0:
                sp_list.append(1500)
            else:
                sp_list.append(self.json_data["rankedSeasonSkill"])
            times_rewinded = 1
            previous_sp_data = graph_sp[fixed_tp.index(time) - times_rewinded]
            while previous_sp_data == "":
                times_rewinded += 1
                previous_sp_data = graph_sp[fixed_tp.index(time) - times_rewinded]
            if (
                abs(int(self.json_data["rankedSeasonSkill"]) - int(previous_sp_data))
                < 10
            ):
                graph_sp.append("")
            else:
                if self.json_data["rankedSeasonSkill"] < 0:
                    graph_sp.append(1500)
                else:
                    graph_sp.append(self.json_data["rankedSeasonSkill"])
            milky_color = "#ededed"
            mpl.rc("text", color=milky_color)
            mpl.rc("axes", labelcolor=milky_color)
            mpl.rc("xtick", color=milky_color)
            mpl.rc("ytick", color=milky_color)
            fig, ax = plt.subplots()
            ax.plot(dates, sp_list, color="#cc2310")
            ax.set(
                title=self._("{user}' skill points over time").format(
                    user=self.json_data["username"]
                ),
                xlabel=self._("Date"),
                ylabel=self._("Skill points"),
            )
            sp_size = 8
            amount_of_sp_obj = len(sp_list)
            while amount_of_sp_obj > 15 and sp_size != 4:
                sp_size -= 2
                amount_of_sp_obj -= 15
            for index in range(len(dates)):
                ax.text(dates[index], sp_list[index], graph_sp[index], size=sp_size)
            for reset_date in cfg.wov_season_resets:
                if (
                    dt.strptime(fixed_tp[0], "%Y-%m-%dT%H:%M:%S.%fZ") < reset_date
                    and dt.strptime(fixed_tp[-1], "%Y-%m-%dT%H:%M:%S.%fZ") > reset_date
                ):
                    plt.axvline(
                        x=reset_date,
                        ymin=0.05,
                        ymax=0.95,
                        color="#DCBB1E",
                        label=self._("Line - season reset"),
                    )
                    plt.legend(
                        loc="upper right"
                        if max(sp_list) != sp_list[-1]
                        else "lower right",
                        labelcolor=milky_color,
                        fontsize=7,
                        frameon=False,
                        fancybox=False,
                        shadow=False,
                        framealpha=0.0,
                    )
            ax.set_facecolor("#1f2736")
            fig.set_facecolor("#080b0f")
            fig.autofmt_xdate()
            plt.setp(ax.get_xticklabels(), rotation=30, horizontalalignment="right")
            with BytesIO() as im_bin:
                plt.savefig(im_bin, format="png")
                im_bin.seek(0)
                attachment = discord.File(fp=im_bin, filename="plot.png")
            plt.close()
            button.disabled = True
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(file=attachment)

    @discord.ui.button(
        label="", emoji=cfg.CustomEmojis.rerequest, style=discord.ButtonStyle.gray
    )
    async def repeat_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        time_diff = dt.utcnow() - dt.strptime(
            self.json_data["caching_data"]["time_cached"], "%Y-%m-%dT%H:%M:%S.%fZ"
        )
        time_diff = time_diff.total_seconds()
        if time_diff < 3600:  # 1 hour
            button.disabled = True
            await interaction.response.edit_message(view=self)
            async with AsyncTranslator(JO.get_lang_code(interaction.user.id)) as at:
                at.install()
                _ = at.gettext
                await interaction.followup.send(
                    content=_(
                        "Can't update information so frequently. Try again in **{again_in}**"
                    ).format(again_in=pretty_time_delta(3600 - time_diff))
                )
        else:
            WovFunc.history_caching(self.json_data)
            json_data_future = await self.api_caller.add_to_queue(
                WovApiCall.get_user_by_id, self.json_data["id"]
            )
            self.json_data = await json_data_future
            DF.json_caching("user", self.json_data)
            embedP = await self.embed_func(self.json_data)
            await interaction.response.edit_message(
                attachments=[embedP[1]], embed=embedP[0], view=self
            )

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True

        await self.message.edit(view=self)


class WovPlayerSelectUsernameConflict(discord.ui.View):
    def __init__(self, username_1: str, username_2: str):
        super().__init__(timeout=600)
        self.username_1 = username_1
        self.username_2 = username_2
        self.message: discord.Message
        self.value = None
        self.generate_buttons()

    def generate_buttons(self):
        self.button_1 = discord.ui.Button(
            label="{username}".format(username=self.username_1),
            style=discord.ButtonStyle.blurple,
        )
        self.button_2 = discord.ui.Button(
            label="{username}".format(username=self.username_2),
            style=discord.ButtonStyle.blurple,
        )
        self.button_1.callback = self.callback_1
        self.button_2.callback = self.callback_2
        self.add_item(self.button_1)
        self.add_item(self.button_2)

    async def callback_1(self, interaction: discord.Interaction):
        self.value = self.username_1
        self.stop()
        await self.message.delete()

    async def callback_2(self, interaction: discord.Interaction):
        self.value = self.username_2
        self.stop()
        await self.message.delete()

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)


class AvatarSelect(discord.ui.Select):
    def __init__(self, images: list, options, embed_names: list):
        super().__init__(
            options=options,
            placeholder="You can select an avatar...",
            min_values=1,
            max_values=1,
        )
        self.embeds = {"All_avatars": None}
        self.attachments = images
        self.embed_names = embed_names

    async def callback(self, interaction: discord.Interaction):
        if self.embeds["All_avatars"] is None:
            for item in self.embed_names:
                self.embeds[item] = {
                    "embed": discord.Embed(
                        title=re.sub("_", " ", item),
                        description="",
                        color=cfg.CustomColors.cyan,
                    ),
                    "attachment": self.attachments[self.embed_names.index(item)],
                }
        with BytesIO() as im_bin:
            key = re.sub("\s", "_", self.values[0])
            self.embeds[key]["attachment"].save(im_bin, "PNG")
            im_bin.seek(0)
            attachment = discord.File(fp=im_bin, filename=f"{key}.png")
            self.embeds[key]["embed"].set_image(url=f"attachment://{key}.png")
        await interaction.response.edit_message(
            embed=self.embeds[key]["embed"], attachments=[attachment]
        )


class WovPlayerAvatars(discord.ui.View):
    def __init__(
        self, images: list, select_options, embed_names: list, *, timeout=3600
    ):  # timeout = 1 hour
        super().__init__(timeout=timeout)
        self.add_item(
            AvatarSelect(images=images, options=select_options, embed_names=embed_names)
        )

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True

        await self.message.edit(view=self)


class ClanSelect(discord.ui.Select):
    def __init__(self, select_options, message_id) -> None:
        super().__init__(
            options=select_options,
            placeholder="Select a clan...",
            min_values=1,
            max_values=1,
        )
        self.message_id = message_id

    async def callback(self, interaction: discord.Interaction):
        WOV_CLAN_SEARCH[f"{self.message_id}"] = int(self.values[0])
        print(WOV_CLAN_SEARCH[f"{self.message_id}"])
        self.view.stop()
        await interaction.response.edit_message(view=None)


class ClanSearchView(discord.ui.View):
    def __init__(self, select_options: list, ctx_message_id, user_called):
        super().__init__(timeout=300)
        self.user = user_called
        self.add_item(
            ClanSelect(select_options=select_options, message_id=ctx_message_id)
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user.id:
            return True
        else:
            async with AsyncTranslator(
                JO.get_lang_code(interaction.user.id)
            ) as translator:
                translator.install()
                _ = translator.gettext
                await interaction.response.send_message(
                    _("You are not the one choosing! :pouting_cat:"), ephemeral=True
                )
            return False

    async def on_timeout(self) -> None:
        embed_err = discord.Embed(
            title="Timeout error",
            description="No clan number received",
            color=cfg.CustomColors.dark_red,
        )
        await self.message.edit(embed=embed_err, view=None)
        logger.debug('"Found Clans" asyncio.TimeoutError:Exiting command function')


class Wolvesville(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_url = "https://api.wolvesville.com/"
        self.api_caller = APICaller()

    async def cog_load(self):
        print("Wolvesville cog loaded successfully!")

    @commands.command(aliases=["wov-clan", "w-clan", "wov-c", "wovc", "w-c"])
    async def wovclan(self, ctx, *, clan_name: str = None):
        async with AsyncTranslator(
            JO.get_lang_code(ctx.message.author.id)
        ) as translator:
            translator.install()
            _ = translator.gettext
            if clan_name is None:
                embedErr = discord.Embed(
                    title=_("Error"),
                    description=_(
                        "No clan name specified. Correct syntax: `.wov-clan {clan name}`"
                    ),
                    color=cfg.CustomColors.red,
                )
                await ctx.send(embed=embedErr)
                return
            clan_name = surrogates.encode(clan_name)
            logger_clan_name = clan_name.encode("ascii", "ignore")
            logger_clan_name = logger_clan_name.decode()
            main_message = None
            DF.add_command_stats(ctx.message.author.id)
            clan_check = DF.cache_check("clan", "name", clan_name)
            if clan_check[0] is False:
                logger.info(
                    f'Couldn\'t find "{logger_clan_name}" in cache. Making an API call.'
                )
                clan_name_search = re.sub("\s", "%20", clan_name)
                clan_dict = await self.api_caller.add_to_queue(
                    WovApiCall.get_clan_by_name, clan_name_search
                )
                clan_dict = await clan_dict
                if len(clan_dict) == 0 or clan_dict is None:
                    embedErr = discord.Embed(
                        title=_("Error"),
                        description=_("Couldn't find any clan with that name."),
                        color=cfg.CustomColors.red,
                    )
                    await ctx.send(embed=embedErr)
                    logger.info(f'Couldn\'t find "{logger_clan_name}" using API')
                    return
                # // cl_names = ""
                # // for cl in clan_dict: cl_names += f"{surrogates.encode(cl['name'])}, "
                # // cl_names = cl_names.encode("ascii", "ignore")
                # // cl_names = cl_names.decode()
                logger.debug(f"(Length - {len(clan_dict)}.)")
                if len(clan_dict) > 1:
                    choose_embed = discord.Embed(
                        title=_("Clans found"),
                        description=_(
                            "use select menu in order to get information on the clan you need"
                        ),
                        color=cfg.CustomColors.cyan,
                    )
                    select_options = []
                    for clan in clan_dict:
                        clan_desc = clan["description"]
                        clan_desc = surrogates.encode(clan_desc)
                        clan_desc = surrogates.decode(clan_desc)
                        clan_desc_arr = clan_desc.split("\n")
                        clan_desc_oneline = ""
                        for i in range(len(clan_desc)):
                            if clan_desc_oneline != "":
                                break
                            clan_desc_oneline = clan_desc_arr[i]
                        if clan_desc_oneline == "":
                            clan_desc_oneline = _("*No description*")
                        # // logger.debug(clan_desc_oneline)
                        # // clan_desc.encode(encoding="utf8").decode()
                        if "tag" in clan:
                            c_tag = re.sub(
                                "u([0-9a-f]{4})",
                                lambda m: chr(int(m.group(1), 16)),
                                clan["tag"],
                            )
                            c_tag = surrogates.decode(c_tag)
                        else:
                            c_tag = ""
                        clan_name = re.sub(
                            "u([0-9a-f]{4})",
                            lambda m: chr(int(m.group(1), 16)),
                            clan["name"],
                        )
                        clan_name = surrogates.decode(clan_name)
                        full_name = f"{c_tag} | {clan_name}"
                        choose_embed.add_field(
                            name=f"**{clan_dict.index(clan)+1}** `{c_tag}` | **{clan_name}** :flag_{clan['language'].lower()}:",
                            value=clan_desc_oneline,
                        )
                        select_options.append(
                            discord.SelectOption(
                                label=full_name, value=clan_dict.index(clan) + 1
                            )
                        )
                    view_chose = ClanSearchView(
                        select_options=select_options,
                        ctx_message_id=ctx.message.id,
                        user_called=ctx.message.author,
                    )
                    view_chose.message: discord.Message = await ctx.send(
                        embed=choose_embed, view=view_chose
                    )

                    if await view_chose.wait() is True:
                        embed_err = discord.Embed(
                            title=_("Timeout error"),
                            description=_("No clan number received"),
                            color=cfg.colors["red"],
                        )
                        await ctx.send(embed=embed_err)
                        logger.info(
                            '"Found Clans" asyncio.TimeoutError:Exiting command function'
                        )
                        return
                    dict_clan = clan_dict[WOV_CLAN_SEARCH[f"{ctx.message.id}"] - 1]
                    await view_chose.message.delete(delay=0.2)
                    logger_clan_name = dict_clan["name"].encode("ascii", "ignore")
                    logger_clan_name = logger_clan_name.decode()
                    logger.info(f"They chose {logger_clan_name}")
                    description = dict_clan["description"]
                    DF.json_caching("clan", dict_clan)
                    time_cached = dt.utcnow()
                    iso = time_cached.isoformat() + "Z"
                    dict_clan["caching_data"] = {}
                    dict_clan["caching_data"]["time_cached"] = str(iso)
                else:
                    dict_clan = clan_dict[0]
                    description = dict_clan["description"]
                    DF.json_caching("clan", dict_clan)
                    time_cached = dt.utcnow()
                    iso = time_cached.isoformat() + "Z"
                    dict_clan["caching_data"] = {}
                    dict_clan["caching_data"]["time_cached"] = str(iso)
            else:
                logger.info(f'Found "{logger_clan_name}" in cache. Retrieving.')
                clan_dict = JO.get_wov_clan_by_name(clan_name)
                dict_clan, description = clan_dict[1], clan_dict[0]

            def embed_creation(dict_clan, description):
                clan_name = re.sub(
                    "u([0-9a-f]{4})",
                    lambda m: chr(int(m.group(1), 16)),
                    dict_clan["name"],
                )
                clan_name = surrogates.decode(clan_name)
                c_tag = re.sub(
                    "u([0-9a-f]{4})",
                    lambda m: chr(int(m.group(1), 16)),
                    dict_clan["tag"],
                )
                c_tag = surrogates.decode(c_tag)
                clan_desc = surrogates.encode(description)
                clan_desc = surrogates.decode(clan_desc)
                try:
                    timestamp = timestamp = dt.strptime(
                        dict_clan["caching_data"]["time_cached"],
                        "%Y-%m-%dT%H:%M:%S.%fZ",
                    )
                except:
                    timestamp = dt.utcnow()
                timestamp = timestamp.replace(tzinfo=pytz.UTC)
                embed_clan = discord.Embed(
                    title=f"`{c_tag}` | {clan_name}",
                    description=_(
                        'General clan information about "{clan_name}" on Wolvesville'
                    ).format(clan_name=clan_name),
                    color=discord.Color.from_str(dict_clan["iconColor"]),
                    timestamp=timestamp,
                )
                file_thumbnail = discord.File(
                    "Images/wov_logo.png", filename="wov_logo.png"
                )
                embed_clan.set_thumbnail(url="attachment://wov_logo.png")
                embed_clan.add_field(
                    name=_("Description"), value=clan_desc, inline=False
                )
                embed_clan.add_field(name="XP", value=f"**{dict_clan['xp']:,}**")
                match dict_clan["joinType"]:
                    case "PUBLIC":
                        join_type = _("Public clan")
                    case "JOIN_BY_REQUEST":
                        join_type = _("Invite only clan")
                    case "PRIVATE":
                        join_type = _("Closed clan")
                embed_clan.add_field(
                    name=_("Language"), value=f":flag_{dict_clan['language'].lower()}:"
                )
                embed_clan.add_field(
                    name=_("Member count"), value=f"**{dict_clan['memberCount']}/50**"
                )
                try:
                    creationDate = f'<t:{calendar.timegm(dt.strptime(dict_clan["creationTime"], "%Y-%m-%dT%H:%M:%S.%fZ").timetuple())}:D>'
                except KeyError:
                    creationDate = _("August 3, 2018 or before")
                embed_clan.add_field(name=_("Creation date"), value=f"{creationDate}")
                embed_clan.add_field(name=_("Clan status"), value=join_type)
                embed_clan.add_field(
                    name=_("Minimum level to join"), value=dict_clan["minLevel"]
                )
                embed_clan.add_field(
                    name=_("Quests"), value=f"**{dict_clan['questHistoryCount']}**"
                )

                return (embed_clan, file_thumbnail)

            first_embed, file_thumbnail = embed_creation(dict_clan, description)
            first_embed.add_field(
                name=_("Members"),
                value=_("*loading...* {emoji}").format(emoji=cfg.CustomEmojis.loading),
                inline=False,
            )

            if main_message is not None:
                await main_message.edit(attachments=[file_thumbnail], embed=first_embed)
            else:
                main_message = await ctx.send(file=file_thumbnail, embed=first_embed)

            members_check = DF.cache_check(
                type_of_search="id", what_to_search="clan_members", name=dict_clan["id"]
            )
            if members_check[0] is True:
                member_list = JO.get_wov_clan_members(dict_clan["id"])
            else:
                member_list = await self.api_caller.add_to_queue(
                    WovApiCall.get_clan_members, dict_clan["id"]
                )
                member_list = await member_list
                DF.json_caching(
                    cache_type="clan_members",
                    json_data=member_list,
                    extra_data=dict_clan["id"],
                )
            first_embed.remove_field(-1)
            clan_leader_str = _("**Leader:** ")
            co_leader_str = _("\n**---Co-leaders---**")
            co_leader_str2 = ""
            members_str = _("\n**...Members...**")
            members_str2 = ""
            for clan_member in member_list:
                if clan_member["playerId"] == dict_clan["leaderId"]:
                    clan_leader_str += f"{clan_member['level'] if clan_member['level'] > 0 else '?'} | **{clan_member['username']}** - *{clan_member['xp']:,}xp*"
                    member_list.remove(clan_member)
                if clan_member["isCoLeader"] is True:
                    # print(len(clan_leader_str + co_leader_str+f"\n{clan_member['level']} | **{clan_member['username']}** -*{clan_member['xp']:,}xp*"))
                    if (
                        len(
                            clan_leader_str
                            + co_leader_str
                            + f"\n{clan_member['level'] if clan_member['level'] > 0 else '?'} | **{clan_member['username']}** - *{clan_member['xp']:,}xp*"
                        )
                        > 1024
                    ):
                        co_leader_str2 += f"\n{clan_member['level'] if clan_member['level'] > 0 else '?'} | **{clan_member['username']}** - *{clan_member['xp']:,}xp*"
                    else:
                        co_leader_str += f"\n{clan_member['level'] if clan_member['level'] > 0 else '?'} | **{clan_member['username']}** - *{clan_member['xp']:,}xp*"
                    member_list.remove(clan_member)
            for clan_member in member_list:
                # print(len(clan_leader_str + co_leader_str+co_leader_str2+members_str+f"\n{clan_member['level']} | **{clan_member['username']}** - *{clan_member['xp']:,}xp*"))
                if (
                    co_leader_str2 != ""
                    or len(
                        clan_leader_str
                        + co_leader_str
                        + co_leader_str2
                        + members_str
                        + f"\n{clan_member['level'] if clan_member['level'] > 0 else '?'} | **{clan_member['username']}** - *{clan_member['xp']:,}xp*"
                    )
                    > 1024
                ):
                    members_str2 += f"\n{clan_member['level'] if clan_member['level'] > 0 else '?'} | **{clan_member['username']}** - *{clan_member['xp']:,}xp*"
                else:
                    members_str += f"\n{clan_member['level'] if clan_member['level'] > 0 else '?'} | **{clan_member['username']}** - *{clan_member['xp']:,}xp*"
            if co_leader_str == _("\n**---Co-leaders---**"):
                co_leader_str = ""
            if members_str == _("\n**...Members...**"):
                members_str = ""
            if co_leader_str2 != "":
                first_embed.add_field(
                    name=_("Members"),
                    value=clan_leader_str + co_leader_str,
                    inline=False,
                )
                first_embed.add_field(
                    name=f"{cfg.CustomEmojis.empty}",
                    value=co_leader_str2 + members_str,
                    inline=False,
                )
            elif members_str2 != "":
                first_embed.add_field(
                    name=_("Members"),
                    value=clan_leader_str + co_leader_str + members_str,
                    inline=False,
                )
                first_embed.add_field(
                    name=f"{cfg.CustomEmojis.empty}", value=members_str2, inline=False
                )
            else:
                first_embed.add_field(
                    name=_("Members"),
                    value=clan_leader_str + co_leader_str + members_str,
                    inline=False,
                )
            view = WovClan(
                clan_json_data=dict_clan,
                embed_func=embed_creation,
                api_caller=self.api_caller,
            )
            view.message = await main_message.edit(embed=first_embed, view=view)

    @commands.command(aliases=["wov-player", "w-player", "wov-p", "wovp", "w-p"])
    async def wovplayer(
        self, ctx: commands.Context, username: str = None, arg: str = None
    ):
        async with AsyncTranslator(JO.get_lang_code(ctx.author.id)) as at:
            at.install()
            _ = at.gettext
            previous_username = None
            if username is None:
                embedErr = discord.Embed(
                    title=_("Error"),
                    description=_(
                        "No username provided. Correct syntax: `.wov-player {username}`"
                    ),
                    color=cfg.CustomColors.red,
                )
                await ctx.send(embed=embedErr)
                return
            elif len(username) < 3:
                embedErr = discord.Embed(
                    title=_("Error"),
                    description=_(
                        "Username is too short. At least 3 characters required"
                    ),
                    color=cfg.CustomColors.red,
                )
                await ctx.send(embed=embedErr)
                return
            cache_cck = DF.cache_check("user", "username", username)
            if cache_cck[0] is False:
                logger.debug(
                    "Couldn't find %s in cache. Making an API call...", username
                )
                player_dict_future = await self.api_caller.add_to_queue(
                    WovApiCall.get_user_by_name, username
                )
                player_dict = await player_dict_future
                if player_dict is None:
                    player_dict = DF.cache_check("user", "previous_username", username)
                    if player_dict[0] is False:
                        embedErr = discord.Embed(
                            title=_("Error"),
                            description=_(
                                "Couldn't find any user with that username. *Maybe they changed it?*"
                            ),
                            color=cfg.CustomColors.red,
                        )
                        await ctx.send(embed=embedErr)
                        return
                    player_dict = JO.get_wov_player_by_prev_username(username)
                    player_dict, bio_first, previous_username = (
                        player_dict[1],
                        player_dict[0],
                        player_dict[2],
                    )
                else:
                    bio_first = (
                        player_dict["personalMessage"]
                        if "personalMessage" in player_dict
                        else "*No personal message found*"
                    )

                DF.json_caching("user", player_dict)
            else:
                if username != cache_cck[1]["username"]:
                    player_username_strict = JO.get_wov_player_by_username(username)
                    if player_username_strict is None:
                        logger.debug(
                            "Couldn't find %s in cache. Making an API call...", username
                        )
                        player_dict_future = await self.api_caller.add_to_queue(
                            WovApiCall.get_user_by_name, username
                        )
                        player_dict = await player_dict_future
                        if player_dict is None:
                            player_dict = JO.get_wov_player_by_username(
                                cache_cck[1]["username"]
                            )
                        else:
                            embed_ask = discord.Embed(
                                title=_("Warning"),
                                description=_(
                                    "Found following usernames:\n- {usernameI}\n- {usernameII}"
                                ).format(
                                    usernameI=cache_cck[1]["username"],
                                    usernameII=username,
                                ),
                                color=cfg.CustomColors.saffron,
                            )
                            view = WovPlayerSelectUsernameConflict(
                                cache_cck[1]["username"], username
                            )
                            view.message = await ctx.send(embed=embed_ask, view=view)
                            await view.wait()
                            if view.value is None:
                                return
                            elif view.value == cache_cck[1]["username"]:
                                player_dict = JO.get_wov_player_by_prev_username(
                                    view.value
                                )
                                player_dict, bio_first, previous_username = (
                                    player_dict[1],
                                    player_dict[0],
                                    player_dict[2],
                                )
                            else:
                                bio_first, previous_username = (
                                    player_dict["personalMessage"]
                                    if "personalMessage" in player_dict
                                    else "*No personal message found*",
                                    None,
                                )
                                DF.json_caching("user", player_dict)
                    else:
                        player_dict, bio_first, previous_username = (
                            player_username_strict[1],
                            player_username_strict[0],
                            player_username_strict[2],
                        )
                else:
                    player_dict = JO.get_wov_player_by_username(username)
                    player_dict, bio_first, previous_username = (
                        player_dict[1],
                        player_dict[0],
                        player_dict[2],
                    )
            caching_time = (
                player_dict["caching_data"]["time_cached"]
                if "caching_data" in player_dict
                else dt.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            )
            if (
                dt.utcnow() - dt.strptime(caching_time, "%Y-%m-%dT%H:%M:%S.%fZ")
            ).days > 30:
                WovFunc.history_caching(player_dict)
                player_dict = await self.api_caller.add_to_queue(
                    WovApiCall.get_user_by_id, player_dict["id"]
                )
                player_dict = await player_dict
                bio_first = (
                    player_dict["personalMessage"]
                    if "personalMessage" in player_dict
                    else "*No personal message found*"
                )
                DF.json_caching("user", player_dict)
            DF.add_command_stats(ctx.message.author.id)
            if arg in ["avatars", "avatar"]:
                select_options, embed_names, attachments, avatar_functs, av_urls = (
                    [],
                    [],
                    [],
                    [],
                    [],
                )
                avatar_embed = discord.Embed(
                    title=_("All avatars"), description="", color=cfg.CustomColors.cyan
                )
                avatar_embed.add_field(
                    name=_("Rendering"),
                    value=_("loading... {emoji}").format(
                        emoji=cfg.CustomEmojis.loading
                    ),
                )
                main_message = await ctx.send(embed=avatar_embed)
                for avatar in player_dict["avatars"]:
                    if avatar["url"] in av_urls:
                        av_urls.append(avatar["url"])
                        continue
                    avatar_functs.append(
                        WovFunc.avatar_rendering(image_URL=avatar["url"], rank=False)
                    )
                    av_urls.append(avatar["url"])
                time_before_rendering = dt.now()
                attachments = await asyncio.gather(*avatar_functs)
                print(dt.now() - time_before_rendering)
                all_avatars_file = await WovFunc.all_avatars_rendering(
                    attachments, av_urls
                )
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
                        select_options.append(
                            discord.SelectOption(label=_("All avatars"))
                        )
                        embed_names.append("All_avatars")
                    else:
                        select_options.append(
                            discord.SelectOption(
                                label=_("Avatar {num}").format(
                                    num=attachments.index(avatar)
                                )
                            )
                        )
                        embed_names.append(f"Avatar_{attachments.index(avatar)}")
                avatar_embed.remove_field(0)
                view = WovPlayerAvatars(
                    images=attachments,
                    select_options=select_options,
                    embed_names=embed_names,
                )
                view.message = await main_message.edit(
                    embed=avatar_embed, attachments=[attachment], view=view
                )
            else:

                async def embed_creation(player_data):
                    statuses = {
                        "PLAY": ["<:letsplay:1025841396751544441>", "Let's play"],
                        "DEFAULT": [":green_circle:", "Appears online"],
                        "DND": [":red_circle:", "Do not disturb"],
                        "OFFLINE": [":black_circle:", "Invisible"],
                    }
                    try:
                        thumbnail = await WovFunc.avatar_rendering(
                            player_data["equippedAvatar"]["url"], player_data["level"]
                        )
                    except KeyError:
                        WovFunc.history_caching(player_data)
                        player_data = await self.api_caller.add_to_queue(
                            WovApiCall.get_user_by_name, username
                        )
                        DF.json_caching("user", player_data)
                        thumbnail = await WovFunc.avatar_rendering(
                            player_data["equippedAvatar"]["url"], player_data["level"]
                        )
                    try:
                        timestamp = dt.strptime(
                            player_data["caching_data"]["time_cached"],
                            "%Y-%m-%dT%H:%M:%S.%fZ",
                        )
                    except:
                        timestamp = dt.utcnow()
                    timestamp = timestamp.replace(tzinfo=pytz.UTC)
                    embed_color = player_data["profileIconColor"]
                    embedPlayer = discord.Embed(
                        title=f"{player_data['username']}",
                        description=f"Information I retrieved about {player_data['username']} on Wolvesville",
                        color=discord.Color.from_str(embed_color),
                        timestamp=timestamp,
                    )
                    with BytesIO() as im_bin:
                        thumbnail.save(im_bin, "PNG")
                        im_bin.seek(0)
                        attachment = discord.File(fp=im_bin, filename="image.png")
                        embedPlayer.set_thumbnail(url="attachment://image.png")
                    try:
                        bio = player_data["personal_message"]
                    except KeyError:
                        if bio_first != "":
                            bio = bio_first
                        else:
                            bio = "*No personal message found*"
                    embedPlayer.add_field(
                        name=_("Personal Message"), value=bio, inline=False
                    )
                    embedPlayer.add_field(
                        name=_("Level"),
                        value=f"**{player_data['level'] if player_data['level'] > 0 else '?'}**",
                    )
                    embedPlayer.add_field(
                        name=_("Status"),
                        value=f"{statuses[player_data['status']][0]} **{statuses[player_data['status']][1]}**",
                    )
                    LO_time_diff = dt.utcnow() - dt.strptime(
                        player_data["lastOnline"], "%Y-%m-%dT%H:%M:%S.%fZ"
                    )
                    LO_time_diff = LO_time_diff.total_seconds()
                    if LO_time_diff < 420:
                        lastOnlineFlag = _("Player is online")
                    else:
                        lastOnlineFlag = pretty_date(player_data["lastOnline"])
                    embedPlayer.add_field(
                        name=_("Last online"), value=f"{lastOnlineFlag}"
                    )
                    try:
                        creationDate = f'<t:{calendar.timegm(dt.strptime(player_data["creationTime"], "%Y-%m-%dT%H:%M:%S.%fZ").timetuple())}:D>'
                    except KeyError:
                        creationDate = _("*Date is private*")
                    embedPlayer.add_field(
                        name=_("Creation date"), value=f"{creationDate}"
                    )
                    embedPlayer.add_field(
                        name=_("Roses"),
                        value=_(
                            "Roses received: **{}** {}\nRoses sent: **{}** {} \nDiff: **{}**"
                        ).format(
                            player_data.get("receivedRosesCount", "?"),
                            cfg.CustomEmojis.single_rose,
                            player_data.get("sentRosesCount", "?"),
                            cfg.CustomEmojis.single_rose,
                            player_data["receivedRosesCount"]
                            - player_data["sentRosesCount"]
                            if "sentRosesCount" in player_data
                            and "receivedRosesCount" in player_data
                            else "?",
                        ),
                    )
                    embedPlayer.add_field(
                        name=_("Honor"),
                        value=_("*Ask developers to update the API*"),
                        inline=False,
                    )
                    # embedPlayer.add_field(name=f"{cfg.CustomEmojis.empty}", value=f"{cfg.CustomEmojis.empty}", inline=False)
                    ranked_keys = [
                        "rankedSeasonPlayedCount",
                        "rankedSeasonSkill",
                        "rankedSeasonMaxSkill",
                        "rankedSeasonBestRank",
                    ]
                    private_ranked = False
                    for item in ranked_keys:
                        match item:
                            case "rankedSeasonSkill":
                                if private_ranked:
                                    current_sp = _("**?**")
                                elif item in player_data and player_data[item] > 0:
                                    current_sp = f"**{player_data[item]}**"
                                else:
                                    current_sp = _(
                                        "*Didn't participate in current season or data is private*"
                                    )
                            case "rankedSeasonMaxSkill":
                                if private_ranked:
                                    max_sp = _("**?**")
                                elif item in player_data and player_data[item] > 0:
                                    max_sp = f"**{player_data[item]}**"
                                else:
                                    max_sp = _(
                                        "*Didn't participate in any season yet or data is private*"
                                    )
                            case "rankedSeasonBestRank":
                                if private_ranked:
                                    best_rank = _("**?**")
                                elif item in player_data and player_data[item] > 0:
                                    best_rank = f"**{player_data[item]}**"
                                else:
                                    best_rank = _(
                                        "*Didn't participate in any season yet or data is private*"
                                    )
                            case "rankedSeasonPlayedCount":
                                if item in player_data and player_data[item] > 0:
                                    seasons_played = f"**{player_data[item]}**"
                                else:
                                    seasons_played = _("*Data is private*")
                                    private_ranked = True
                    embedPlayer.add_field(
                        name=_("Ranked stats"),
                        value=_(
                            "Current sp: {}\nOverall best sp: {}\nBest season final rank: {}\nSeasons participated in: **{}**"
                        ).format(current_sp, max_sp, best_rank, seasons_played),
                    )
                    if (
                        "gameStats" in player_data
                        and player_data["gameStats"]["totalWinCount"] > 0
                    ):
                        all_games = (
                            player_data["gameStats"]["totalWinCount"]
                            + player_data["gameStats"]["totalLoseCount"]
                            + player_data["gameStats"]["totalTieCount"]
                            + player_data["gameStats"]["exitGameBySuicideCount"]
                        )
                        gen_percentages = {
                            "totalWinCount": 0,
                            "totalLoseCount": 0,
                            "totalTieCount": 0,
                            "exitGameBySuicideCount": 0,
                        }
                        for perc in gen_percentages:
                            gen_percentages[perc] = round(
                                percentage_calc(
                                    all_games, player_data["gameStats"][perc]
                                ),
                                2,
                            )
                        if (
                            "totalPlayTimeInMinutes" not in player_data["gameStats"]
                            or player_data["gameStats"]["totalPlayTimeInMinutes"] < 0
                        ):
                            total_playtime = _("*Data is private*")
                        else:
                            total_playtime = timedelta(
                                minutes=player_data["gameStats"][
                                    "totalPlayTimeInMinutes"
                                ]
                            )
                            total_playtime = (
                                f"{round(total_playtime.total_seconds()/3600, 2)}h"
                            )
                        general_stats = _(
                            "Total games played: **{}**\nTotal wins: **{} ({:.2f}%)**\nTotal defeats: **{} ({:.2f}%)**\nTotal ties: **{} ({:.2f}%)**\nFlee count: **{} ({:.2f}%)**\nTotal playtime: **{}**"
                        ).format(
                            all_games
                            - player_data["gameStats"]["exitGameBySuicideCount"],
                            player_data["gameStats"]["totalWinCount"],
                            gen_percentages["totalWinCount"],
                            player_data["gameStats"]["totalLoseCount"],
                            gen_percentages["totalLoseCount"],
                            player_data["gameStats"]["totalTieCount"],
                            gen_percentages["totalTieCount"],
                            player_data["gameStats"]["exitGameBySuicideCount"],
                            gen_percentages["exitGameBySuicideCount"],
                            total_playtime,
                        )
                    else:
                        general_stats = _("*This data is private*")

                    if player_data["gameStats"]["villageWinCount"] >= 0:
                        role_percentages = {
                            "solo": 0,
                            "voting": 0,
                            "village": 0,
                            "werewolf": 0,
                        }
                        for perc in role_percentages:
                            total_role_games = (
                                player_data["gameStats"][f"{perc}WinCount"]
                                + player_data["gameStats"][f"{perc}LoseCount"]
                            )
                            role_percentages[perc] = round(
                                percentage_calc(
                                    total_role_games,
                                    player_data["gameStats"][f"{perc}WinCount"],
                                ),
                                2,
                            )
                        role_stats = _(
                            "Village: **{}** Wins/**{}** Defeats  **({}% wr)**\nWerewolves: **{}** Wins/**{}** Defeats  **({}% wr)**\nSolo voting: **{}** Wins/**{}** Defeats  **({}% wr)**\nSolo killer: **{}** Wins/**{}** Defeats  **({}% wr)**"
                        ).format(
                            player_data["gameStats"]["villageWinCount"],
                            player_data["gameStats"]["villageLoseCount"],
                            role_percentages["village"],
                            player_data["gameStats"]["werewolfWinCount"],
                            player_data["gameStats"]["werewolfLoseCount"],
                            role_percentages["werewolf"],
                            player_data["gameStats"]["votingWinCount"],
                            player_data["gameStats"]["votingLoseCount"],
                            role_percentages["voting"],
                            player_data["gameStats"]["soloWinCount"],
                            player_data["gameStats"]["soloLoseCount"],
                            role_percentages["solo"],
                        )
                    else:
                        role_stats = _("*This data is private*")
                    embedPlayer.add_field(name=_("General stats"), value=general_stats)
                    embedPlayer.add_field(
                        name=_("Team stats"), value=role_stats, inline=False
                    )
                    try:
                        clan_id = player_data["clanId"]
                    except KeyError:
                        clan_id = None
                    if clan_id is not None:
                        clan_check = DF.cache_check("clan", "id", player_data["clanId"])
                        if clan_check[0] is False:
                            logger.info(
                                "Couldn't find clan in cache. Making an API call..."
                            )
                            clan_dict_future = await self.api_caller.add_to_queue(
                                WovApiCall.get_clan_by_id, player_data["clanId"]
                            )
                            clan_dict = await clan_dict_future
                            clan_desc = clan_dict["description"]
                            DF.json_caching("clan", clan_dict)
                        else:
                            clan_dict = JO.get_wov_clan_by_id(player_data["clanId"])
                            clan_desc, clan_dict = clan_dict[0], clan_dict[1]
                            if (
                                dt.utcnow()
                                - dt.strptime(
                                    clan_dict["caching_data"]["time_cached"],
                                    "%Y-%m-%dT%H:%M:%S.%fZ",
                                )
                            ).days > 30:
                                clan_dict = await WovApiCall.get_clan_by_id(
                                    player_data["clanId"]
                                )
                                DF.json_caching("clan", clan_dict)
                                clan_desc = clan_dict["description"]

                        clan_desc = surrogates.encode(clan_desc)
                        clan_desc = surrogates.decode(clan_desc)
                        clan_desc = clan_desc.split("\n")
                        clan_desc = clan_desc[0]
                        # // clan_desc.encode(encoding="utf8").decode()
                        c_tag = re.sub(
                            "u([0-9a-f]{4})",
                            lambda m: chr(int(m.group(1), 16)),
                            clan_dict["tag"],
                        )
                        c_tag = surrogates.decode(c_tag)
                        clan_name = re.sub(
                            "u([0-9a-f]{4})",
                            lambda m: chr(int(m.group(1), 16)),
                            clan_dict["name"],
                        )
                        clan_name = surrogates.decode(clan_name)
                        clan_info = _(
                            "`{}` | **{}** :flag_{}: \n{}***...***\n*use `.wov-clan {}` for more information*"
                        ).format(
                            c_tag,
                            clan_name,
                            clan_dict["language"].lower(),
                            clan_desc,
                            clan_name,
                        )
                    else:
                        clan_info = _("*Not in clan or this data is private*")
                    embedPlayer.add_field(name=_("Clan"), value=clan_info, inline=False)
                    embedPlayer.add_field(
                        name=_("Avatars"),
                        value=_(
                            "*Use command `.wov-player {username} avatars` for avatars*"
                        ).format(username=username),
                    )
                    if previous_username:
                        embedPlayer.add_field(
                            name=_("Previous username"), value=previous_username
                        )
                    objects_to_return = [embedPlayer, attachment]
                    return objects_to_return

                embedP = await embed_creation(player_dict)
                try:
                    if arg.isdigit():
                        if int(arg) <= 30:
                            days = int(arg)
                        else:
                            days = 30
                    else:
                        days = 30
                except:
                    days = 30
                view = WovPlayer(
                    embed_func=embed_creation,
                    json_data=player_dict,
                    days=days,
                    gettext=_,
                    api_caller=self.api_caller,
                )
                view.message = await ctx.send(
                    file=embedP[1], embed=embedP[0], view=view
                )


async def setup(bot):
    await bot.add_cog(Wolvesville(bot))
