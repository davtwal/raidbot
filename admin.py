import discord
from discord import Guild
from discord.ext import commands

from tracking import close_connections
from globalvars import REACT_CHECK, REACT_X, confirmation, get_admin_roles, ROLES, get_event_roles, get_helper_roles, get_manager_roles, get_raid_roles, get_security_roles, get_vetcontrol_roles, get_veteran_roles
import shattersbot as sb
import dungeons

# Actual cog
import asyncio

class AdminCmds(commands.Cog, name="Admin Commands"):
  def __init__(self, bot: sb.ShattersBot):
    self.bot = bot
  
  @commands.command(name='debug')
  @commands.has_any_role(*get_admin_roles())
  async def debugset(self, ctx: commands.Context, setting=None):
    """[Admin+] Enable or disable debug mode.

    Args:
        setting (str): 'enable' or 'disable'.
    """
    
    if setting == 'enable':
      if self.bot.is_debug() == False:
        self.bot.debugmode = True
        await ctx.send("Debug mode enabled.")
      else:
        await ctx.send("Debug mode is already enabled.")
      
    elif setting == 'disable':
      if self.bot.is_debug() == True:
        self.bot.debugmode = False
        await ctx.send("Disabled debug mode.")
      else:
        await ctx.send("Debug mode is already disabled.")     
    
  
  @commands.command(name='view')
  @commands.has_any_role(*get_admin_roles())
  async def view(self, ctx: commands.Context, mainarg=None):
    """[Admin+] View internal parts of the bot.

    Args:
        mainarg ([str]): What to view. Can be: roles, staffroles, sections, section_<sectionname>, hcs, or afks.
    """
    if mainarg is None:
      await ctx.send("What to view. Can be: roles, staffroles, sections, section_<sectionname>, hcs, or afks.")
      return

    if mainarg == 'staffroles':
      await ctx.send(str(ROLES))

    elif mainarg == 'roles':
      embed = discord.Embed()

      indiv_role_desc = ""
      for role in sb.GDICT_INDIV_ROLES:
        indiv_role_desc += f"`{role}`: {self.bot.gdict[ctx.guild.id][role]}\n"
      
      indiv_role_desc += f"`early`: {self.bot.get_early_roles(ctx.guild.id)}\n"

      embed.add_field(name='Individual Roles', value=indiv_role_desc)

      dungeon_pingroles_desc = ""
      for dungeon in self.bot.get_dungeon_ping_role_list(ctx.guild.id):
        role = self.bot.get_dungeon_ping_role(ctx.guild.id, dungeon)
        dungeon_pingroles_desc += f"`{dungeon}`: {role.mention if role else 'None'}"
        
      embed.add_field(name="Dungeon Ping Roles", value=dungeon_pingroles_desc)

      embed.add_field(name="Staff Roles", value=f"""
                  T0: {get_admin_roles()}
                  T1: {get_manager_roles()}
                  T2a: {get_veteran_roles()}
                  T2b: {get_raid_roles()}
                  T2c: {get_event_roles()}
                  T3a: {get_helper_roles()}
                  T3b: {get_vetcontrol_roles()}
                  T3c: {get_security_roles()}
                  """)
      
      await ctx.send(embed=embed)
    
    elif mainarg == 'sections':
      await ctx.send(f'```{self.bot.gdict[ctx.guild.id][sb.GDICT_SECTIONS].keys()}```')
      
    elif mainarg == 'hcs':
      mngrs = self.bot.managers
      await ctx.send(f'{[mngrs[ctx.guild.id][sect].active_hcs for sect in mngrs[ctx.guild.id]]}')
    
    elif mainarg == 'afks':
      mngrs = self.bot.managers
      await ctx.send(f'{[mngrs[ctx.guild.id][sect].active_afks for sect in mngrs[ctx.guild.id]]}')
    
    elif mainarg and len(mainarg) > 8 and mainarg[:8] == 'section_':
      await ctx.send(f'```{self.bot.gdict[ctx.guild.id][sb.GDICT_SECTIONS][mainarg[8:]]}```')

    else:
      await ctx.send("Invalid view option given.")
    
    pass
  
  async def _setup_roles(self, ctx, gid, *args) -> bool:
    if len(args) < 2:
      await ctx.send('Invalid number of arguments passed.')
      return False
    
    if args[0] == 'early':
      try:
        if args[1] == 'add':
          for rolestr in args[2:]:
            roleid = int(rolestr)
            if rolestr not in self.bot.gdict[gid][sb.GDICT_EARLY_ROLES]:
              self.bot.gdict[gid][sb.GDICT_EARLY_ROLES].append(roleid)
              await ctx.send(f"{roleid} added to early roles.")
              return True
              
        if args[1] == 'remove':
          for rolestr in args[2:]:
            roleid = int(rolestr)
            if rolestr in self.bot.gdict[gid][sb.GDICT_EARLY_ROLES]:
              self.bot.gdict[gid][sb.GDICT_EARLY_ROLES].remove(roleid)
              await ctx.send(f"{roleid} removed from early roles.")
              return True
        
        if args[1] == 'set':
          roleids = [int(rolestr) for rolestr in args[2:]]
          self.bot.gdict[gid][sb.GDICT_EARLY_ROLES] = roleids
          await ctx.send(f"Early role IDs set to {roleids}")
          return True
          
        await ctx.send("Invalid add|remove|set given.")
        return False
      
      except ValueError:
        await ctx.send("Argument must be an integer.")
        return False
    # endif args[0] == 'early'
      
    elif args[0] in sb.GDICT_INDIV_ROLES:
      return await self._setup_role(ctx, gid, args[0], args[1])
    else:
      await ctx.send(f"Invalid role. Role must be one of `{sb.GDICT_INDIV_ROLES}`.")
      return False

  async def _setup_role(self, ctx, gid, rolename, roleid) -> bool:
    try:
      self.bot.gdict[gid][rolename] = int(roleid)
      await ctx.send(f"Role ID for `{rolename}` set to `{roleid}`")
      return True
    
    except ValueError:
      await ctx.send("Argument must be an integer.")
      return False

  async def _setup_channel(self, ctx, gid, chname, chid) -> bool:
    try:
      ch: discord.TextChannel = ctx.guild.get_channel(int(chid))
    except:
      await ctx.send('Argument must be an integer.')
      return False
    
    if not ch or ch.type != discord.ChannelType.text:
      await ctx.send(f'Channel ID `{chid}` not found, or is not a text channel.')
      return False
    
    await ctx.send(f'Run info channel set to {ch.mention}.')
    self.bot.gdict[gid][sb.GDICT_RUNINFO_CH] = ch.id
    return True

  @commands.command(name='setup')
  @commands.has_any_role(*get_admin_roles())
  async def setup(self, ctx: commands.Context, mainarg=None, *args):
    f"""[Admin+] Setup command.

    Args:
        mainarg (str): Which setup command to use.
        
    Setup Commands:
        setup debug <enabled|disabled>
          Enables or disables debug mode.
    
        setup role <role name> role_id
          Sets whatever role to the role id given. Roles are {sb.GDICT_INDIV_ROLES}.
            
        setup role early <add|remove|set> role_ids...
          Sets, adds, or removes from the early roles.
          Early roles will automatically get moved into the voice channel and given location
          as soon as they click the Join button.

        setup dungeonping <dungeonname> <role ID>
          Sets the ping role for a specific dungeon.
        
        setup <channel> <channel_id>
          Sets the channel ID for a given channel.
          Channels are {sb.GDICT_CHANNELS}.

        setup deafcheck <warntime|susptime> <time>
          Sets the warning or suspension time for a detected deafen. Time is in seconds.
            After the warntime, the user will be messaged by the bot asking them to undeafen.
            Then, after susptime has passed, the owner of the previous AFK will be messaged in suspension proof.

        setup afkrelevancy <time>
          Sets the time an AFK check is considered 'relevant' to <time>. Time is in seconds.
          Note that only one AFK check can be considered 'relevant' for each voice channel at a time.

        setup section add|remove name
          Adds or removes a section.
        
        setup dungeonping <dungeon code> <role ID>
          Sets the role ping for a specific dungeon code.

        setup section <name> <part> (arguments...)
          Sets a different part of the given section to something.
          I'm too lazy to add the checking for this command that will almost never be used,
          so this command literally just slaps whatever you give it into it, with some exceptions.
          If you aren't confident in using this command, just ask a dev.
          Available parts:
            cmd_ch: [int] The command channel. Should be a text channel's ID.
            status_ch: [int] Status AFK checks. Text channel ID.
            min_role_tier: [int] The minimum 'role tier' required to do afks in this section.
            lounge_ch: [int] Lounge voice channel ID.
            is_vet: [True|False] If the channel is considered 'veteran' (e.g. it changes vet raider perms instead of raider perms)
            allow_setcap: [True|False] If RLs can use ^setcap on raiding channels here.
            allow_unlock: [True|False] if RLs can use ^lock and ^unlock on these raiding channels.
            vc_min: [int] Minimum voice cap for the section.
            vc_max: [int] Maximum voice cap for the section.
            deafcheck: [True|False] If deafen checking is enabled for this section.
            deafcheck_vet: [True|False] If veteran raiders are also checked for deafening.
            
            whitelist: List[str] Adds/removes/sets dungeon whitelist for the section.
            blacklist: List[str] Adds/removes/sets dungeon blacklist.
            Note: You cannot have a whitelist and a blacklist in a section at the same time.
            Use ^dungeons for a list of codes.
            
            voice_chs: List[int]
            drag_chs: List[int]
            HOW VOICES WORK:
            - Voice channels have a list. So do drag channels.
            - There can only ever be NO drag channels, OR one for each voice channel.
            - When setting drag channels, you must give IDs equal to the number of voice channels listed.
            - When removing a voice channel, its drag channel will also be removed.
            - You cannot remove drag channels individually; they are all or nothing.
            
            Also, all those rules are made up and the command just does whatever it wants.
    """
    if mainarg is None:
      await ctx.send("No arguments passed.\nPossible arguments: `debug, role, section`")
      pass
    
    gid = ctx.guild.id

    if mainarg == 'debug':
      await ctx.send("Use `^debug` instead.")
      return

    elif mainarg == 'role':
      if await self._setup_roles(ctx, gid, *args):
        self.bot.save_db()

    elif mainarg == 'dungeonping':
      if len(args) < 2:
        await ctx.send("Invalid amount of arguments")
        return
      
      try:
        role = ctx.guild.get_role(int(args[1]))
      except ValueError:
        await ctx.send("Role ID must be an integer.")
        return
      
      if role is None:
        await ctx.send(f"Role with ID `{args[1]}` not found.")
        return

      for dlist in dungeons.dungeonlist:
        if args[0] in dungeons.dungeonlist[dlist]:
          self.bot.gdict[gid][sb.GDICT_DUNGEON_PING_ROLE][args[0]] = int(args[1])
          await ctx.send(embed=discord.Embed(description=f"Role ping for {dungeons.dungeonlist[dlist][args[0]].name} set to {role.mention}"))
          self.bot.save_db()
          break

    elif mainarg in sb.GDICT_CHANNELS:
      if len(args) < 1:
        await ctx.send('Invalid amount of arguments.')
        return

      if self._setup_channel(ctx, gid, mainarg, args[0]):
        self.bot.save_db()

    elif mainarg == 'deafcheck':
      if len(args < 2):
        await ctx.send('Invalid amount of arguments.')
        return

      try:
        time = int(args[1])
      except:
        await ctx.send('Time must be an integer.')
        return

      if args[0] == 'warntime':
        self.bot.gdict[gid][sb.GDICT_DEAFCHECK_WARNTIME] = time
        await ctx.send(f'Deafen check warn time set to {time}.')

      elif args[0] == 'susptime':
        self.bot.gdict[gid][sb.GDICT_DEAFCHECK_SUSTIME] = time
        await ctx.send(f'Deafen check suspension time set to {time}.')

      self.bot.save_db()

    elif mainarg == 'afkrelevancy':
      try:
        time = int(args[0])
        if time < 60:
          await ctx.send('AFK relevancy time must be > 60 seconds.')
          return

        self.bot.gdict[gid][sb.GDICT_AFK_RELEVANTTIME] = time
        await ctx.send(f'AFK Relevancy time set to {time}.')
        self.bot.save_json(sb.SHATTERS_JSON_TXT)
      except:
        await ctx.send("Invalid arguments given.")
        return

    elif mainarg == 'section':
      if len(args) < 2:
        await ctx.send('invalid amount of arguments')
        return
      
      # oh god oh fuck
      if args[0] == 'add':
        self.bot.gdict[gid][sb.GDICT_SECTIONS][args[1]] = sb.DEFAULT_GUILD_DICT[sb.GDICT_SECTIONS]
        pass
      
      elif args[0] == 'remove':
        self.bot.gdict[gid][sb.GDICT_SECTIONS].pop(args[1])
        pass
      
      elif args[0] in self.bot.gdict[gid][sb.GDICT_SECTIONS]:
        if len(args) > 3:
          abc = [None if a == 'None' else a for a in args]
          if args[1] in ['voice_chs', 'drag_chs']:
            self.bot.gdict[gid][sb.GDICT_SECTIONS][args[0]][args[1]] = [int(a) for a in args[2:]]
          elif args[1] in ['whitelist', 'blacklist']:
            #await ctx.send(f'gid {gid} sect {args[0]} type {args[1]} cur {self.bot.gdict[gid][sb.GDICT_SECTIONS][args[0]][args[1]]} new {abc[2:]}')
            self.bot.gdict[gid][sb.GDICT_SECTIONS][args[0]][args[1]] = abc[2:]
            #await ctx.send(f'Section {args[0]}[{args[1]}] set to {self.bot.gdict[gid][sb.GDICT_SECTIONS][args[0]][args[1]]}')
          else:
            #await ctx.send(f'b')
            self.bot.gdict[gid][sb.GDICT_SECTIONS][args[0]][args[1]] = abc[2:]

        else:
          #await ctx.send(f'c')
          if args[2] == 'None':
            self.bot.gdict[gid][sb.GDICT_SECTIONS][args[0]][args[1]] = None
          elif args[1] in ['voice_chs', 'drag_chs']:
            self.bot.gdict[gid][sb.GDICT_SECTIONS][args[0]][args[1]] = int(args[2])
          else:
            #await ctx.send(f'e')
            self.bot.gdict[gid][sb.GDICT_SECTIONS][args[0]][args[1]] = args[2]
        #await ctx.send(f'd')
        pass
        #await ctx.send(f'e')
        await ctx.send(f'Section {args[0]}[{args[1]}] set to {self.bot.gdict[gid][sb.GDICT_SECTIONS][args[0]][args[1]]}')
      
      else:
        await ctx.send(f'Invalid section name `{args[0]}`. Section names are {self.bot.gdict[gid][sb.GDICT_SECTIONS].keys()}')
        
      self.bot.save_db()
      pass
    
    else:
      await ctx.send(f'Invalid operation. Options are `debug, role, deafcheck, {sb.GDICT_CHANNELS}, afkrelevancy, dungeonping, section`.')
    pass
  
  async def do_exit(self):
    self.bot.log('Restart command executed.')
    self.bot.close_connections()
    self.bot.save_db()
    exit(0)

  @commands.command('restart')
  @commands.has_any_role(*get_admin_roles())
  async def cmd_restart(self, ctx: commands.Context, force=None):
    """[Admin+] Restarts the bot, cancelling any active HCs. Can wait for AFK checks to finish though."""
    # This prevents any new AFKs/HCs from being put up
    self.bot.pending_shutdown = True

    if force == 'force':
      await ctx.message.add_reaction(REACT_CHECK)
      await self.do_exit()

    found_hcs = []
    found_afks = []
    for gid in self.bot.managers:
      for sectname in self.bot.managers[gid]:
        sect = self.bot.managers[gid][sectname]
        if len(sect.active_hcs) > 0:
          found_hcs.append((gid, sectname))
        if len(sect.active_afks) > 0:
          found_afks.append((gid, sectname))

    if len(found_hcs) > 0:
      embed = discord.Embed(title="Active Headcounts Found")
      embed.description = "A few active headcounts were found."
      val = ""
      for gid, sectname in found_hcs:
        sect = self.bot.managers[gid][sectname]
        for owner_id in sect.active_hcs:
          hc = sect.active_hcs[owner_id]
          owner: discord.Member = ctx.guild.get_member(owner_id)
          val += f"{hc.status_ch.mention}: {owner.mention}\n"

      embed.add_field(name="Headcounts", value=val)
      msg = await ctx.send(embed=embed)
      if not await confirmation(ctx, self.bot, "Would you like to continue anyway? The headcounts will be cancelled."):
        self.bot.pending_shutdown = False
        await msg.delete()
        await ctx.message.add_reaction(REACT_X)
        return

      else:
        for gid, sectname in found_hcs:
          sect = self.bot.managers[gid][sectname]
          owners = list(sect.active_hcs.keys()) # This copies the keys and lets us do .abandon()
          for owner_id in owners:
            owner: discord.Member = ctx.guild.get_member(owner_id)
            hc = sect.active_hcs[owner_id]
            await hc.abandon()
            await hc.status_ch.send("Sadly ShattsBot (me) needs to restart for maintenance, so this headcount has been cancelled. Please wait for the next headcount.\nSorry for the inconvenience!")
            await hc.ctx.send(f"{owner.mention}, the bot is restarting soon so your headcount has been cancelled.\nSorry for the inconvenience! You can put up another headcount after the bot is back up.")

      await msg.delete()

    if len(found_afks) > 0:
      embed = discord.Embed(title="Active AFK Checks Found")
      embed.description = "A few active AFK checks were found."
      val = ""
      for gid, sectname in found_afks:
        sect = self.bot.managers[gid][sectname]
        for owner_id in sect.active_afks:
          afk_check = sect.active_afks[owner_id]
          owner: discord.Member = ctx.guild.get_member(owner_id)
          val += f"{afk_check.status_ch.mention}: {owner.mention}\n"

      embed.add_field(name="Active AFK Checks", value=val)

      msg = await ctx.send(embed=embed)
      if await confirmation(ctx, self.bot, "Would you like to wait until the AFK checks are over?", checktext="The bot will check every 30 seconds to see if all AFKs are closed."):
        cont = True
        while cont:
          for gid, sectname in found_afks:
            if len(self.bot.managers[gid][sectname].active_afks) > 0:
              await asyncio.sleep(30)
            else:
              await ctx.send(f"{ctx.author.mention}, the bot is now restarting.")
              cont = False
              break
      
      else:
        for gid, sectname in found_afks:
          sect = self.bot.managers[gid][sectname]
          owners = list(sect.active_afks.keys()) # This copies the keys and lets us do .close()
          for owner_id in owners:
            owner: discord.Member = ctx.guild.get_member(owner_id)
            afk_check = sect.active_afks[owner_id]
            await afk_check.close()
            await afk_check.ctx.send(f"{owner.mention}, your AFK check was automatically closed as the bot needs to restart. Sorry for any inconvenience!")
      
      await msg.delete()
    
    await ctx.message.add_reaction(REACT_CHECK)
    await self.do_exit()
  pass