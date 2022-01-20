
import discord
from discord.ext import commands
from discord.ext.commands.bot import Bot

import asyncio
from globalvars import find_channel, get_unlockables, get_vetchannels, get_event_roles, get_raid_roles, confirmation, get_vetonlycmd, get_vetleader_roles
from globalvars import get_setcap_vetmax, get_setcap_vetmin, get_setcap_max, get_setcap_min
from hc_afk_helpers import check_vetleader, channel_checks, create_list, dungeon_checks

import dungeons

####
# AFK Types:
# - Normal: Has portal react, moves people out if they don't react
# - 
#
#


class AfkCheck:
  def __init__(self, owner, )
  pass

class AfkCmds(commands.Cog):
  def __init__(self, bot: commands.Bot):
    self.bot = bot
    self.afks = []
    
    # active afks: status channel: afk check obj
    self.active_afk = {}
  
  def _afk(self, statuschannelid):
    return self.active_afk(statuschannelid)
  
  async def afk_list(self, ctx, statuschannel, lazy, show_shatters=False,):
    start, dungeon = create_list(self.bot, ctx, show_shatters=show_shatters)
    if start:      
      if lazy is None:
        lazy = await confirmation(ctx, self.bot, "Would you like the AFK check to be lazy? (aka drag only until opened)")
      
      await self.afk_checks(self, ctx, dungeon, lazy)
      
      # TODO: Ask for location
      self.afk_checks(self, ctx, dungeon, lazy)
  
  async def afk_checks(self, ctx, dungeon, lazy, location):
    

    # Special options:
    if dungeon == None or dungeon == 'list':
      await self.afk_list(self.bot, ctx)
      return
    
    d = None
    for d_type in dungeons.dungeonlist:
      if dungeon in dungeons.dungeonlist[d_type]:
        d = dungeons.dungeonlist[d_type][dungeon]
        break

    # Confirm the dungeon is actually an option
    if d is None:
      await ctx.send(dungeon + " is not a valid dungeon. Type `=events` or `=ehc list` to view all options.")
      return
    
    await self.afk_main(ctx, d, lazy, location)
    pass
  
  async def afk_main(self, ctx, dungeon, lazy, location):
    pass
  
  @commands.command(name='eafk')
  @commands.has_any_role(*get_event_roles())
  async def eafk_command(self, ctx: commands.Context, type_or_dungeon:str=None, dungeon_or_cap:str=None, cap_or_loc:str=None, *other_location_parts):
    # Check to see if this channel can even support an AFK check.
    success, statuschannel = channel_checks(ctx)
    if success:
      # Check to see if the user is in a voice channel:
      voice_ch = ctx.author.voice.channel if ctx.author.voice and ctx.author.voice.channel else None
      if voice_ch is None:
        await ctx.send("You must be in a voice channel to use this command.")
        return
      
      
      if type_or_dungeon is None:
        await self.afk_list(ctx, statuschannel, None)
        return
      
      lazy = False
      dungeon = None
        
      if type_or_dungeon.lower() == 'l' or type_or_dungeon.lower() == 'lazy':
        lazy = True
        dungeon = dungeon_or_cap
        caploc = cap_or_loc
        third = other_location_parts
        
      else:
        dungeon = type_or_dungeon
        caploc = dungeon_or_cap
        third = [cap_or_loc, *other_location_parts] if other_location_parts else [cap_or_loc]
      
      dcheck_res = dungeon_checks(dungeon)
      
      # Dcheck res -2: Invalid dungeon given. Give an error.
      if dcheck_res == -2:
        await ctx.send(f'{type_or_dungeon} is an invalid dungeon type. Use `^events` or `^eafk list` to view a list of dungeons.')
        return

      # Dcheck res -1: They want/get the list.
      elif dcheck_res == -1:
        await self.afk_list(ctx, statuschannel, lazy)
        pass
      
      # Dcheck res 0: Everything checks out.
      elif dcheck_res == 0:
        if caploc:
          try:
            # We haven't dropped out of the try, hence, we do have a cap argument.
            cap = int(caploc)
            
            if voice_ch:
              is_unlockable = voice_ch in get_unlockables(ctx.guild.id)
              is_vetchannel = voice_ch in get_vetchannels(ctx.guild.id)
              if is_unlockable or is_vetchannel:
                if is_vetchannel:
                  capmax = get_setcap_vetmax(ctx.guild.id)
                  capmin = get_setcap_vetmin(ctx.guild.id)
                else:
                  capmax = get_setcap_max(ctx.guild.id)
                  capmin = get_setcap_min(ctx.guild.id)
                  
                if cap < capmin:
                  await ctx.send(f'Note: You cannot set the voice cap below {capmin}, so the cap has been set to {capmin}.')
                  cap = capmin
                  
                elif cap > capmax:
                  await ctx.send(f'Note: You cannot set the voice cap above {capmax}, so the cap has been set to {capmax}.')
                  cap = capmax
                  
                await voice_ch.edit(user_limit=cap)
              else:
                await ctx.send(f'Note: {voice_ch.mention} ')
          
            loc = ' '.join(*third) if third else None
          except ValueError:
          # caploc is not the cap, but is instead part of the location.
            loc = ' '.join(caploc, *third) if third else caploc
        else:
          # No cap, or location hereafter. Location will be TBD.
          
          
          
          
      
      if type_or_dungeon is None or type_or_dungeon.lower() == 'list':
        # If just eafk, ask for dungeon, 
        await self.afk_list(ctx, False)
        return
      
      
        # Lazy AFK check. dungeon_or_cap must be a dungeon. If not, there is an error.
        if dungeon_or_cap is None:
          # If no dungeon, but lazy specified: Ask for dungeon & location, then do lazy AFK.
          return
        
        try:
          cap = 
        
        if cap_or_loc is None:
          # No channel voice cap, and no location given. Set location as 'None'.
          cap_or_loc = 'None'
          
        
      
      pass
    
    
    
    if type_or_dungeon.lower() == 'l' or type_or_dungeon.lower() == 'lazy':
      
    
    if type_or_dungeon and type_or_dungeon.lower() == 'l':
      if dungeon:
        if dungeon.lower() == 'shatters':
          await ctx.send('No.')
        else:
          await self.afk_checks(ctx, dungeon.lower(), True)
      
    
    if dungeon and dungeon.lower() == 'shatters':
      await ctx.send('No.')
      return
    
    await self.afk_checks(ctx, dungeon.lower(), False)
    pass
    
  @commands.command(name='afk')
  @commands.has_any_role(*get_raid_roles())
  async def afk_command(self, ctx, type=None, location=None, cap=None):
    await self.afk_checks(ctx, 'shatters', False)