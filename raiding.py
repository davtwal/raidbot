import discord
from discord.ext import commands

from typing import List, Dict, Optional, Tuple

from globalvars import RaidingSection, get_event_roles, get_raid_roles, confirmation

import dungeons
from hc_afk_helpers import channel_checks, create_list, dungeon_checks, get_voice_ch, ask_location
from hc_afk_helpers import DCHECK_LIST, DCHECK_INVALID
import section_manager as sm

managers: Dict[int, Dict[str, sm.SectionAFKCheckManager]] = {}

import globalvars as g

def setup_managers(bot: commands.Bot, new_managers):
  print('Setting up raid managers...')
  for gid in new_managers:
    managers[gid] = {}
    guild = bot.get_guild(gid)
    if guild is None:
      continue
    
    print(f'Guild {guild.name} (ID {gid}):')    
    for section_name in new_managers[gid]:
      print(f'- Section "{section_name}"')
      managers[gid][section_name] = sm.SectionAFKCheckManager(guild, section_name)
  
  print("Finshed setting up raid managers.")
  pass

class RaidingCmds(commands.Cog, name='Raiding Commands'):
  def __init__(self, bot: commands.Bot):
    self.bot = bot
  
  ## Listing Commands
  
  @commands.command(name='events')
  @commands.has_any_role(*get_event_roles())
  async def event_list(self, ctx):
    """[ERL+] Lists all of the possible dungeons for doing an Event AFK check."""
    #if ctx.guild.id != 850544046711111680: return
    await create_list(self.bot, ctx, allow_continue=False)
  
  @commands.command(name='dungeons')
  @commands.has_any_role(*get_event_roles())
  async def dungeon_list(self, ctx):
    """[ERL+] Lists all of the possible dungeons."""
    #if ctx.guild.id != 850544046711111680: return
    await create_list(self.bot, ctx, allow_continue=False, show_shatters=True)
  
  ######################
  ### HEADCOUNTS
  ######################
  
  async def headcount_main(self, ctx: commands.Context, d: dungeons.Dungeon, raid_section: RaidingSection):    
    bot = self.bot
    if d is None:
      await ctx.send("Error: d was None. Please contact an admin.")
      return
    
    statuschannel = ctx.guild.get_channel(raid_section.status_ch)
    if statuschannel is None:
      await ctx.send("Error: statuschannel was None. Please contact an admin.")
      return
    
    if statuschannel.type is not discord.ChannelType.text:
      await ctx.send("Error: statuschannel's type was not text. Please contact an admin.")
      return
    
    await managers[ctx.guild.id][raid_section.name].try_create_headcount(bot, ctx, statuschannel, d)

  ## Actual headcount commands

  @commands.command(name='ehc')
  @commands.has_any_role(*get_event_roles())
  async def event_headcount(self, ctx: commands.Context, dungeon=None):
    """[ERL+] Starts up an event headcount. Cannot be used in the Raiding section. Cannot be Shatters.

    Args:
        dungeon (str): The dungeon code you would like. To see a list of available event dungeons, use ^events.
    """
    #if ctx.guild.id != 850544046711111680: return
    
    if dungeon is not None and dungeon.lower() == 'shatters':
      await ctx.send("No.")
      return
    
    
    
    async def do_list_check():
      list_cont, n_d = await create_list(self.bot, ctx)
      if list_cont is False:
        return None
      else:
        return n_d
    
    if dungeon is None:
      d = await do_list_check()
      if d is None: return
      
    else:
      dungeon = dungeon.lower()
    
      dcheck_res, d = dungeon_checks(dungeon)
      if dcheck_res == DCHECK_INVALID:
        await ctx.send(f'{dungeon} is not a valid dungeon.')
        return
    
      if dcheck_res == DCHECK_LIST:
        d = await do_list_check()
        if d is None: return
    
    cont, section = await channel_checks(ctx)
      
    if cont:
      print(f"Continue with {dungeon}")
      if section.dungeon_allowed(dungeon):
        await self.headcount_main(ctx, d, section)
      else:
        await ctx.send(f"You cannot put up a headcount for `{dungeon if dungeon else d.name}` in this section.")

  @commands.command(name='hc')
  @commands.has_any_role(*get_raid_roles())
  async def raid_headcount(self, ctx: commands.Context, ignored=None):
    """[ARL+] Starts up a Shatters headcount. Cannot be used in the Events section. (Note: ViBot requires a `s` as an option for headcounts; it is optional here.)"""
    if ctx.guild.id != 850544046711111680: 
      await ctx.send('Leading Shatters is currently disabled. Soon (tm)')
      return
    
    cont, section = await channel_checks(ctx)
    
    if cont:   
      if section.dungeon_allowed(dungeons.SHATTERS_DNAME):
        await self.headcount_main(ctx, dungeons.get(dungeons.SHATTERS_DNAME), section)
      else:
        await ctx.send("You cannot put up a headcount for `shatters` in this section.")
    
  ######################
  ### AFK CHECKS
  ######################
  
  # This listener checks to see if a user has joined a lounge or drag channel.
  # If they have, it tells the relevant section's manager.
  @commands.Cog.listener()
  async def on_voice_state_update(self, member: discord.Member, before, after: discord.VoiceState):
    if after.channel is None or after.channel.id is None:
      return
    
    if before.channel == after.channel:
      if before.self_deaf is False and after.self_deaf:
        print(f"Deafen detected O_O: {member.display_name}")
      elif before.self_deaf and after.self_deaf is False:
        print(f"Undeafen detected :> {member.display_name}")
    
    else:
      for g_id in managers:
        for sect_name in managers[g_id]:
          manager = managers[g_id][sect_name]
          if after.channel.id == manager.section.lounge_ch or (manager.section.drag_chs and after.channel.id in manager.section.drag_chs):
            await manager.handle_voice_update(member)
   # if after.channel
    
    pass
  
  async def afk_main(self, ctx: commands.Context, dungeon: dungeons.Dungeon, raid_section: RaidingSection, lazy:bool=False, cap=None, location:str=None):
    # Step 1: Check which voice channel this will be in.
    voice_ch = await get_voice_ch(self.bot, ctx, raid_section)
    if voice_ch is None:
      return None
    
    if location is None:
      location = await ask_location(self.bot, ctx)
      if location is None:
        return None
    
    if cap is not None:
      if raid_section.allow_setcap:
        cap = max(raid_section.vc_min, min(raid_section.vc_max, cap))
        await voice_ch.edit(user_limit=cap)
    
    # Step 2: Get the status channel and make sure it's valid
    status_ch = ctx.guild.get_channel(raid_section.status_ch)
    if status_ch is None:
      await ctx.send("Erorr: Section status channel is None. Please contact an admin.")
      return None
    
    # Step 3: Tell the manager to start the AFK check.
    return await managers[ctx.guild.id][raid_section.name].try_create_afk(self.bot, ctx, status_ch, voice_ch, dungeon, lazy, location)
  
  @commands.command(name='eafk')
  @commands.has_any_role(*get_event_roles())
  async def event_afk(self, ctx: commands.Context, *args):
    """[ERL+] Starts up an Event AFK in the current voice channel the user is in, for the same section as the bot command channel.

    Usage:
        eafk [l|lazy] <dungeon> [cap] [location..]
        
        [l|lazy] means that, if you put an l or 'lazy' here, then the AFK check will be 'lazy'. A lazy AFK check is one where
        important reacts, such as keys, are moved into the channel first. Then, when the RL is ready, the channel is opened to the rest
        of the raiders. This is an optional argument, and if not given, the AFK check will be the standard "open immediately" type.
        
        <dungeon> is the code name of the dungeon to run. For a list of event dungeons, use `^events`.
        If no dungeon is provided, then a list will be provided - similar to ^events - and you can pick from there.
        However, if lazy was specified, then the command will instead fail if no dungeon is specified.
        
        [cap] is an optional argument that changes the maximum user cap for the voice channel, if allowed.
        The minimum and maximum of what the cap can be is different per section, and if the cap is outside of that range, it will be clamped.
        It must be a number.
        
        [location] is an optional argument that provides reacts with early location the location specified. If no location is specified, it will
        be set to "TBD". The location of your AFK check can be updated with the ^loc command after it's up.
    """
    #if ctx.guild.id != 850544046711111680:
    #  return
    cont, section = await channel_checks(ctx)
    
    if cont:
      if section.whitelist is not None:
        if len(section.whitelist) == 1:
          await ctx.send("This section has a whitelist with only one available dungeon. Use `^afk` instead.")
          return
      
      args_parsed = 0
      cap = None
      lazy = False
      loc = None
      
      async def do_list_check():
        l_cont, l_dung = await create_list(self.bot, ctx)
        if l_cont:
          d_code = l_dung.get_code()
          if d_code is None:
            await ctx.send("Error: `d_code` was None. Please contact an admin.")
            return False, None, None
          else:
            lazy = await confirmation(ctx, self.bot, "Would you like the AFK check to be lazy? (aka important drags first)")
            return lazy, d_code, l_dung
            
      
      if len(args) == 0 or args[0].lower() == 'list':        
        print("Doing list check.")
        lazy, d_code, dungeon = await do_list_check()
        if d_code is None:
          return
        
      else:
        print("No list check.")
        if args[0].lower() == 'l' or args[0].lower() == 'lazy':
          if len(args) == 1:
            await ctx.send("Not enough arguments given. Use `^help eafk` for usage info.")
            return
        
          if args[1].lower() == dungeons.SHATTERS_DNAME:
            await ctx.send("No.")
            return
        
          lazy = True
          dcheck_res, dungeon = dungeon_checks(args[1])
          args_parsed = 2
          
        else:
          if args[0].lower() == dungeons.SHATTERS_DNAME:
            await ctx.send("No.")
            return
          
          lazy = False
          dcheck_res, dungeon = dungeon_checks(args[0])
          args_parsed = 1
        
        if dcheck_res == DCHECK_INVALID:
          await ctx.send(f'`{args[args_parsed - 1]}` is an invalid dungeon or afk type. Use `^help eafk` for usage info.')
          return
      
        elif dcheck_res == DCHECK_LIST:
          lazy, d_code, dungeon = await do_list_check()
          if d_code is None:
            return
          
        else:
          d_code = dungeon.get_code()
          if d_code is None:
            await ctx.send("Error: `d_code` was None. Please contact an admin.")
            return
      
        if args_parsed < len(args):
          # We have more variables left, so the next one will be either the voice cap, or the beginning of the location.
          try:
            cap = int(args[args_parsed])
        
            args_parsed += 1
          except ValueError:
            # No cap. Remaining variables are location.
            pass
        
        if(args_parsed < len(args)):
          loc = ' '.join(args[args_parsed:]) 
      
      if section.dungeon_allowed(d_code) is False:
        await ctx.send(f'You cannot put up an AFK check for `{d_code}` in this section.')
        return
      
      await self.afk_main(ctx, dungeon, section, lazy, cap, loc)
      
  @commands.command(name='afk')
  @commands.has_any_role(*get_raid_roles())
  async def shatts_afk(self, ctx: commands.Context, *args):
    """[ARL+] Starts up an Shatters AFK in the current voice channel the user is in, for the same section as the bot command channel.

    Usage:
        afk [s/z/l|lazy] [cap] [location..]
        
        If an 's' is put as the first argument, it is ignored. It's allowed to keep in style with ViBot's AFK command.
        All arguments, including this one, are optional.
        
        [z/l|lazy] means that, if you put an z, l or 'lazy' here, then the AFK check will be 'lazy'. A lazy AFK check is one where
        important reacts, such as keys, are moved into the channel first. Then, when the RL is ready, the channel is opened to the rest
        of the raiders. This is an optional argument, and if not given, the AFK check will be the standard "open immediately" type.
        
        [cap] is an optional argument that changes the maximum user cap for the voice channel, if allowed.
        The minimum and maximum of what the cap can be is different per section, and if the cap is outside of that range, it will be clamped.
        It must be a number.
        
        [location] is an optional argument that provides reacts with early location the location specified. If no location is specified, it will
        be set to "TBD". The location of your AFK check can be updated with the ^loc command after it's up.
    """
    if ctx.guild.id != 850544046711111680: 
      await ctx.send('Leading Shatters is currently disabled. Soon (tm)')
      return
    
    cont, section = await channel_checks(ctx)
    
    if cont:
      if section.dungeon_allowed(dungeons.SHATTERS_DNAME) is False:
        await ctx.send("You cannot make a Shatters AFK check in this section.")
        return
      
      dungeon = dungeons.get(dungeons.SHATTERS_DNAME)
      assert dungeon
      
      lazy = False
      loc = None
      cap = None
      if len(args) > 0:
        args_parsed = 0
        if args[0].lower() == 'z' or args[0].lower() == 'l' or args[0].lower == 'lazy':
          lazy = True
          args_parsed += 1
        elif args[0].lower() == 's':
          args_parsed += 1
          
        if args_parsed < len(args):
          try:
            cap = int(args[args_parsed])        
            args_parsed += 1          
          except ValueError:
            pass
        
          if args_parsed < len(args):
            loc = ' '.join(args[args_parsed:])

      await self.afk_main(ctx, dungeon, section, lazy, cap, loc)
  
  @commands.command(name='transfer')
  @commands.has_any_role(*get_event_roles())
  async def transfer_afk(self, ctx:commands.Context, transferTo=None):
    """[ERL+] Request to transfer an AFK check to someone else. They must be allowed to put up AFK checks in the section.
    
    Args:
        transferTo (@mention): The person to transfer to. This needs to be a ping.
    """
    cont: bool = None
    section: RaidingSection = None
    cont, section = await channel_checks(ctx)
    if cont:
      if ctx.author.id not in managers[ctx.guild.id][section.name].active_afks:
        await ctx.send("You do not have an active AFK check!")
        return
      if transferTo is None or len(transferTo) < 18:
        await ctx.send("You must ping whoever you are trying to transfer to.")
      else:
        try:
          userid = int(transferTo[3:-1])
          dest_user = ctx.guild.get_member(userid)
          if dest_user is None or dest_user.id == ctx.author.id or dest_user.bot:
            if dest_user.id == self.bot.user.id:
              await ctx.send("Lol no 😂")
            else:
              await ctx.send("Invalid user.")
          else:
            if section.role_check(dest_user.roles):
              do_transf = await confirmation(ctx, self.bot, f'Do you accept the transfer from {ctx.author.mention}?', auth_override=dest_user, timeout=20)
              if do_transf:
                result = await managers[ctx.guild.id][section.name].transfer_afk(ctx.author, dest_user)
                if result:
                  await ctx.send(f"AFK check transferred to {dest_user.mention}")
                else:
                  await ctx.send(f'AFK transfer failed. :(')
              pass
            else:
              await ctx.send(embed=discord.Embed(description=f"{dest_user.mention} is not allowed to be a transfer target in this raiding section."))
            pass
        
        except ValueError:
          await ctx.send("You must ping whoever you are trying to transfer to.")