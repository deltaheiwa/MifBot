from calendar import c
from dis import disco
from pydoc import describe
import discord
import random
import asyncio
import json
from discord.ext import commands
from PIL import Image, ImageDraw, ImageChops, ImageFont
from io import BytesIO
from pathlib import Path
from functions import *
import GameFunctions as GF
import pymysql
import creds
import coloredlogs

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s:%(levelname)s --- %(message)s')
console_formatter = CustomFormatter()
stream_handler = logging.StreamHandler()
coloredlogs.install(level='DEBUG', logger=logger)
file_handler_debug = logging.FileHandler(config.account_system_log)
file_handler_debug.setFormatter(formatter)
stream_handler.setFormatter(console_formatter)
logger.addHandler(file_handler_debug)


class DeleteConfirmationModal(discord.ui.Modal):
    def __init__(self, previous_login, previous_password):
        super().__init__(title="Confirm")
        self.prev_login = previous_login
        self.prev_password = previous_password
        
    
    login = discord.ui.TextInput(
        label="Username", placeholder="Input your previous username", style=discord.TextStyle.short, required=True)
    password = discord.ui.TextInput(
        label="Password", placeholder="Input your previous password", style=discord.TextStyle.short, required=True)
    
    async def on_submit(self, interaction: discord.Interaction):
        if self.children[0].value != self.prev_login:
            embed = discord.Embed(
                title="Error", description=f"**{self.children[0].value}** is not the right username.", color=discord.Color.dark_red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        if self.children[1].value != self.prev_password:
            embed = discord.Embed(
                title="Error", description=f"**{self.children[1].value}** is wrong password.", color=discord.Color.dark_red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        delete_user(interaction.user)
        embed = discord.Embed(
            title="Account deleted",
            description="You successfully deleted your previous account. Now you can register a new one",
            color=discord.Color.from_rgb(200, 50, 5)
        )
        await interaction.response.edit_message(embed=embed, view=None)


class RegAccountExists(discord.ui.View):
    def __init__(self, prev_login, prev_password, *, timeout = 60):
        super().__init__(timeout=timeout)
        self.prev_login = prev_login
        self.prev_password = prev_password
    
    @discord.ui.button(label="", emoji=config.CustomEmojis.checkmark_button, style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="Warning!",
            description="If you will register a new account, you will lose your previous account! \nPlease input login and password of your previous account to proceed, or press **Cancel** button.",
            color=config.CustomColors.saffron)
        modal_button = discord.ui.Button(label="Confirm", style=discord.ButtonStyle.blurple)
        cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.red)
        
        async def modal_button_callback(interaction2: discord.Integration):
            await interaction2.response.send_modal(DeleteConfirmationModal(previous_login=self.prev_login, previous_password=self.prev_password))
        async def cancel_button_callback(interaction3: discord.Integration):
            embed=discord.Embed(title="Canceled", description="You canceled registration. If you want to login into your previous account, use `login` command", color=config.CustomColors.cyan)
            await interaction3.response.edit_message(embed=embed,view=None)
        async def on_timeout(self) -> None:
            for item in self.children:
                item.disabled = True
            
            await self.message.edit(view=self)
        cancel_button.callback = cancel_button_callback
        modal_button.callback = modal_button_callback
        view = discord.ui.View(timeout=180)
        view.add_item(modal_button)
        view.add_item(cancel_button)
        view.on_timeout = on_timeout
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="", emoji=config.CustomEmojis.crossmark_button, style=discord.ButtonStyle.red)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="You declined", description="If you want to login into your account, simply use `login` command",
            color=config.CustomColors.red)
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(embed=embed,view=self)
    
    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        
        await self.message.edit(view=self)

class RegistrationModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Registration Form")
        
    
    login = discord.ui.TextInput(
        label="Username", placeholder="No special characters are allowed", style=discord.TextStyle.short, min_length=3, max_length=50, required=True)
    password = discord.ui.TextInput(
        label="Password", placeholder="Shouldn't be shorter than 4 characters", style=discord.TextStyle.short, min_length=4, max_length=128, required=True)
    confirm_password = discord.ui.TextInput(
        label="Confirm Password", placeholder="Repeat your password", style=discord.TextStyle.short, min_length=4, max_length=128, required=True)
    nickname = discord.ui.TextInput(
        label="Nickname", placeholder="If empty, will be equal to your login", min_length=2, max_length=50, style=discord.TextStyle.short)
    
    async def on_submit(self, interaction: discord.Interaction):
        if any(not c.isalnum() for c in self.children[0].value):
            embedErr = discord.Embed(title="Error",
                description=f"`{self.children[0].value}` contains a special character.\nUse a different username", color= config.CustomColors.dark_red)
            await interaction.response.send_message(embed=embedErr, ephemeral=True)
            return
        if check_login(self.children[0].value):
            embedErr=discord.Embed(title="Error", description="Sorry! An account with this username already exists.\nInput a different username", color=config.CustomColors.dark_red)
            await interaction.response.send_message(embed=embedErr, ephemeral=True)
            return
        if self.children[1].value != self.children[2].value:
            embedErr=discord.Embed(title="Error", description=f"Passwords {self.children[1].value} and {self.children[2].value} don't match!", color=config.CustomColors.dark_red)
            await interaction.response.send_message(embed=embedErr, ephemeral=True)
            return
        if any(not c.isalnum() for c in self.children[3].value):
            embedErr = discord.Embed(title="Error",
                description=f"`{self.children[3].value}` contains a special character.\nUse a different username", color= config.CustomColors.dark_red)
            await interaction.response.send_message(embed=embedErr, ephemeral=True)
            return
        if self.children[3].value == "":
            nickname=self.children[0].value
        else:
            nickname=self.children[3].value
        
        on_new_player(interaction.user, [self.children[0].value, self.children[1].value, nickname])
        embed = discord.Embed(
            title="Congrats", description="You completed the registration", color=config.CustomColors.cyan)
        await interaction.response.edit_message(embed=embed, view=None)

class RegistrationView(discord.ui.View):
    def __init__(self, *, timeout = 600):
        super().__init__(timeout=timeout)
    
    @discord.ui.button(label="Register", style=discord.ButtonStyle.blurple)
    async def register(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RegistrationModal())
    
    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        
        embed=discord.Embed(title="Canceled", description="Registration canceled due to timeout", color=config.CustomColors.dark_red)
        await self.message.edit(embed=embed, view=self)

class TransferConfirmModal(discord.ui.Modal):
    def __init__(self, account_info, user1):
        super().__init__(title="Transfer confirmation")
        self.account = account_info
        self.user1 = user1
    
    login = discord.ui.TextInput(
        label="Username", placeholder="No special characters are allowed", style=discord.TextStyle.short, min_length=3, max_length=50, required=True)
    password = discord.ui.TextInput(
        label="Password", placeholder="Shouldn't be shorter than 4 characters", style=discord.TextStyle.short, min_length=4, max_length=128, required=True)
    
    async def on_submit(self, interaction: discord.Interaction):
        if self.children[0].value == self.account[0]['login'] and self.children[1].value == self.account[0]['password']:
            account_switch(self.user1, interaction.user)
            await self.user1.send("Owner of the account accepted the transfer. You are now owner of this account :white_check_mark:")
            await interaction.response.send_message(f"You successfully transfered account to {interaction.user} :white_check_mark:\nYou can create a new account now")
        else:
            embedErr=discord.Embed(title="Error", description="Sorry! Wrong username or password", color=config.CustomColors.dark_red)
            await interaction.response.send_message(embed=embedErr, ephemeral=True)
            return

class LoginModal(discord.ui.Modal):
    def __init__(self, bot):
        super().__init__(title="Registration Form")
        self.bot = bot
    
    login = discord.ui.TextInput(
        label="Username", placeholder="No special characters are allowed", style=discord.TextStyle.short, min_length=3, max_length=50, required=True)
    password = discord.ui.TextInput(
        label="Password", placeholder="Shouldn't be shorter than 4 characters", style=discord.TextStyle.short, min_length=4, max_length=128, required=True)
    
    async def on_submit(self, interaction: discord.Interaction):
        if any(not c.isalnum() for c in self.children[0].value):
            embedErr = discord.Embed(title="Error",
                description=f"`{self.children[0].value}` contains a special character.\nThis username is not allowed", color= config.CustomColors.dark_red)
            await interaction.response.send_message(embed=embedErr, ephemeral=True)
            return
        if check_login(self.children[0].value) is False:
            embedErr = discord.Embed(
                title="Error", description="I couldn't find this username in my database. Maybe you misspelled it?",
                color=config.CustomColors.dark_red)
            await interaction.response.send_message(embed=embedErr, ephemeral=True)
            return
        information = get_user_by_login(self.children[0].value)
        if self.children[1].value != information[0]['password']:
            embedErr = discord.Embed(
                title="Wrong password", description="Password doesn't match",
                color=config.CustomColors.dark_red)
            return
        if interaction.user.id != information[0]['id']:
            if information[0]['atc'] == 1:
                user2 = self.bot.get_user(int(information[0]['id']))
                embed = discord.Embed(
                    title="Transfer confirmation", description="Someone else tried to log into account owned by you! Fill the form to confirm the transfer", color=config.CustomColors.cyan)
                modal_button = discord.ui.Button(label="Accept", style=discord.ButtonStyle.blurple)
                cancel_button = discord.ui.Button(label="Decline", style=discord.ButtonStyle.red)
                
                async def modal_button_callback(interaction2: discord.Integration):
                    await interaction2.response.send_modal(TransferConfirmModal(account_info = information, user1 = interaction.user))
                async def cancel_button_callback(interaction3: discord.Integration):
                    embed=discord.Embed(title="Declined", description="You declined the transfer. If you want to login into your account, use `login` command", color=config.CustomColors.cyan)
                    user1 = interaction.user
                    await user1.send("Owner of the account declined the transfer. You can register or log into your account")
                    await interaction3.response.edit_message(embed=embed,view=None)
                
                
                async def on_timeout(self) -> None:
                    for item in self.children:
                        item.disabled = True
                    user1 = interaction.user
                    await user1.send("Owner of the account declined the transfer. You can register or log into your account")
                    await self.message.edit(view=self)
                cancel_button.callback = cancel_button_callback
                modal_button.callback = modal_button_callback
                view = discord.ui.View(timeout=180)
                view.add_item(modal_button)
                view.add_item(cancel_button)
                view.on_timeout = on_timeout
                await user2.send(embed=embed, view=view)
                await interaction.response.send_message("Owner of this account has `Account transfer confirmation` enabled, and in order for you to get ownership they have to confirm transfer within 10 minutes. Also if you have an account already, you will lose it!")
                return
        on_login(interaction.user.id)
        await interaction.response.send_message("Successfully logged in :white_check_mark:")

class LoginView(discord.ui.View):
    def __init__(self, bot, *, timeout = 600):
        super().__init__(timeout=timeout)
        self.bot = bot
    
    @discord.ui.button(label="Login", style=discord.ButtonStyle.blurple)
    async def login(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LoginModal(bot=self.bot))
    
    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        
        embed=discord.Embed(title="Canceled", description="Login canceled due to timeout", color=config.CustomColors.dark_red)
        await self.message.edit(embed=embed, view=self)

class AccountSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    async def cog_load(self):
        print("AccountSystem cog loaded successfully!")


    '''
    @commands.command(aliases=['prof'])
    async def profile(self, ctx, member: discord.Member = None):
        if member is None:
            member = ctx.author
        
        if check_exists(member) == False or check_logged(member) == False:
            if member == ctx.author:
                await ctx.send("You don't have an account yet. You can register by using command `register`")
            else:
                await ctx.send(format(member.mention)+" has no account yet")
        else:
            info_data_get = get_userdata_by_id(member, "*")
            info_data = info_data_get[0]
            info_get = get_user_by_id(member, "*")
            info = info_get[0]
            nick, bgNum, level, Xp, needXp = str(info['nickname']), str(info_data['bg']), str(
                info_data['level']), str(info_data['xp']), str(info_data['max_xp'])
            print(nick, bgNum, level, Xp, needXp)
            profileElements = Image.open(
                Path('Images', 'profile.png')).convert("RGBA")
            background = Image.open(
                Path('Images', f'bg{bgNum}.png')).convert("RGBA")
            pfp = member.display_avatar
            pfpdata = BytesIO(await pfp.read())
            pfp = Image.open(pfpdata)
            pfp = pfp.resize((114, 114))
            nick = f"{nick[:15]}.." if len(nick) > 15 else nick
            XpStr = f"{Xp} / {needXp}"

            draw = ImageDraw.Draw(profileElements)
            font = ImageFont.truetype("pixelFont2.ttf", 60)
            lvlfont = ImageFont.truetype("pixelFont2.ttf", 50)
            xpfont = ImageFont.truetype("pixelFont2.ttf", 36)

            draw.text((172, -5), nick, font=font, fill=(0, 0, 0, 255))
            if int(level) < 10:
                draw.text((397, 57), level, font=lvlfont, fill=(0, 0, 0, 255))
            elif int(level) >= 10 and int(level) < 100:
                draw.text((386, 57), level, font=lvlfont, fill=(0, 0, 0, 255))
            elif int(level) >= 100:
                draw.text((377, 57), level, font=lvlfont, fill=(0, 0, 0, 255))
            draw.text((260, 114), XpStr, font=xpfont, fill=(0, 0, 0, 255))
            profileElements.paste(pfp, (26, 27), pfp)
            background.paste(profileElements, (0, 0), profileElements)

            with BytesIO() as a:
                background.save(a, "PNG")
                a.seek(0)
                await ctx.send(file=discord.File(a, "profile.png"))
            add_command_stats(ctx.message.author)
    '''

    @commands.command(aliases=['reg'])
    async def register(self, ctx):
        userM = ctx.message.author
        if ctx.message.guild is not None:
            await ctx.send("Check your DMS :grey_exclamation:")
        if check_exists(userM) is False:
            logger.info(f"User {userM} not registered")
        else:
            logger.info(f"User {userM} is registered")
            if check_logged(userM):
                await userM.send("You are already logged in!")
                return
            else:
                get_info = get_user_by_id(userM.id, "login, password")
                logger.debug(get_info)
                embed = discord.Embed(title="Be careful!",
                                    description=f"You already have an account `{get_info[0]['login']}` registered on this discord account! If you register a new account, you will probably lose progress on a previous one.\nAre you sure you want to continue?",
                                    color=config.CustomColors.cyan)
                view = RegAccountExists(prev_login=get_info[0]['login'], prev_password=get_info[0]['password'])
                view.message = await userM.send(embed=embed, view=view)
                return
        async with userM.typing():
            await asyncio.sleep(3)
        embedWarn = discord.Embed(
            title="Warning!",
            description="Never use your real discord credentials (email, password, etc.)!\nThis registration is only to access bot's features and store some extra stats",
            color=config.CustomColors.saffron)
        embedWarn.add_field(name="Special Characters", value="Please, do not use any special characters")
        view_reg = RegistrationView()
        view_reg.message = await userM.send(embed=embedWarn, view=view_reg)

    @commands.command()
    async def login(self, ctx):
        user = ctx.author
        
        if ctx.message.guild != None:
            await ctx.send("Check your DMS :grey_exclamation:")
        
        if check_logged(user):
            await user.send("You are already logged in!")
            return
        
        if check_exists(user) is False:
            embed = discord.Embed(
                title="Warning!",
                description="I couldn't detect any account connected to your discord account. If you want to create a new account, use `register` command. \nAlthough you can log into existing account, but remember to confirm the account transfer",
                color=config.CustomColors.saffron)
            await user.send(embed=embed)
        async with user.typing():
            await asyncio.sleep(1)

        embed = discord.Embed(title="Reminder",
            description="If you are trying to login into account which is already connected to another account, you would probably need to confirm the transfer",
            color=config.CustomColors.saffron)
        view = LoginView(bot=self.bot)
        view.message = await user.send(embed=embed, view=view) 

    @commands.command()
    async def logout(self, ctx):
        user = ctx.author
        check = check_exists(user)
        if ctx.message.guild is None:
            pass
        else:
            await ctx.send("Check your DMS :grey_exclamation:")
        if check == False:
            await user.send("You don't have any account owned. Use `register` command to create a new account")
        else:
            if check_logged(user) == False:
                await user.send("You are not logged into any account")
            else:
                on_logout(user.id)
                await user.send("You successfully logged out!")

    # @commands.Cog.listener()
    # async def on_reaction_add(self, reaction, user, message):
        # if message ==
    
    @commands.hybrid_command(name="nickname",with_app_command=True, description="Changes your nickname, of your 'Mif' account")
    async def nickname(self, ctx: commands.Context, *, nickname = None):
        user = ctx.message.author
        await ctx.defer(ephemeral=True)
        if local_checks(user) is False:
            await ctx.send("You don't have an account yet. You can register by using command `register`")
            return
        if nickname is None:
            await ctx.send("Sorry but I see no nickname. Example: `.nickname My New Nickname`")
            return
        on_nickname_change(user.id, nickname)
        await ctx.send(f"Nickname was successfully changed :white_check_mark:")
        add_command_stats(user)

    @commands.hybrid_command(name="wallet",with_app_command=True, description="Shows the amount of coins you have")
    async def wallet(self, ctx: commands.Context):
        user = ctx.message.author
        await ctx.defer(ephemeral=True)
        if local_checks(user) == True:
            coins = get_userdata_by_id(user.id, 'cash')
            nickname = get_user_by_id(user.id, 'nickname')
            coins = coins['cash']
            logger.debug(f"{nickname[0]['nickname']}' coins - {coins}")
            embed = discord.Embed(title=f"{nickname[0]['nickname']}'s wallet", description=f"**{coins}** {config.CustomEmojis.spinning_coin} \n*Approximate value: {GF.get_coins(coins)[0:-1]}*", colour=user.color)
            await ctx.send(embed=embed)
            add_command_stats(user)
        else:
            await ctx.send("You are not registered or not logged in!", ephemeral=True)
    
    @commands.hybrid_command(name="daily", with_app_command=True, description="Collect your daily!")
    async def daily(self, ctx: commands.Context):
        user = ctx.message.author
        await ctx.defer(ephemeral=True)
        if local_checks(user) is False:
            await ctx.send("You are not registered or not logged in!", ephemeral=True)
            return
        info_about_daily = daily_info_json(user.id)
        user_coins = get_userdata_by_id(user.id, "cash")
        user_coins = user_coins['cash']
        logger.info(f"{user}'s {info_about_daily}")
        time_diff = 75601
        if info_about_daily is None:
            info_about_daily={"dailyCount": 0, "lastDailyTime": None}
        if info_about_daily['lastDailyTime'] is not None:
            time_diff = datetimefix.utcnow() - datetimefix.strptime(info_about_daily['lastDailyTime'], "%Y-%m-%dT%H:%M:%S.%fZ")
            time_diff = time_diff.total_seconds()
        if time_diff < 75600:
            embed_too_early = discord.Embed(title="Already collected", description=f"You may collect another daily in **{pretty_time_delta(75600 - time_diff)}**.\nYour daily streak is: **{info_about_daily['dailyCount']} days**", color=config.CustomColors.red)
            await ctx.send(embed=embed_too_early)
            return
        if time_diff > 75600*2:
            prev_streak = info_about_daily['dailyCount']
            info_about_daily['dailyCount'] = 1
            coins_bonus = round(coins_formula(info_about_daily['dailyCount']))
            update_userdata(user.id, "cash", user_coins+coins_bonus)
            embed=discord.Embed(title="Daily streak lost", description=f"You lost your streak of **{prev_streak}** :(", color=discord.Color.from_rgb(2, 185, 209))
            embed.add_field(name="You gained", value=f"{coins_bonus} {config.CustomEmojis.spinning_coin} \n*Approximate value: {GF.get_coins(coins_bonus)}*", inline=False)
            await ctx.send(embed=embed)
            await add_stats(user, "dailyInfo", replacement=info_about_daily['dailyCount'])
            add_command_stats(user)
            return
        info_about_daily['dailyCount'] += 1
        coins_bonus = round(coins_formula(info_about_daily['dailyCount']))
        update_userdata(user.id, "cash", user_coins+coins_bonus)
        embed=discord.Embed(title="Daily collected", description=f"You are on **{info_about_daily['dailyCount']}** daily streak!", color=config.CustomColors.cyan)
        embed.add_field(name="You gained", value=f"{coins_bonus} {config.CustomEmojis.spinning_coin} \n*Approximate value: {GF.get_coins(coins_bonus)}*", inline=False)
        await ctx.send(embed=embed)
        await add_stats(user, "dailyInfo", replacement=info_about_daily['dailyCount'])
        add_command_stats(user)
        


async def setup(bot):
    await bot.add_cog(AccountSystem(bot))
