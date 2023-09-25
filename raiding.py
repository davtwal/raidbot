import discord
from discord.ext import commands

from typing import List, Dict, Optional, Tuple
import asyncio
import re

from globalvars import RaidingSection, get_staff_roles, get_event_roles, get_raid_roles, confirmation, get_manager_roles, get_veteran_roles

import dungeons
from hc_afk_helpers import can_lead_hardmode, channel_checks, create_list, dungeon_checks, get_voice_ch, ask_location
from hc_afk_helpers import DCHECK_LIST, DCHECK_INVALID
from shattersbot import ShattersBot

DEAFEN_WARNING_MESSAGE = """I've detected that you've deafened inside of one of {}'s raiding channels while not being allowed to.
**You have {} seconds to undeafen, or you may be suspended.** Please undeafen immediately.
"""

DEAFEN_SUSPWARN_MESSAGE = """It's been {} seconds since you were warned to undeafen. The raid leader has been notified.
If you are suspended and would like to contest the suspension, please message {}#{} or any security+."""

DEAFEN_CAN_SUSP_WARNED = """They were messaged and warned, but still did not undeafen"""
DEAFEN_CAN_SUSP_COULDNTWARN = """I tried to warn them through DMs, but I was unable to"""

DEAFEN_CAN_SUSP_MESSAGE = """{}: {} was detected to be deafened in your run. {}.
If able, you (or any other RL/Security) can suspend them for up to 6 hours using the below command:

`;suspend {} 6 hours You were detected as deafened in one of my runs while not being allowed to. If you think this is a mistake, please message me or a security.`

If you think this is a mistake or a non-issue, you can ignore this message (or `;warn` them instead).
If you do not have suspension permissions, you can ping anyone who does to have them take care of this."""

DEAFEN_THANK_UNDEAFEN = """Thank you for undeafening. Enjoy the raid!"""


class RaidingCmds(commands.Cog, name='Raiding Commands'):
  def __init__(self, bot: ShattersBot):
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

    if self.bot.pending_shutdown:
      await ctx.send("A shutdown is pending. Please wait until the bot restarts. Sorry for the inconvenience!")
      return

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

    await bot.managers[ctx.guild.id][raid_section.name].try_create_headcount(bot, ctx, statuschannel, d)

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
      if section.dungeon_allowed(dungeon):
        await self.headcount_main(ctx, d, section)
      else:
        await ctx.send(f"You cannot put up a headcount for `{dungeon if dungeon else d.name}` in this section.")

  @commands.command(name='hc')
  @commands.has_any_role(*get_raid_roles())
  async def raid_headcount(self, ctx: commands.Context, hm:str=None):
    """[ARL+] Starts up a headcount. Cannot be used in the Events section.
    Optionally, you can add an "h" or "hm" to the end of the command (e.g. "^hc h") to make a hardmode headcount.
    Optionally, you can add an "m" or "mv" to make this a moonlight village headcount.
    Any other type will be ignored.
    """
    #if ctx.author.id != 170752798189682689: 
    #  await ctx.send('Leading Shatters is currently disabled. Soon (tm)')
    #  return

    cont, section = await channel_checks(ctx)

    dungeon = dungeons.SHATTERS_DNAME
    if hm:
      if hm.lower()[0] == 'h':
        if can_lead_hardmode(ctx):
          dungeon = dungeons.HARDSHATTS_DNAME
        else:
          await ctx.send("You cannot put up a hard mode headcount.")
          return
        
      elif hm.lower()[0] == 'm':
        dungeon = dungeons.MVILLAGE_DNAME

    if cont:   
      if section.dungeon_allowed(dungeon):
        await self.headcount_main(ctx, dungeons.get(dungeon), section)
      else:
        await ctx.send(f"You cannot put up a headcount for `{dungeon}` in this section.")
    
  ######################
  ### AFK CHECKS
  ######################

  deafen_list: Dict[int, asyncio.Task] = {} # deafened user's id: task
  async def check_deafen(self, member: discord.Member, afk_owner: discord.Member):
    print(f'[DEAFCHECK]: Deafen detected by {member.display_name}; afk owner {afk_owner.display_name}')
    warntime = self.bot.get_deafcheck_warntime(member.guild.id)
    susptime = self.bot.get_deafcheck_sustime(member.guild.id)
    susproof_ch = member.guild.get_channel(self.bot.get_susproof_channel(member.guild.id))

    if afk_owner.id in self.bot.get_deafcheck_optout_list(afk_owner.guild.id):
      # we don't care if the owner doesn't care.
      return

    if susproof_ch is None or susproof_ch.type != discord.ChannelType.text:
      print(f'[DEAFCHECK]: No suspension proof channel found, or suspension proof channel is not a text channel.')
      return

    await asyncio.sleep(warntime)
    warnedmsg = DEAFEN_CAN_SUSP_WARNED

    print(f'[DEAFCHECK] {member.display_name}: Made it past warn time ({warntime}s). Warning...')
    try:
      await member.send(DEAFEN_WARNING_MESSAGE.format(member.guild.name, susptime))
      print(f'[DEAFCHECK] {member.display_name}: Warned successfully. Waiting for suspension time...')
      await asyncio.sleep(susptime)

      print(f'[DEAFCHECK] {member.display_name}: Suspension time has passed. Sending suspension warning and suspension ping...')
      try:
        await member.send(DEAFEN_SUSPWARN_MESSAGE.format(susptime, afk_owner.name, afk_owner.discriminator))

      except:
        print(f'[DEAFCHECK] {member.display_name}: DM suspension warning failed.')

    except asyncio.CancelledError:
      print(f'[DEAFCHECK] {member.display_name}: Task cancelled. Thanking for undeafening and exiting.')
      try:
        await member.send(DEAFEN_THANK_UNDEAFEN)
      except: pass
      return

    except:
      print(f'[DEAFCHECK] {member.display_name}: Warning message failed. Sending suspension message...')
      warnedmsg = DEAFEN_CAN_SUSP_COULDNTWARN

    try:
      await susproof_ch.send(DEAFEN_CAN_SUSP_MESSAGE.format(afk_owner.mention, member.mention, warnedmsg, re.search('[a-zA-Z]+', member.display_name)[0]))
      print(f'[DEAFCHECK] {member.display_name}: Suspension proof message sent.')
    except:
      print(f'[DEAFCHECK] {member.display_name}: Failed to send message in suspension proof :(')

    del self.deafen_list[member.id]

  # This listener checks to see if a user has joined a lounge or drag channel.
  # If they have, it tells the relevant section's manager.
  @commands.Cog.listener()
  async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if after.channel is None or after.channel.id is None:
      return
    
    for g_id in self.bot.managers:
      for sect_name in self.bot.managers[g_id]:
        manager = self.bot.managers[g_id][sect_name]
        sect = manager.section

        if (before.channel and before.channel.id == after.channel.id or after.self_deaf) and after.channel.id in manager.section.voice_chs:
          #print('|| Statechange detected in a raiding channel.')
          if sect.deafcheck and (before.channel is None or before.self_deaf != after.self_deaf):
            #print('|| Deafen or undeafen, and deafcheck.')

            for role in get_staff_roles():
              if role in [r.name for r in member.roles]:
                return # We don't care about staff who are deafened (for now)

            if sect.deafcheck_vet or self.bot.get_vetraider_role(member.guild.id) not in [r.id for r in member.roles]:
              #print('|| Either not veteran or veterans are also checked.')
              if after.self_deaf:
                #print('|| Is now deafened.')
                owner_id = manager.has_relevant_afk(before.channel.id)
                if owner_id:
                  owner = manager.guild.get_member(owner_id)
                  if owner:
                    #print(f'|| Relevant AFK found with owner {owner.display_name}')
                    self.deafen_list[member.id] = asyncio.create_task(self.check_deafen(member, owner))
              else:
                #print('|| Is now undeafened.')
                if member.id in self.deafen_list:
                  #print('|| Task found and cancelled.')
                  self.deafen_list[member.id].cancel()
                  del self.deafen_list[member.id]
                else:
                  pass #print('|| No task to cancel.')

        elif after.channel.id == sect.lounge_ch or (sect.drag_chs and after.channel.id in sect.drag_chs):
          await manager.handle_lounge_join(member)
    
    pass
  
  async def afk_main(self, ctx: commands.Context, dungeon: dungeons.Dungeon, raid_section: RaidingSection, lazy:bool=False, cap=None, location:str=None):
    # Step 1: Check which voice channel this will be in.
    if self.bot.pending_shutdown:
      await ctx.send("A shutdown is pending. Please wait until the bot restarts. Sorry for the inconvenience!")
      return

    if dungeon is None:
      await ctx.send("Internal Error: `dungeon` was None. Please report to the developer.")
      return
    
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
    
    print('made it 2')
    # Step 3: Tell the manager to start the AFK check.
    return await self.bot.managers[ctx.guild.id][raid_section.name].try_create_afk(self.bot, ctx, status_ch, voice_ch, dungeon, lazy, location)
  
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
        afk [type] [cap] [location..]
        
        If an 's' is put as the first argument, it is ignored. It's allowed to keep in style with ViBot's AFK command.
        All arguments, including this one, are optional.
        
        [type] asks for the type of Shatters AFK this is. If not specified, it does a normal Shatters AFK check.
        Type list:
          - s        : Normal shatters. Though this is here for compatibility with ViBot, it's good practice to use it.
          - z/l/lazy : Lazy AFK check normal shatters.
          - h/hm     : Hard mode shatters. You must be a VRL+ to do hard mode.
          - hz/hl    : Hard mode, but with a lazy AFK check. You must be a VRL+ to do hard mode.
          - mv       : Moonlight Village
          - ml       : Moonlight Village (Lazy)
        
        A lazy AFK check is one where important reacts, such as keys, are moved into the channel first. Then, when the RL is ready,
        the channel is opened to the rest of the raiders.
        
        [cap] is an optional argument that changes the maximum user cap for the voice channel, if allowed.
        The minimum and maximum of what the cap can be is different per section, and if the cap is outside of that range, it will be clamped.
        It must be a number.
        
        [location] is an optional argument that provides reacts with early location the location specified. If no location is specified, it will
        be set to "TBD". The location of your AFK check can be updated with the ^loc command after it's up.
    """    
    cont, section = await channel_checks(ctx)
    
    if cont:
      self.bot.log(f"AFK command {ctx.author.display_name}: ^afk {' '.join(args)}")
      lazy = False
      loc = "Not Set"
      cap = None
      dungeon = dungeons.SHATTERS_DNAME

      if len(args) > 0:
        args_parsed = 0

        typeclause = args[0].lower()
        if len(typeclause) < 1:
          await ctx.send("Invalid type detected. Please use an valid option.")
          return

        if typeclause[0] == 'h': #Only check for the first character to be h
          if can_lead_hardmode(ctx):
            dungeon = dungeons.HARDSHATTS_DNAME
          else:
            await ctx.send("You cannot put up hard mode AFK checks.")
            return

          if len(typeclause) > 1 and (typeclause[1] == 'z' or typeclause[1] == 'l'):
            lazy = True

          args_parsed += 1

        elif typeclause[0] == 'm':
          dungeon = dungeons.MVILLAGE_DNAME

          if len(typeclause) > 1 and (typeclause[1] == 'l'):
            lazy = True
          
          args_parsed += 1

        else:
          dungeon = dungeons.SHATTERS_DNAME

          if typeclause[0] in ['z', 'l']:
            lazy = True

          args_parsed += 1
        
        ## 2: Check for cap and location
        if args_parsed < len(args):
          try:
            cap = int(args[args_parsed])        
            args_parsed += 1          
          except ValueError:
            pass
        
          if args_parsed < len(args):
            loc = ' '.join(args[args_parsed:])

      dungeon = dungeons.get(dungeon)

      print('made it')
      if section.dungeon_allowed(dungeon.code) is False:
        await ctx.send(f"You cannot make a {dungeon.name} AFK check in this section.")
        return

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
      if ctx.author.id not in self.bot.managers[ctx.guild.id][section.name].active_afks:
        await ctx.send("You do not have an active AFK check!")
        return
      if transferTo is None or len(transferTo) < 18:
        await ctx.send("You must ping whoever you are trying to transfer to.")
      else:
        try:
          userid = int(transferTo[3:-1])
          dest_user = ctx.guild.get_member(userid)
          if dest_user is None or dest_user.id == ctx.author.id or dest_user.bot:
            if dest_user is not None and dest_user.id == self.bot.user.id:
              await ctx.send("Lol no 😂")
            else:
              await ctx.send("Invalid user.")
          else:
            if section.role_check(dest_user.roles):
              do_transf = await confirmation(ctx, self.bot, f'Do you accept the transfer from {ctx.author.mention}?', auth_override=dest_user, timeout=20)
              if do_transf:
                result = await self.bot.managers[ctx.guild.id][section.name].transfer_afk(ctx.author, dest_user)
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

  ######################
  ### OTHER COMMANDS
  ######################

  #@commands.command('poll')
  #@commands.has_any_role(*get_event_roles())
  async def cmd_poll(self, ctx: commands.Context, polltype=None, *check_text):
    """
    [ERL+] Puts up a poll of a specific type. Use ^help poll to see options.

    Types:
      hm: Hard mode if void phantasm is found. Poll options: (Play) Reset for v/alch. (Check) Do HM if v/alch, but finish the run if not found. (X) Don't do hard mode.
      us/eu: US or EU.
      region: US, EU, or Asia/Australia.
      check <text>: Asks if something is OK.

    Examples:
      ^poll hm
      ^poll check Do weak boss key?
    """