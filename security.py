import asyncio
import datetime as dt
import time
import math
from typing import Optional, Tuple

import discord
from discord.ext import commands
from globalvars import REACT_CHECK, REACT_X, confirmation, get_helper_roles, get_manager_roles, get_staff_roles, get_vetcontrol_roles

from shattersbot import ShattersBot
import re

def user_search(name:str, guild: discord.Guild) -> Tuple[Optional[discord.Member], list]:
  """
  Searches for a user in a specific guild.
  Can be user ID, descriminator (e.g. achoo#8888), or IGN.
  IGNs are formatted like the following:
    (prefix)NameA | NameB | NameC
  Prefixes are ignored, and you can search for either Name A, B or C and they should
  all return the same person.

  Returns Tuple:
    Member (if found)
    All IGNs of the user, if found. If a member is found but this is still None, then the user's display name and discord name are the same.
  """
  if name is None or guild is None:
    return None, None

  search:discord.Member = None
  try:
    search = guild.get_member(int(name))

  except ValueError:
    if re.search("#", name):
      search = guild.get_member_named(name)

    else:
      matches = None
      for m in guild.members:
        matches = re.findall('[a-zA-Z]+', m.display_name.lower())
        if name.lower() in matches:
          search = m
          break
          
  return search, re.findall('[a-zA-Z]+', search.display_name) if search and search.display_name != search.name else None

def convert_time(time_count, time_type) -> int:
  time_type = time_type.lower()
  if time_type == 'y' or time_type == 'years' or time_type == 'year':
    timescale = 365 * 52 * 7 * 24 * 60 * 60
  elif time_type == 'w' or time_type == 'weeks' or time_type == 'week':
    timescale = 60 * 60 * 24 * 7
  elif time_type == 'd' or time_type == 'days' or time_type == 'day':
    timescale = 60 * 60 * 24
  elif time_type == 'h' or time_type == 'hours' or time_type == 'hour':
    timescale = 60 * 60
  elif time_type == 'm' or time_type == 'minutes' or time_type == 'minute':
    timescale = 60
  elif time_type == 's' or time_type == 'seconds' or time_type == 'second':
    timescale = 1
  else:
    return -1

  return timescale * time_count

class SecurityCog(commands.Cog, name="Security Commands"):
  AUTO_CHECK_TIME = 60 * 60 * 6

  def __init__(self, bot: ShattersBot):
    self.bot = bot
    self.auto_tasks = []

  def start_auto_check(self):
    self.auto_check_task = asyncio.create_task(self.auto_unsuspend_check())

  async def auto_unvetban(self, time_delay, guild_id, user_id):
    await asyncio.sleep(time_delay)
    self.bot.log(f"[SEC] Automatically un-vetbanning {user_id} in {guild_id}")

    guild: discord.Guild = self.bot.get_guild(guild_id)
    user: discord.Member = guild.get_member(user_id)
    banned_vet_role = guild.get_role(self.bot.get_vetbanned_role(guild.id))
    veteran_role = guild.get_role(self.bot.get_vetraider_role(guild.id))

    error = self.bot.tracker.deactivate_vetban(user.id, guild.id)
    if error:
      self.bot.log(f"[SEC] Auto unvetban for {user_id} in {guild_id} failed: {error}")
      return

    try:
      if banned_vet_role in user.roles:
        await user.add_roles(veteran_role, reason=f"Vet ban expired.")
        await user.remove_roles(banned_vet_role, reason=f"Vet ban expired.")
    except discord.Forbidden:
      self.bot.log(f"[SEC] Auto unvetban for {user_id} in {guild_id} failed due to perms.")
      return

    await user.send(f"Your vetban in {guild.name} has expired and you've been regiven the veteran role. Welcome back!")
    pass

  async def auto_unsuspend_check(self):
    while True:
      self.bot.log('[SEC] Checking for nearby discipline removals...')
      for guild in self.bot.guilds:
        active_vetbans, error = self.bot.tracker.get_active_vetbans(guild.id)
        if error:
          self.bot.log(f"[SEC] Skipping {guild.name}...")
          continue

        if len(active_vetbans) > 0:
          for ban in active_vetbans:
            self.bot.log(f'[SEC] [{guild.name}] Vetban ID#{ban[0]}: comp {time.time()} + {self.AUTO_CHECK_TIME} <= {ban[-1]}')
            if time.time() + self.AUTO_CHECK_TIME >= ban[-1]:
              self.bot.log(f'[SEC] [{guild.name}] -- Within 6 hours. Task scheduled.')
              self.auto_tasks.append(asyncio.create_task(self.auto_unvetban(ban[-1] - time.time(), guild.id, ban[0])))
            else:
              self.bot.log(f'[SEC] [{guild.name}] -- Not within 6 hours. Task not scheduled.')
      
      # Checks every six hours.
      self.bot.log('[SEC] Finished checking. Back to sleep!')
      await asyncio.sleep(self.AUTO_CHECK_TIME)
    pass

  @commands.command(name='find')
  @commands.has_any_role(*get_staff_roles())
  async def cmd_find_user(self, ctx: commands.Context, name=None):
    """
    [ERL+] Searches for a user.
    Can be user ID, descriminator (e.g. achoo#8888), or IGN.
    IGNs are formatted like the following:
      (prefix)NameA | NameB | NameC
    Prefixes are ignored, and you can search for either Name A, B or C and they should
    all return the same person.
    """
    if name is None:
      await ctx.send("Please enter a name, ID, or discord tag.")
      return

    found, igns = user_search(name, ctx.guild)

    embed = discord.Embed()
    embed.title=(f"User Search: {name}")

    if found is None:
      embed.color = discord.Color.brand_red()
      embed.description = f"`{name}` returned no matches."
    
    else:
      embed.color = discord.Color.brand_green()
      embed.description = f"Matched {found.mention}\n • Nick: `{found.display_name}`\n • ID: `{found.id}`"
      embed.set_thumbnail(url=found.display_avatar.url)
      embed.set_footer(text="Find is currently a work in progress :)")

      if igns:
        realmeye_val = ""
        for ign in igns:
          realmeye_val += f" • [{ign}](https://www.realmeye.com/player/{ign})\n"
        embed.add_field(name="RealmEye(s)", inline=True, value=realmeye_val)
        embed.add_field(name="Voice", inline=True, value=f"{found.voice.channel.mention}" if found.voice and found.voice.channel else "Not Connected")
      else:
        embed.description += "\n\nDoesn't seem to be verified."

    await ctx.send(embed=embed)

  @commands.command(name="history")
  @commands.has_any_role(*get_helper_roles())
  async def cmd_user_history(self, ctx: commands.Context, name=None):
    """
    [HELPER+] Shows the discipline history of a user.
    """
    if name is None:
      await ctx.send("Please enter a name, ID, or discord tag.")
      return

    user, _ = user_search(name, ctx.guild)
    if user is None:
      await ctx.send(f"Unable to find `{name}`")
      return

    embed = discord.Embed(title=f"Discipline History for {user.display_name}")
    embed.description = f"Search matched {user.mention}"
    embed.color = discord.Color.dark_purple()

    embed.add_field(name='Can Modmail?', value="`WIP`", inline=True)
    embed.add_field(name='Can Verify?', value="`WIP`", inline=True)
    embed.add_field(name='Mutes', value="`WIP`", inline=False)
    embed.add_field(name='Warns (Last Month)', value='`WIP`', inline=False)
    embed.add_field(name='Suspensions', value='`WIP`', inline=False)

    # Vetbans
    vetban_val = ""
    banhist, error = self.bot.tracker.get_user_vetban_history(user.id, ctx.guild.id)
    if error:
      await ctx.send(f"An error occurred while collecting vet ban history:\n`{error}`")
      return

    for item in banhist:
      mod = ctx.guild.get_member(item[2])
      vetban_val += f"{REACT_CHECK if item[0] else REACT_X}: `{item[1]}` by {mod.mention if mod else item[2]}"
      vetban_val += f" Expire{'s' if item[0] else 'd'} <t:{int(item[4])}:R>\n"
    
    if len(banhist) == 0:
      vetban_val = "None"

    embed.add_field(name='Vet Bans', value=vetban_val, inline=False)

    await ctx.send(embed=embed)

  @commands.command(name="vetban")
  @commands.has_any_role(*get_vetcontrol_roles())
  async def cmd_vetban(self, ctx: commands.Context, id_or_name=None, time_count=None, time_type=None, *reason_args):
    """[VRL/VERL+ & HELPER+] Removes "Veteran Raider" and gives "Banned Veteran Raider" for the specified duration.

    Args:
      id_or_name (int or str): The ID or name (IGN, no prefixes) of the person to vetban.
      time_count (int): Time duration count. Must be a whole number above 0.
      time_type (str): Type of time that time_count is counting. Can be s (seconds), m (minutes), h (hours), d (days), or w (weeks).
      reason_args (*): The reason. Continue typing after the time type to give a reason.

    Example command:
      ^vetban Sdj 2 w always leeches, never shoots while near the boss, absolute monkey
    """

    if id_or_name is None:
      await ctx.send("You must provide an ID or name.")
      return

    if time_count is None or time_type is None:
      await ctx.send("You must provide a valid time.")
      return

    # 0: Find the user
    guild: discord.Guild = ctx.guild
    user, _ = user_search(id_or_name, guild)

    banned_vet_role = guild.get_role(self.bot.get_vetbanned_role(guild.id))
    veteran_role = guild.get_role(self.bot.get_vetraider_role(guild.id))
    if banned_vet_role is None or veteran_role is None:
      await ctx.send("ERROR: Either banned vet role or vet rols is not set. Please contact an admin.")
      return

    if user is None:
      await ctx.send(f"Unable to find `{id_or_name}`")
      return

    # 1: Check to see if the person they're trying to vetban has vetcontrol
    for role in user.roles:
      if role.name in get_vetcontrol_roles():
        await ctx.send(embed=discord.Embed(description=f"You cannot vetban {user.mention}."))
        return

    # 2: Make sure the command is properly formed, with proper time_count & time_type
    try:
      time_c = int(time_count)
    except ValueError:
      await ctx.send("Invalid time amount.")
      return

    bantime = convert_time(time_c, time_type)
    if bantime < 0:
      await ctx.send("Invalid time type. Valid time types are 'w' (weeks), 'd' (days), 'h' (hours), 'm' (minutes), and 's' (seconds)")
      return

    ban_timestamp = time.time() + bantime

    # 3: Check to see if the user is already vet banned. If so, ask to overwrite.
    # If they aren't vet banned already, confirm that you want to vet ban.
    vetbancheck, reason, modid, error = self.bot.tracker.is_vetbanned(user.id, guild.id)
    if error:
      await ctx.send(f"Unable to vetban due to an error:\n{error}")
      return

    if vetbancheck is not None:
      banmod = guild.get_member(modid)
      confirmtext = f"""
      {user.mention} is already vet banned until <t:{int(vetbancheck)}:f> by {banmod.mention if banmod else modid}:\n
      ```reason```
      Your ban will ban them until <t:{int(ban_timestamp)}:f>.\n\nDo you want to overwrite the original ban?
      """
      if not await confirmation(ctx, self.bot, confirmtext):
        await ctx.message.add_reaction(REACT_X)
        return
    
    # 4: Vetban them.
    reason = ' '.join(reason_args)
    if await confirmation(ctx, self.bot, f"Are you sure you want to vetban {user.mention} until <t:{int(ban_timestamp)}:f>?\n: Reason: `{reason}`"):
      try:
        await user.add_roles(banned_vet_role, reason=f"Vetbanned by {ctx.author.display_name}: '{reason}'")
        await user.remove_roles(veteran_role, reason=f"Vetbanned by {ctx.author.display_name}: '{reason}'")
      except discord.Forbidden:
        await ctx.send("Forbidden error :/")
        return
      
      error = self.bot.tracker.add_vetban(user.id, guild.id, ctx.author.id, ctx.message.id, ban_timestamp, reason)
      if error:
        #undo if error
        await user.add_roles(veteran_role, reason=f"Error")
        await user.remove_roles(banned_vet_role, reason=f"Error")
        await ctx.send(error)
        return

      if time.time() + self.AUTO_CHECK_TIME > ban_timestamp:
        self.auto_tasks.append(asyncio.create_task(self.auto_unvetban(ban_timestamp - time.time(), ctx.guild.id, user.id)))

      await user.send(embed=discord.Embed(description=f"""
      You have been banned from veteran raiding in {guild.name} by {ctx.author.display_name} (`{ctx.author.name}#{ctx.author.discriminator}`).
      Reason: `{reason}`
      Your ban will automatically expire <t:{int(ban_timestamp)}:R>.
      If you wish to appeal, please message the person who vet banned you first before messaging anyone else.
      """, color=discord.Color.dark_red()))

      await ctx.send(embed=discord.Embed(description=f"{user.mention} was vetbanned."))

    else:
      await ctx.message.add_reaction(REACT_X)

  @commands.command('unvetban')
  @commands.has_any_role(*get_vetcontrol_roles())
  async def cmd_unvetban(self, ctx: commands.Context, id_or_name=None):
    """[VRL/VERL+ & HELPER+] Un-vetbans someone.

    Args:
      id_or_name (int or str): The ID or name (IGN, no prefixes) of the person to unvetban.

    Example command (though you'd never run it):
      ^unvetban Sdj
    """
    if id_or_name is None:
      await ctx.send("You must provide an ID or name.")
      return

    # 0: Find the user
    guild: discord.Guild = ctx.guild
    user, _ = user_search(id_or_name, guild)

    banned_vet_role = guild.get_role(self.bot.get_vetbanned_role(guild.id))
    veteran_role = guild.get_role(self.bot.get_vetraider_role(guild.id))
    if banned_vet_role is None or veteran_role is None:
      await ctx.send("ERROR: Either banned vet role or vet rols is not set. Please contact an admin.")
      return

    if user is None:
      await ctx.send(f"Unable to find `{id_or_name}`")
      return

    # 3: Check to see if the user is already vet banned. If so, ask to overwrite.
    # If they aren't vet banned already, confirm that you want to vet ban.
    vetbancheck, reason, modid, error = self.bot.tracker.is_vetbanned(user.id, guild.id)
    if error:
      await ctx.send(f"Unable to vetban due to an error:\n{error}")
      return

    if not vetbancheck:
      if banned_vet_role not in user.roles:
        await ctx.send(embed=discord.Embed(description=f"{user.mention} is not currently vet banned.", color=discord.Color.dark_red()))
        return
      
      if not await confirmation(ctx, self.bot, f"{user.mention} is not listed as vet banned but has the vet banned role. Would you like to remove it?"):
        await ctx.message.add_reaction(REACT_X)
        return

    else:
      banmod: discord.Member = ctx.guild.get_member(modid)
      if not await confirmation(ctx, self.bot, f"""
        {user.mention} was vet banned by {banmod.mention if banmod else modid} for the reason:
        ```{reason}```
        Their ban expires <t:{int(vetbancheck)}:R> on <t:{int(vetbancheck)}:f>.
        Are you sure you want to un-vetban them?
        """):
        await ctx.message.add_reaction(REACT_X)
        return

      error = self.bot.tracker.deactivate_vetban(user.id, guild.id)
      if error:
        await ctx.send(error)
        return

    try:
      if banned_vet_role in user.roles:
        await user.add_roles(veteran_role, reason=f"Unvetbanned by {ctx.author.display_name}")
        await user.remove_roles(banned_vet_role, reason=f"Unvetbanned by {ctx.author.display_name}")
    except discord.Forbidden:
      await ctx.send("Forbidden error :/")
      return

    await ctx.send(embed=discord.Embed(description=f"{user.mention} was un-vetbanned."))
    await user.send(f"You were unvetbanned in {guild.name} by `{ctx.author.name}#{ctx.author.discriminator}`. Welcome back!")


