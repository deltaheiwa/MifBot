import re
import discord
from discord.ext import commands

global GAME_SERVER_ID
GAME_SERVER_ID = 1158174710950015079


class ConfirmationView(discord.ui.View):
    def __init__(self, ctx, member):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.member = member
        self.value = None
        self.message: discord.Message

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        self.stop()

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        self.stop()

    async def on_timeout(self) -> None:
        await self.message.edit(content='Timed out', view=None)

class TempTToCW(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        self.regions = {}  # This will hold the mapping of regions and houses
        self.SPECIFIC_GUILD_ID = GAME_SERVER_ID  # Replace with your guild's ID
        self.COMMANDER_id = None
        self.COMMANDER_isAlive = False
        self.COMMANDER_currentLocation = 'DESERT'
        self.HOUSE_CATEGORIES = {'DESERT', 'PLAIN', 'UNDERGROUND', 'SPACE', 'OCEAN', 'JUNGLE', 'TUNDRA'}
        self.REPORTING_CHANNEL_ID: int = None
    
    async def cog_load(self) -> None:
        print("TempTToCW cog loaded successfully!")
    
    async def cog_unload(self) -> None:
        print("TempTToCW cog unloaded successfully!")

    def sanitize_category_name(self, name):
        # Remove emojis and special characters
        name = re.sub(r'[^\w\s]', '', name)
        # Remove hyphens and other non-alphanumeric characters except for whitespace
        name = re.sub(r'[-]', ' ', name)
        # Replace multiple spaces with a single space
        name = re.sub(r'\s+', ' ', name).strip()
        return name.upper()
    
    def get_region_data(self):
        region_data = ''
        for region_name, region_info in self.regions.items():
            region_data += f"{region_name}: \n"
            for house_name, house_id in region_info['houses'].items():
                region_data += f"{house_name}: {house_id}\n"
            region_data += '---------------\n'

        return region_data
    
    def get_commander_info(self):
        return f"Commander ID: {self.COMMANDER_id} ({self.bot.get_user(self.COMMANDER_id).mention})\nIs Alive: {self.COMMANDER_isAlive}\nCurrent Location: {self.COMMANDER_currentLocation}"

    # Command to map guild channels
    @commands.command(name='map-houses')
    @commands.has_permissions(administrator=True)
    async def mapHouses(self, ctx):
        # Ensure this command is only used in the specific guild
        if ctx.guild.id != self.SPECIFIC_GUILD_ID:
            return

        # Clear any existing mapping
        self.regions.clear()

        for category in ctx.guild.categories:
            # Sanitize the category name and then check if it is in the predefined list
            sanitized_name = self.sanitize_category_name(category.name)
            if sanitized_name in self.HOUSE_CATEGORIES:
                region_name = sanitized_name
                self.regions[region_name] = {'id': category.id, 'houses': {}}
                for channel in category.text_channels:  # Assuming houses are text channels
                    # Map the house channels
                    self.regions[region_name]['houses'][channel.name] = channel.id

        await ctx.send(f'House channels have been mapped for {len(self.regions)} regions.')

    # Event listener for channel updates
    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        if self.COMMANDER_isAlive is False:
            return
        # Check for updates in the specific guild
        if before.guild.id == self.SPECIFIC_GUILD_ID and isinstance(after, discord.TextChannel):
            # Check if the updated channel is a house in the COMMANDER's current location
            commander_category = self.COMMANDER_currentLocation

            
            player_role = discord.utils.get(after.guild.roles, name="Alive")
            
            # Determine the difference in overwrites between before and after
            before_overwrites = before.overwrites
            after_overwrites = after.overwrites

            # Find members who got added
            for target in after_overwrites:
                if (isinstance(target, discord.Member) and
                    after_overwrites[target].read_messages is True and
                    (target not in before_overwrites or before_overwrites[target].read_messages is not True)):
                    if player_role in target.roles:
                        if target.id == self.COMMANDER_id:
                            if self.sanitize_category_name(after.category.name) != commander_category:
                                self.COMMANDER_currentLocation = self.sanitize_category_name(after.category.name)
                                if self.REPORTING_CHANNEL_ID is not None:
                                    channel = self.bot.get_channel(self.REPORTING_CHANNEL_ID)
                                    await channel.send(f"Commander is now in {self.COMMANDER_currentLocation}")
                        elif commander_category in self.regions and after.id in self.regions[commander_category]['houses'].values():
                            if self.REPORTING_CHANNEL_ID is not None:
                                overseer_role = discord.utils.get(after.guild.roles, name="Overseer")
                                channel = self.bot.get_channel(self.REPORTING_CHANNEL_ID)
                                await channel.send(f"{overseer_role.mention} {target.mention} was added to {after.mention}. Inform Gala")

            # Find members who got removed
            for target in before_overwrites:
                if (isinstance(target, discord.Member) and
                    before_overwrites[target].read_messages is True and
                    (target not in after_overwrites or after_overwrites[target].read_messages is not True)):
                    if player_role in target.roles:
                        if commander_category in self.regions and after.id in self.regions[commander_category]['houses'].values():
                            if self.REPORTING_CHANNEL_ID is not None:
                                overseer_role = discord.utils.get(after.guild.roles, name="Overseer")
                                channel = self.bot.get_channel(self.REPORTING_CHANNEL_ID)
                            await channel.send(f"{overseer_role.mention} {target.mention} was removed from {after.mention}. Inform Gala")
    
    @commands.hybrid_command(name='set-commander-reminder-channel', aliases=["scrc"], guild=discord.Object(id=GAME_SERVER_ID))
    @commands.has_permissions(administrator=True)
    async def setCommanderReminderChannel(self, ctx):
        await ctx.defer(ephemeral=True)
        # Ensure this command is only used in the specific guild
        if ctx.guild.id != self.SPECIFIC_GUILD_ID:
            return
        
        self.REPORTING_CHANNEL_ID = ctx.channel.id
        await ctx.send("Commander reminder channel has been set to this channel.")
    
    @commands.hybrid_command(name='set-commander', aliases=["sc"], guild=discord.Object(id=GAME_SERVER_ID))
    @commands.has_permissions(administrator=True)
    async def setCommander(self, ctx, member: discord.Member):
        await ctx.defer(ephemeral=True)
        # Ensure this command is only used in the specific guild
        if ctx.guild.id != self.SPECIFIC_GUILD_ID:
            return
        
        if self.COMMANDER_id is not None:
            # write a confirmation prompt with view and two buttons
            view = ConfirmationView(ctx, member)
            
            # Send the confirmation message with the view
            view.message = await ctx.send(f"Are you sure you want to set {member.mention} as the commander?", view=view)
            await view.wait()
            if view.value is None or not view.value:
                await ctx.send("Cancelled.")
                await view.message.edit(view=None)
                return
        self.COMMANDER_id = member.id
        self.COMMANDER_isAlive = True
        await ctx.send(f"Commander has been set to {member.mention}")

    @commands.hybrid_command(name='kill-switch', aliases=["ks"], guild=discord.Object(id=GAME_SERVER_ID))
    @commands.has_permissions(administrator=True)
    async def killSwitch(self, ctx):
        await ctx.defer(ephemeral=True)
        # Ensure this command is only used in the specific guild
        if ctx.guild.id != self.SPECIFIC_GUILD_ID:
            return
        
        self.COMMANDER_isAlive = not self.COMMANDER_isAlive
        await ctx.send(f"Commander is now {'alive' if self.COMMANDER_isAlive else 'dead'}")


    @commands.command(name='suicide')
    async def suicide(self, ctx):
        if ctx.author.id == 835883093662761000:
            await ctx.send("Alright.")
            await self.bot.unload_extension("cogs.TempTToCW")

    @commands.command(name='debug-data')
    async def debugData(self, ctx: commands.Context):
        if ctx.author.id == 835883093662761000:
            region_data = self.get_region_data()
            commander_info = self.get_commander_info()
            formatted_data = f"### Region Data ###\n{region_data}\n\n### Commander Information ###\n{commander_info}"

            await ctx.send(formatted_data)




async def setup(bot):
    await bot.add_cog(TempTToCW(bot))