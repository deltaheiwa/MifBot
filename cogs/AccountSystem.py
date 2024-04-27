import random
import asyncio
from datetime import datetime as dt

import discord
from discord.ext import commands
from discord.interactions import Interaction

from bot_util.functions.universal import pretty_time_delta
from bot_util.functions.bot import coins_formula
from bot_util.misc import Logger, AsyncTranslator
from bot_util import bot_config
from db_data.psql_main import DatabaseFunctions as DF

logger = Logger(__name__, log_file_path=bot_config.LogFiles.account_system_log)


class DeleteConfirmationModal(discord.ui.Modal):
    def __init__(self, previous_login, previous_password, _):
        super().__init__(title=_("Confirm"))
        self.prev_login = previous_login
        self.prev_password = previous_password
        self._ = _
        self.children: list[discord.ui.TextInput]
        self.add_textinputs()

    async def on_submit(self, interaction: discord.Interaction):
        if self.children[0].value != self.prev_login:
            embed = discord.Embed(
                title=self._("Error"),
                description=self._("**{username}** is not the right username.").format(
                    username=self.children[0].value
                ),
                color=discord.Color.dark_red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        if self.children[1].value != self.prev_password:  # TODO: Change to hashing
            embed = discord.Embed(
                title=self._("Error"),
                description=self._("**{password}** is wrong password.").format(
                    password=self.children[1].value
                ),
                color=discord.Color.dark_red(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        DF.delete_user(interaction.user.id)
        embed = discord.Embed(
            title=self._("Account deleted"),
            description=self._(
                "You successfully deleted your previous account. Now you can register a new one."
            ),
            color=discord.Color.from_rgb(200, 50, 5),
        )
        await interaction.response.edit_message(embed=embed, view=None)

    def add_textinputs(self):
        login = discord.ui.TextInput(
            label=self._("Username"),
            placeholder=self._("Input your previous username"),
            style=discord.TextStyle.short,
            required=True,
        )
        password = discord.ui.TextInput(
            label=self._("Password"),
            placeholder=self._("Input your previous password"),
            style=discord.TextStyle.short,
            required=True,
        )
        self.add_item(login)
        self.add_item(password)

    async def on_error(self, interaction: Interaction, error: Exception):
        logger.error(error)
        embed = discord.Embed(
            title=self._("Error"),
            description=self._(
                "Something went wrong. Please, try again later\n\nThis problem has been reported to the developer automatically"
            ),
            color=bot_config.CustomColors.dark_red,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

        await bot_config.bot.telegram_bot.send_automatic_exception(
            error,
            func=self.__class__.__name__,
            line=error.__traceback__.tb_lineno,
            extra="DeleteConfirmationModal. Check logs for more info",
        )


class RegAccountExists(discord.ui.View):
    def __init__(self, prev_login: str, prev_password: str, _, *, timeout=60):
        super().__init__(timeout=timeout)
        self.prev_login = prev_login
        self.prev_password = prev_password
        self.children: list[discord.ui.Button]
        self.message: discord.Message
        self._ = _

    @discord.ui.button(
        label="",
        emoji=bot_config.CustomEmojis.checkmark_button,
        style=discord.ButtonStyle.green,
    )
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title=self._("Warning!"),
            description=self._(
                "If you will register a new account, you will lose your previous account! \nPlease input login and password of your previous account to proceed, or press **Cancel** button."
            ),
            color=bot_config.CustomColors.saffron,
        )
        modal_button = discord.ui.Button(
            label="Confirm", style=discord.ButtonStyle.blurple
        )
        cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.red)

        async def modal_button_callback(interaction: discord.Interaction):
            await interaction.response.send_modal(
                DeleteConfirmationModal(
                    previous_login=self.prev_login,
                    previous_password=self.prev_password,
                    _=self._,
                )
            )

        async def cancel_button_callback(interaction: discord.Interaction):
            embed = discord.Embed(
                title=self._("Canceled"),
                description=self._(
                    "You canceled registration. If you want to login into your previous account, use `login` command"
                ),
                color=bot_config.CustomColors.cyan,
            )
            await interaction.response.edit_message(embed=embed, view=None)

        async def on_timeout(self) -> None:
            for item in self.children:
                item.disabled = True

            await self.message.edit(view=self)

        cancel_button.callback = cancel_button_callback
        modal_button.callback = modal_button_callback
        view = discord.ui.View(timeout=180)
        view.add_item(modal_button)
        view.add_item(cancel_button)
        view.on_timeout = on_timeout  # type: ignore
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(
        label="",
        emoji=bot_config.CustomEmojis.crossmark_button,
        style=discord.ButtonStyle.red,
    )
    async def decline(
            self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        embed = discord.Embed(
            title=self._("You declined"),
            description=self._(
                "If you want to login into your account, simply use the `login` command"
            ),
            color=bot_config.CustomColors.red,
        )
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True

        await self.message.edit(view=self)

    async def on_error(self, interaction: Interaction, error: Exception):
        logger.error(error)
        embed = discord.Embed(
            title=self._("Error"),
            description=self._(
                "Something went wrong. Please, try again later\n\nThis problem has been reported to the developer automatically"
            ),
            color=bot_config.CustomColors.dark_red,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await bot_config.bot.telegram_bot.send_automatic_exception(
            error,
            func=self.__class__.__name__,
            line=error.__traceback__.tb_lineno,
            extra="RegAccountExists. Check logs for more info",
        )


class RegistrationModal(discord.ui.Modal):
    def __init__(self, _):
        self._ = _
        super().__init__(title=_("Registration Form"))
        self.children: list[discord.ui.TextInput]
        self.add_textinputs()

    def add_textinputs(self):
        login = discord.ui.TextInput(
            label=self._("Username"),
            placeholder=self._("No special characters are allowed"),
            style=discord.TextStyle.short,
            min_length=3,
            max_length=50,
            required=True,
        )
        password = discord.ui.TextInput(
            label=self._("Password"),
            placeholder=self._("Shouldn't be shorter than 4 characters"),
            style=discord.TextStyle.short,
            min_length=4,
            max_length=128,
            required=True,
        )
        confirm_password = discord.ui.TextInput(
            label=self._("Confirm Password"),
            placeholder=self._("Repeat your password"),
            style=discord.TextStyle.short,
            min_length=4,
            max_length=128,
            required=True,
        )
        nickname = discord.ui.TextInput(
            label=self._("Nickname"),
            placeholder=self._("If empty, will be equal to your login"),
            min_length=2,
            max_length=50,
            style=discord.TextStyle.short,
        )

        self.add_item(login)
        self.add_item(password)
        self.add_item(confirm_password)
        self.add_item(nickname)

    async def on_submit(self, interaction: discord.Interaction):
        if any(not c.isalnum() for c in self.children[0].value.replace(" ", "")):
            embedErr = discord.Embed(
                title=self._("Error"),
                description=self._(
                    "`{username}` contains a special character.\nUse a different username"
                ).format(username=self.children[0].value),
                color=bot_config.CustomColors.dark_red,
            )
            await interaction.response.send_message(embed=embedErr, ephemeral=True)
            return
        if DF.check_if_login_exists(self.children[0].value):
            embedErr = discord.Embed(
                title=self._("Error"),
                description=self._(
                    "Sorry! An account with this username already exists.\nInput a different username"
                ),
                color=bot_config.CustomColors.dark_red,
            )
            await interaction.response.send_message(embed=embedErr, ephemeral=True)
            return
        if self.children[1].value != self.children[2].value:
            embedErr = discord.Embed(
                title=self._("Error"),
                description=self._(
                    "Passwords {password} and {confirm_password} don't match!"
                ).format(
                    password=self.children[1].value,
                    confirm_password=self.children[2].value,
                ),
                color=bot_config.CustomColors.dark_red,
            )
            await interaction.response.send_message(embed=embedErr, ephemeral=True)
            return
        if any(not c.isalnum() for c in self.children[3].value):
            embedErr = discord.Embed(
                title=self._("Error"),
                description=self._(
                    "`{nickname}` contains a special character.\nUse a different nickname"
                ).format(nickname=self.children[3].value),
                color=bot_config.CustomColors.dark_red,
            )
            await interaction.response.send_message(embed=embedErr, ephemeral=True)
            return
        if self.children[3].value == "":
            nickname = self.children[0].value
        else:
            nickname = self.children[3].value

        DF.on_new_player(
            interaction.user.id,
            {
                "login": self.children[0].value,
                "password": self.children[1].value,
                "nickname": nickname,
            },
        )
        embed = discord.Embed(
            title=self._("Congrats"),
            description=self._("You completed the registration"),
            color=bot_config.CustomColors.cyan,
        )
        await interaction.response.edit_message(embed=embed, view=None)

    async def on_error(self, interaction: Interaction, error: Exception):
        logger.error(error)
        embed = discord.Embed(
            title=self._("Error"),
            description=self._(
                "Something went wrong. Please, try again later\n\nThis problem has been reported to the developer automatically"
            ),
            color=bot_config.CustomColors.dark_red,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await bot_config.bot.telegram_bot.send_automatic_exception(
            error,
            func=self.__class__.__name__,
            line=error.__traceback__.tb_lineno,
            extra="RegistrationModal. Check logs for more info",
        )


class RegistrationView(discord.ui.View):
    def __init__(self, _, *, timeout=600):
        super().__init__(timeout=timeout)
        self._ = _
        self.children: list[discord.ui.Button]
        self.message: discord.Message

    @discord.ui.button(label="Register", style=discord.ButtonStyle.blurple)
    async def register(
            self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_modal(RegistrationModal(self._))

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True

        embed = discord.Embed(
            title=self._("Canceled"),
            description=self._("Registration canceled due to timeout"),
            color=bot_config.CustomColors.dark_red,
        )
        await self.message.edit(embed=embed, view=self)

    async def on_error(self, interaction: Interaction, error: Exception):
        logger.error(error)
        embed = discord.Embed(
            title=self._("Error"),
            description=self._(
                "Something went wrong. Please, try again later\n\nThis problem has been reported to the developer automatically"
            ),
            color=bot_config.CustomColors.dark_red,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await bot_config.bot.telegram_bot.send_automatic_exception(
            error,
            func=self.__class__.__name__,
            line=error.__traceback__.tb_lineno,
            extra="RegistrationView. Check logs for more info",
        )


class TransferConfirmModal(discord.ui.Modal):
    def __init__(self, account_info, user1, _):
        super().__init__(title="Transfer confirmation")
        self.account = account_info
        self.user1 = user1
        self._ = _
        self.children: list[discord.ui.TextInput]
        self.add_textinputs()

    def add_textinputs(self):
        login = discord.ui.TextInput(
            label="Username",
            placeholder="No special characters are allowed",
            style=discord.TextStyle.short,
            min_length=3,
            max_length=50,
            required=True,
        )
        password = discord.ui.TextInput(
            label="Password",
            placeholder="Shouldn't be shorter than 4 characters",
            style=discord.TextStyle.short,
            min_length=4,
            max_length=128,
            required=True,
        )
        self.add_item(login)
        self.add_item(password)

    async def on_submit(self, interaction: discord.Interaction):
        if (
                self.children[0].value == self.account["login"]
                and self.children[1].value == self.account["password"]
        ):
            DF.account_switch(self.user1.id, interaction.user.id)
            await self.user1.send(
                self._(
                    "Owner of the account accepted the transfer. You are now owner of this account :white_check_mark:"
                )
            )
            await interaction.response.send_message(
                "You successfully transferred account to {transferred_to} :white_check_mark:\nYou can create a new account now".format(
                    transferred_to=self.user1
                )
            )
        else:
            embedErr = discord.Embed(
                title="Error",
                description="Sorry! Wrong username or password",
                color=bot_config.CustomColors.dark_red,
            )
            await interaction.response.send_message(embed=embedErr, ephemeral=True)
            return

    async def on_error(self, interaction: Interaction, error: Exception):
        logger.error(error)
        embed = discord.Embed(
            title=self._("Error"),
            description=self._(
                "Something went wrong. Please, try again later\n\nThis problem has been reported to the developer automatically"
            ),
            color=bot_config.CustomColors.dark_red,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await bot_config.bot.telegram_bot.send_automatic_exception(
            error,
            func=self.__class__.__name__,
            line=error.__traceback__.tb_lineno,
            extra="TransferConfirmModal. Check logs for more info",
        )


class LoginModal(discord.ui.Modal):
    def __init__(self, bot, _):
        super().__init__(title=_("Login Form"))
        self.bot = bot
        self.children: list[discord.ui.TextInput]
        self._ = _
        self.add_textinputs()

    async def on_submit(self, interaction: discord.Interaction):
        if any(not c.isalnum() for c in self.children[0].value):
            embedErr = discord.Embed(
                title=self._("Error"),
                description=self._(
                    "`{username}` contains a special character.\nThis username is not allowed"
                ).format(username=self.children[0].value),
                color=bot_config.CustomColors.dark_red,
            )
            await interaction.response.send_message(embed=embedErr, ephemeral=True)
            return
        if DF.check_if_login_exists(self.children[0].value) is False:
            embedErr = discord.Embed(
                title=self._("Error"),
                description=self._(
                    "I couldn't find this username in my database. Maybe you misspelled it?"
                ),
                color=bot_config.CustomColors.dark_red,
            )
            await interaction.response.send_message(embed=embedErr, ephemeral=True)
            return
        information = DF.get_user_by_login(self.children[0].value)
        if isinstance(information, bool):
            return
        if self.children[1].value != information["password"]:
            embedErr = discord.Embed(
                title=self._("Wrong password"),
                description=self._("Password doesn't match"),
                color=bot_config.CustomColors.red,
            )
            await interaction.response.send_message(embed=embedErr, ephemeral=True)
            return
        if interaction.user.id != information["id"]:
            user1 = interaction.user
            if information["atc"] == 1:
                user2 = self.bot.get_user(int(information["id"]))
                embed = discord.Embed(
                    title="Transfer confirmation",
                    description="Someone else tried to log into account owned by you! Fill the form to confirm the transfer",
                    color=bot_config.CustomColors.cyan,
                )
                modal_button = discord.ui.Button(
                    label=self._("Accept"), style=discord.ButtonStyle.blurple
                )
                cancel_button = discord.ui.Button(
                    label=self._("Decline"), style=discord.ButtonStyle.red
                )

                async def modal_button_callback(interaction: discord.Interaction):
                    await interaction.response.send_modal(
                        TransferConfirmModal(
                            account_info=information, user1=user1, _=self._
                        )
                    )

                async def cancel_button_callback(interaction_b: discord.Interaction):
                    embed = discord.Embed(
                        title="Declined",
                        description="You declined the transfer. If you want to login into your account, use `login` command",
                        color=bot_config.CustomColors.cyan,
                    )
                    user1 = interaction.user
                    await user1.send(
                        self._(
                            "Owner of the account declined the transfer. You can register or log into your account"
                        )
                    )
                    await interaction_b.response.edit_message(embed=embed, view=None)

                async def on_timeout(self) -> None:
                    for item in self.children:
                        item.disabled = True
                    user1 = interaction.user
                    await user1.send(
                        self._(
                            "Owner of the account declined the transfer. You can register or log into your account"
                        )
                    )
                    await self.message.edit(view=self)

                cancel_button.callback = cancel_button_callback
                modal_button.callback = modal_button_callback
                view = discord.ui.View(timeout=180)
                view.add_item(modal_button)
                view.add_item(cancel_button)
                view.on_timeout = on_timeout  # type: ignore
                await user2.send(embed=embed, view=view)
                await interaction.response.send_message(
                    self._(
                        "Owner of this account has `Account transfer confirmation` enabled, and in order for you to get ownership they have to confirm transfer within 10 minutes. Also if you have an account already, you will lose it!"
                    )
                )
                return
        DF.on_login(interaction.user.id)
        await interaction.response.send_message(
            self._("Successfully logged in :white_check_mark:")
        )

    def add_textinputs(self):
        login = discord.ui.TextInput(
            label=self._("Username"),
            placeholder=self._("No special characters are allowed"),
            style=discord.TextStyle.short,
            min_length=3,
            max_length=50,
            required=True,
        )
        password = discord.ui.TextInput(
            label=self._("Password"),
            placeholder=self._("Shouldn't be shorter than 4 characters"),
            style=discord.TextStyle.short,
            min_length=4,
            max_length=128,
            required=True,
        )
        self.add_item(login)
        self.add_item(password)

    async def on_error(self, interaction: Interaction, error: Exception):
        logger.error(error)
        embed = discord.Embed(
            title=self._("Error"),
            description=self._(
                "Something went wrong. Please, try again later\n\nThis problem has been reported to the developer automatically"
            ),
            color=bot_config.CustomColors.dark_red,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await bot_config.bot.telegram_bot.send_automatic_exception(
            error,
            func=self.__class__.__name__,
            line=error.__traceback__.tb_lineno,
            extra="LoginModal. Check logs for more info",
        )


class LoginView(discord.ui.View):
    def __init__(self, bot, _, *, timeout=600):
        super().__init__(timeout=timeout)
        self.bot = bot
        self._ = _
        self.children: list[discord.ui.Button]
        self.message: discord.Message

    @discord.ui.button(label="Login", style=discord.ButtonStyle.blurple)
    async def login(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LoginModal(bot=self.bot, _=self._))

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True

        embed = discord.Embed(
            title=self._("Canceled"),
            description=self._("Login canceled due to timeout"),
            color=bot_config.CustomColors.dark_red,
        )
        await self.message.edit(embed=embed, view=self)

    async def on_error(self, interaction: Interaction, error: Exception):
        logger.error(error)
        embed = discord.Embed(
            title=self._("Error"),
            description=self._(
                "Something went wrong. Please, try again later\n\nThis problem has been reported to the developer automatically"
            ),
            color=bot_config.CustomColors.dark_red,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await bot_config.bot.telegram_bot.send_automatic_exception(
            error,
            func=self.__class__.__name__,
            line=error.__traceback__.tb_lineno,
            extra="LoginView. Check logs for more info",
        )


# ---------------------------------------------------------------------------------------#
class AccountSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        print("AccountSystem cog loaded successfully!")

    @commands.hybrid_command(
        aliases=["reg", "signup"],
        name="register",
        description="Register an account for 'Mif'",
        with_app_command=True,
    )
    async def register(self, ctx: commands.Context):
        try:
            userM = ctx.message.author
            async with AsyncTranslator(DF.get_lang_code(userM.id)) as lang:
                lang.install()
                _ = lang.gettext
                if ctx.message.guild is not None:
                    await ctx.send(_("Check your DMS :grey_exclamation:"))
                if DF.check_if_member_exists(userM.id) is False:
                    logger.info(f"User {userM} not registered")
                else:
                    logger.info(f"User {userM} is already registered")
                    if DF.check_if_member_is_logged(userM.id):
                        await userM.send(_("You are already logged in!"))
                        return
                    else:
                        get_info = DF.get_user_by_id(userM.id, ["login", "password"])
                        logger.debug(get_info)
                        embed = discord.Embed(
                            title=_("Be careful!"),
                            description=_(
                                "You already have an account `{login}` registered on this discord account! If you register a new account, you will probably lose progress on a previous one.\nAre you sure you want to continue?"
                            ).format(login=get_info["login"]),
                            color=bot_config.CustomColors.cyan,
                        )
                        view = RegAccountExists(
                            prev_login=get_info["login"],
                            prev_password=get_info["password"],
                            _=_,
                        )
                        view.message = await userM.send(embed=embed, view=view)
                        return
                async with userM.typing():
                    await asyncio.sleep(3)
                embedWarn = discord.Embed(
                    title=_("Warning!"),
                    description=_(
                        "Never use your real discord credentials (email, password, etc.)!\nThis registration is only to access bot's features and store some extra stats"
                    ),
                    color=bot_config.CustomColors.saffron,
                )
                embedWarn.add_field(
                    name=_("Special Characters"),
                    value=_("Please, do not use any special characters"),
                )
                view_reg = RegistrationView(_=_)
                view_reg.message = await userM.send(embed=embedWarn, view=view_reg)
        except Exception as e:
            logger.exception(e)
            await self.bot.telegram_bot.send_automatic_exception(
                e, ctx=ctx, line=e.__traceback__.tb_lineno
            )

    @commands.hybrid_command(
        name="login", with_app_command=True, description="Login into your 'Mif' account"
    )
    async def login(self, ctx: commands.Context):
        try:
            user = ctx.author
            await ctx.defer(ephemeral=True)
            async with AsyncTranslator(DF.get_lang_code(user.id)) as lang:
                lang.install()
                _ = lang.gettext
                if ctx.message.guild is not None:
                    await ctx.send(_("Check your DMS :grey_exclamation:"))

                if DF.check_if_member_is_logged(user.id):
                    await user.send(_("You are already logged in!"))
                    return

                if DF.check_if_member_exists(user.id) is False:
                    embed = discord.Embed(
                        title=_("Warning!"),
                        description=_(
                            "I couldn't detect any account connected to your discord account. If you want to create a new account, use `register` command. \nAlthough you can log into existing account, but remember to confirm the account transfer"
                        ),
                        color=bot_config.CustomColors.saffron,
                    )
                    await user.send(embed=embed)
                async with user.typing():
                    await asyncio.sleep(1)

                embed = discord.Embed(
                    title=_("Reminder"),
                    description=_(
                        "If you are trying to login into account which is already connected to another account, you would probably need to confirm the transfer"
                    ),
                    color=bot_config.CustomColors.saffron,
                )
                view = LoginView(bot=self.bot, _=_)
                view.message = await user.send(embed=embed, view=view)
        except Exception as e:
            logger.exception(e)
            await self.bot.telegram_bot.send_automatic_exception(
                e, ctx=ctx, line=e.__traceback__.tb_lineno
            )

    @commands.hybrid_command(
        name="logout",
        with_app_command=True,
        description="Logs you out from your 'Mif' account",
    )
    async def logout(self, ctx: commands.Context):
        try:
            user = ctx.author
            await ctx.defer(ephemeral=True)
            async with AsyncTranslator(DF.get_lang_code(user.id)) as lang:
                lang.install()
                _ = lang.gettext
                if ctx.message.guild is not None:
                    await ctx.send(_("Check your DMS :grey_exclamation:"))
                if DF.check_if_member_exists(user.id) is False:
                    await user.send(
                        _(
                            "You don't have any account owned. Use `register` command to create a new account"
                        )
                    )
                else:
                    if DF.check_if_member_is_logged(user.id) is False:
                        await user.send(_("You are not logged into any account"))
                    else:
                        DF.on_logout(user.id)
                        await user.send(_("You successfully logged out!"))
        except Exception as e:
            logger.exception(e)
            await self.bot.telegram_bot.send_automatic_exception(
                e, ctx=ctx, line=e.__traceback__.tb_lineno
            )

    @commands.hybrid_command(
        name="nickname",
        with_app_command=True,
        description="Changes your nickname, of your 'Mif' account",
    )
    async def nickname(self, ctx: commands.Context, *, nickname=None):
        try:
            user = ctx.message.author
            await ctx.defer(ephemeral=True)
            async with AsyncTranslator(DF.get_lang_code(user.id)) as lang:
                lang.install()
                _ = lang.gettext
                if DF.check_if_member_is_logged(user.id) is False:
                    await ctx.send(
                        _(
                            "You don't have an account yet. You can register by using command `register`"
                        )
                    )
                    return
                if nickname is None:
                    await ctx.send(
                        _(
                            "Sorry but I see no nickname. Example: `.nickname My New Nickname`"
                        )
                    )
                    return
                DF.on_nickname_change(user.id, nickname)
                await ctx.send(
                    _("Nickname was successfully changed :white_check_mark:")
                )
                DF.add_to_command_stat(user.id)
        except Exception as e:
            logger.exception(e)
            await self.bot.telegram_bot.send_automatic_exception(
                e, ctx=ctx, line=e.__traceback__.tb_lineno
            )

    @commands.hybrid_command(
        name="wallet",
        with_app_command=True,
        description="Shows the amount of coins you have",
    )
    async def wallet(self, ctx: commands.Context):
        try:
            user = ctx.message.author
            await ctx.defer(ephemeral=True)
            async with AsyncTranslator(DF.get_lang_code(user.id)) as lang:
                lang.install()
                _ = lang.gettext
                if DF.check_if_member_is_logged(user.id) is True:
                    coins = DF.get_coins(user.id)
                    nickname = DF.get_user_by_id(user.id, ["nickname"])
                    logger.debug(f"{nickname['nickname']}' coins - {coins}")
                    embed = discord.Embed(
                        title=f"{nickname['nickname']}'s wallet",
                        description="**{coins}** {emoji}".format(
                            coins=coins, emoji=bot_config.CustomEmojis.spinning_coin
                        ),
                        color=user.color,
                    )
                    await ctx.send(embed=embed)
                    DF.add_to_command_stat(user.id)
                else:
                    await ctx.send(
                        _("You are not registered or not logged in!"), ephemeral=True
                    )
        except Exception as e:
            logger.exception(e)
            await self.bot.telegram_bot.send_automatic_exception(
                e, ctx=ctx, line=e.__traceback__.tb_lineno
            )

    @commands.hybrid_command(
        name="daily", with_app_command=True, description="Collect your daily!"
    )
    async def daily(self, ctx: commands.Context):
        try:
            user = ctx.message.author
            await ctx.defer(ephemeral=True)
            async with AsyncTranslator(DF.get_lang_code(user.id)) as lang:
                lang.install()
                _ = lang.gettext
                if DF.check_if_member_is_logged(user.id) is False:
                    await ctx.send(
                        _("You are not registered or not logged in!"), ephemeral=True
                    )
                    return
                info_about_daily = DF.get_daily_info(user.id)
                logger.info("{}'s {}".format(user, info_about_daily))
                time_diff = 75601
                if info_about_daily is None:
                    info_about_daily = {"dailyCount": 0, "lastDailyTime": None}
                if info_about_daily["lastDailyTime"] is not None:
                    time_diff = dt.utcnow() - dt.strptime(
                        info_about_daily["lastDailyTime"], "%Y-%m-%dT%H:%M:%S.%fZ"
                    )
                    time_diff = time_diff.total_seconds()
                if time_diff < 75600:
                    embed_too_early = discord.Embed(
                        title=_("Already collected"),
                        description=_(
                            "You may collect another daily in **{}**.\nYour daily streak is: **{} days**"
                        ).format(
                            pretty_time_delta(75600 - time_diff),
                            info_about_daily["dailyCount"],
                        ),
                        color=bot_config.CustomColors.red,
                    )
                    await ctx.send(embed=embed_too_early)
                    return
                if time_diff > 75600 * 2:
                    prev_streak = info_about_daily["dailyCount"]
                    info_about_daily["dailyCount"] = 1
                    info_about_daily["lastDailyTime"] = dt.utcnow().strftime(
                        "%Y-%m-%dT%H:%M:%S.%fZ"
                    )
                    coins_bonus = round(
                        coins_formula(
                            info_about_daily["dailyCount"], random.uniform(0.9, 1.3)
                        )
                    )
                    DF.add_coins(user.id, coins_bonus)
                    embed = discord.Embed(
                        title=_("Daily streak lost"),
                        description=_("You lost your streak of **{}** :(").format(
                            prev_streak
                        ),
                        color=discord.Color.from_rgb(2, 185, 209),
                    )
                    embed.add_field(
                        name=_("You gained"),
                        value="**{}** {}".format(
                            coins_bonus, bot_config.CustomEmojis.spinning_coin
                        ),
                        inline=False,
                    )
                    await ctx.send(embed=embed)
                    DF.update_daily_info(user.id, info_about_daily)
                    DF.add_to_command_stat(user.id)
                    return
                info_about_daily["dailyCount"] += 1  # type: ignore
                info_about_daily["lastDailyTime"] = dt.utcnow().strftime(
                    "%Y-%m-%dT%H:%M:%S.%fZ"
                )
                coins_bonus = round(
                    coins_formula(
                        info_about_daily["dailyCount"], random.uniform(0.9, 1.3)
                    )
                )
                DF.add_coins(user.id, coins_bonus)
                embed = discord.Embed(
                    title=_("Daily collected"),
                    description=_("You are on **{}** daily streak!").format(
                        info_about_daily["dailyCount"]
                    ),
                    color=bot_config.CustomColors.cyan,
                )
                embed.add_field(
                    name=_("You gained"),
                    value="{} {}".format(
                        coins_bonus, bot_config.CustomEmojis.spinning_coin
                    ),
                    inline=False,
                )
                await ctx.send(embed=embed)
                DF.update_daily_info(user.id, info_about_daily)
                DF.add_to_command_stat(user.id)
        except Exception as e:
            logger.exception(e)
            await self.bot.telegram_bot.send_automatic_exception(
                e, ctx=ctx, line=e.__traceback__.tb_lineno
            )


async def setup(bot):
    await bot.add_cog(AccountSystem(bot))
