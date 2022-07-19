import datetime as dt

import discord
from discord.ext import commands
from globalvars import get_manager_roles, get_vetcontrol_roles

from shattersbot import ShattersBot
import re

def find_user_by_ign(guild: discord.Guild, name: str):
    for m in guild.members:
      if name.lower() in re.findall('[a-zA-Z]+', m.display_name.lower()):
        return m
    return None

class SecurityCog(commands.Cog, name="Security Commands"):
  def __init__(self, bot: ShattersBot):
    self.bot = bot

  @commands.command(name='find')
  @commands.has_any_role(*get_manager_roles())
  async def find_user_by_ign(self, ctx: commands.Context, name):
    search = None
    for m in ctx.guild.members:
      if name.lower() in re.findall('[a-zA-Z]+', m.display_name.lower()):
        search = m
        break

  @commands.command(name="vetban")
  @commands.has_any_role(*get_vetcontrol_roles())
  async def cmd_vetban(self, ctx: commands.Context, id_or_name, time_count, time_type, *reason_args):
    """[VRL/VERL+ & SEC+] Removes "Veteran Raider" and gives "Banned Veteran Raider" for the specified duration.

    Args:
      id_or_name (int or str): The ID or name (IGN, no prefixes) of the person to vetban.
      time_count (int): Time duration count. Must be a whole number above 0.
      time_type (str): Type of time that time_count is counting. Can be s (seconds), m (minutes), h (hours), d (days), or w (weeks).
      reason_args (*): The reason. Continue typing after the time type to give a reason.

    Example command:
      ^vetban Sdj 2 w always leeches, never shoots while near the boss, absolute monkey
    """

    # 0: Find the user
    g: discord.Guild = ctx.guild
    try:
      user_id = int(id_or_name)
      user = g.get_member(user_id)

      if user is None:
        await ctx.send(f"No user with id `{user_id}`.")
        return

    except ValueError:
      uname = id_or_name
      user = find_user_by_ign(g, uname)

      if user is None:
        await ctx.send(f"Unable to find user `{uname}`.")
        return

    # 1: Check to see if the user can be vet banned. This cannot be done if the user is:
    #    a) Someone with vet control
    #    b) Not a veteran raider
    vet_found = False
    already_banned = False
    for role in user.roles:
      if role.name in get_vetcontrol_roles():
        await ctx.send(embed=discord.Embed(description=f"You cannot vetban `{user.mention}`."))
        return

      if role.id == self.bot.get_vetraider_role(g.id):
        vet_found = True
      
      elif role.id == self.bot.get_vetbanned_role(g.id):
        already_banned = True

    if not vet_found and not already_banned:
      await ctx.send(embed=discord.Embed(description=f'{user.mention} is not a veteran raider or vet banned!'))
      return
    elif vet_found and already_banned:
      await ctx.send(embed=discord.Embed(description=f"{user.mention} is both veteran AND vet banned - consider asking an upper staff what's up."))
      return

    # 2: Make sure the command is properly formed, with proper time_count & time_type
    try:
      time_c = int(time_count)
    except ValueError:
      await ctx.send("Invalid time amount.")
      return

    time_type = time_type.lower()
    if time_type == 'w' or time_type == 'weeks':
      timescale = 60 * 60 * 24 * 7
    elif time_type == 'd' or time_type == 'days':
      timescale = 60 * 60 * 24
    elif time_type == 'h' or time_type == 'hours':
      timescale = 60 * 60
    elif time_type == 'm' or time_type == 'minutes':
      timescale = 60
    elif time_type == 's' or time_type == 'seconds':
      timescale = 1
    else:
      await ctx.send("Invalid time type. Valid time types are 'w' (weeks), 'd' (days), 'h' (hours), 'm' (minutes), and 's' (seconds)")
      return

    ban_expire_time = dt.datetime.now() + dt.timedelta(seconds=time_c * timescale)

    # 3: Check to see if the user is already vet banned. If so, ask to overwrite.
    # If they aren't vet banned already, confirm that you want to vet ban.
    if already_banned:
      
      pass
    
    # 4: Vetban them.
    else:
      pass