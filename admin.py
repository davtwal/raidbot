import globalvars as g
from globalvars import find_channel

import discord
from discord import Guild
from discord.ext import commands
from raiding import get_managers

from tracking import close_connections

# Actual cog

class AdminCmds(commands.Cog):
  def __init__(self, bot: commands.Bot):
    self.bot = bot
  
  @commands.command(name='debug')
  @commands.has_any_role(*g.get_admin_roles())
  async def debugset(self, ctx: commands.Context, setting=None):
    """[Admin+] Enable or disable debug mode.

    Args:
        setting (str): 'enable' or 'disable'.
    """
    
    if setting == 'enable':
      if g.bot_debugmode == False:
        g.bot_debugmode = True
        await ctx.send("Debug mode enabled.")
      else:
        await ctx.send("Debug mode is already enabled.")
      
    elif setting == 'disable':
      if g.bot_debugmode == True:
        g.bot_debugmode = False
        await ctx.send("Disabled debug mode.")
      else:
        await ctx.send("Debug mode is already disabled.")     
    
  
  @commands.command(name='view')
  @commands.has_any_role(*g.get_admin_roles())
  async def view(self, ctx: commands.Context, mainarg=None):
    """[Admin+] View internal parts of the bot.

    Args:
        mainarg ([str]): What to view. Can be: roles, staffroles, sections, section_<sectionname>, hcs, or afks
    """
    if mainarg is None:
      await ctx.send("moron")
      return

    if mainarg == 'staffroles':
      await ctx.send(str(g.ROLES))

    elif mainarg == 'roles':
      await ctx.send(f'Raider Role: {g.get_raider_role(ctx.guild.id)}\n'
                  +  f'Vet Role: {g.get_vetraider_role(ctx.guild.id)}\n'
                  +  f'Raidstream Role: {g.get_raidstream_role(ctx.guild.id)}\n'
                  +  f'Nitro Role: {g.get_nitro_role(ctx.guild.id)}\n'
                  +  f'Early Roles: {g.get_early_roles(ctx.guild.id)}\n')
    
    elif mainarg == 'sections':
      await ctx.send(f'```{g.gdict[ctx.guild.id][g.GDICT_SECTIONS].keys()}```')
      
    elif mainarg == 'hcs':
      mngrs = get_managers()
      await ctx.send(f'{[mngrs[ctx.guild.id][sect].active_hcs for sect in mngrs[ctx.guild.id]]}')
    
    elif mainarg == 'afks':
      mngrs = get_managers()
      await ctx.send(f'{[mngrs[ctx.guild.id][sect].active_afks for sect in mngrs[ctx.guild.id]]}')
    
    elif mainarg and len(mainarg) > 8 and mainarg[:8] == 'section_':
      await ctx.send(f'```{g.gdict[ctx.guild.id][g.GDICT_SECTIONS][mainarg[8:]]}```')
    
    
    else:
      await ctx.send("Invalid view option given.")
    
    pass
  
  @commands.command(name='setup')
  @commands.has_any_role(*g.get_admin_roles())
  async def setup(self, ctx: commands.Context, mainarg=None, *args):
    """[Admin+] Setup command.

    Args:
        mainarg (str): Which setup command to use.
        
    Setup Commands:
        setup debug <enabled|disabled>
          Enables or disables debug mode.
    
        setup role <stream|raider|vet|nitro> role_id
          Sets whatever role to the role id given.
            Stream role is the ephemeral streaming role.
            Raider is the raider role.
            Vet is the veteran raider role.
            Nitro is the nitro role. :shrug:
            
        setup role early <add|remove|set> role_ids...
          Sets, adds, or removes from the early roles.
          Early roles will automatically get moved into the voice channel and given location
          as soon as they click the Join button.
        
        setup susproof <channel_id>
          Sets the suspension proof channel.

        setup runinfo <channel_id>
          Sets the run info channel.

        setup deafcheck <warntime|susptime> <time>
          Sets the warning or suspension time for a detected deafen. Time is in seconds.
            After the warntime, the user will be messaged by the bot asking them to undeafen.
            Then, after susptime has passed, the owner of the previous AFK will be messaged in suspension proof.

        setup afkrelevancy <time>
          Sets the time an AFK check is considered 'relevant' to <time>. Time is in seconds.
          Note that only one AFK check can be considered 'relevant' for each voice channel at a time.

        setup section add|remove name
          Adds or removes a section.
          
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
      if len(args) < 2:
        await ctx.send('Invalid number of arguments passed.')
        return
      
      if args[0] == 'stream':
        try:
          g.gdict[gid][g.GDICT_RAIDSTREAM_ROLE] = int(args[1])
          await ctx.send(f"Role ID set to {int(args[1])}")
        except ValueError:
          await ctx.send("Argument must be an integer.")
          return
        
      elif args[0] == 'raider':
        try:
          g.gdict[gid][g.GDICT_RAIDER_ROLE] = int(args[1])
          await ctx.send(f"Role ID set to {int(args[1])}")
        except ValueError:
          await ctx.send("Argument must be an integer.")
          return
        
      elif args[0] == 'vet':
        try:
          g.gdict[gid][g.GDICT_VETRAIDER_ROLE] = int(args[1])
          await ctx.send(f"Role ID set to {int(args[1])}")
        except ValueError:
          await ctx.send("Argument must be an integer.")
          return
      
      elif args[0] == 'nitro':
        try:
          g.gdict[gid][g.GDICT_NITRO_ROLE] = int(args[1])
          await ctx.send(f"Role ID set to {int(args[1])}")
        except ValueError:
          await ctx.send("Argument must be an integer.")
          return
      
      elif args[0] == 'early':
        try:
          if args[1] == 'add':
            for rolestr in args[2:]:
              roleid = int(rolestr)
              if rolestr not in g.gdict[gid][g.GDICT_EARLY_ROLES]:
                g.gdict[gid][g.GDICT_EARLY_ROLES].append(roleid)
                await ctx.send(f"{roleid} added to early roles.")
                
          elif args[1] == 'remove':
            for rolestr in args[2:]:
              roleid = int(rolestr)
              if rolestr in g.gdict[gid][g.GDICT_EARLY_ROLES]:
                g.gdict[gid][g.GDICT_EARLY_ROLES].remove(roleid)
                await ctx.send(f"{roleid} removed from early roles.")
          
          elif args[1] == 'set':
            roleids = [int(rolestr) for rolestr in args[2:]]
            g.gdict[gid][g.GDICT_EARLY_ROLES] = roleids
            await ctx.send(f"Early role IDs set to {roleids}")
            
          else:
            await ctx.send("Invalid add|remove|set given.")
        except ValueError:
          await ctx.send("Argument must be an integer.")
          return
            
      
      else:
        await ctx.send("Invalid role type given.")
        return
      
      g.save_json(g.SHATTERS_JSON_TXT)

    elif mainarg == 'susproof':
      if len(args) < 1:
        await ctx.send('Invalid amount of arguments.')
        return

      try:
        ch: discord.TextChannel = ctx.guild.get_channel(int(args[0]))
      except:
        await ctx.send('Argument must be an integer.')
        return

      if not ch or ch.type != discord.ChannelType.text:
        await ctx.send(f'Channel ID #{args[0]} not found, or is not a text channel.')
        return

      await ctx.send(f'Suspension proof channel set to {ch.mention}.')
      g.gdict[gid][g.GDICT_SUSPROOF_CH] = ch.id
      g.save_json(g.SHATTERS_JSON_TXT)

    elif mainarg == 'runinfo':
      if len(args) < 1:
        await ctx.send('Invalid amount of arguments.')
        return

      try:
        ch: discord.TextChannel = ctx.guild.get_channel(int(args[0]))
      except:
        await ctx.send('Argument must be an integer.')
        return

      if not ch or ch.type != discord.ChannelType.text:
        await ctx.send(f'Channel ID #{args[0]} not found, or is not a text channel.')
        return

      await ctx.send(f'Run info channel set to {ch.mention}.')
      g.gdict[gid][g.GDICT_RUNINFO_CH] = ch.id
      g.save_json(g.SHATTERS_JSON_TXT)

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
        g.gdict[gid][g.GDICT_DEAFCHECK_WARNTIME] = time
        await ctx.send(f'Deafen check warn time set to {time}.')

      elif args[0] == 'susptime':
        g.gdict[gid][g.GDICT_DEAFCHECK_SUSTIME] = time
        await ctx.send(f'Deafen check suspension time set to {time}.')

      g.save_json(g.SHATTERS_JSON_TXT)

    elif mainarg == 'afkrelevancy':
      try:
        time = int(args[0])
        if time < 60:
          await ctx.send('AFK relevancy time must be > 60 seconds.')
          return

        g.gdict[gid][g.GDICT_AFK_RELEVANTTIME] = time
        await ctx.send(f'AFK Relevancy time set to {time}.')
        g.save_json(g.SHATTERS_JSON_TXT)
      except:
        await ctx.send("Invalid arguments given.")
        return

    elif mainarg == 'section':
      if len(args) < 2:
        await ctx.send('invalid amount of arguments')
        return
      
      # oh god oh fuck
      if args[0] == 'add':
        g.gdict[gid][g.GDICT_SECTIONS][args[1]] = g.DEFAULT_GUILD_DICT[g.GDICT_SECTIONS]
        pass
      
      elif args[0] == 'remove':
        g.gdict[gid][g.GDICT_SECTIONS].pop(args[1])
        pass
      
      elif args[0] in g.gdict[gid][g.GDICT_SECTIONS]:
        if len(args) > 3:
          abc = [None for a in args if a == 'None']
          if args[1] in ['voice_chs', 'drag_chs']:
            g.gdict[gid][g.GDICT_SECTIONS][args[0]][args[1]] = [int(a) for a in args[2:]]
          else:
            g.gdict[gid][g.GDICT_SECTIONS][args[0]][args[1]] = abc[2:]
        else:
          if args[2] == 'None':
            g.gdict[gid][g.GDICT_SECTIONS][args[0]][args[1]] = None
            
          elif args[1] in ['voice_chs', 'drag_chs']:
            g.gdict[gid][g.GDICT_SECTIONS][args[0]][args[1]] = int(args[2])
          else:
            g.gdict[gid][g.GDICT_SECTIONS][args[0]][args[1]] = args[2]
        pass
      
        await ctx.send(f'Section {args[0]}[{args[1]}] set to {g.gdict[gid][g.GDICT_SECTIONS][args[0]][args[1]]}')
      
      else:
        await ctx.send(f'Invalid section name `{args[0]}`. Section names are {g.gdict[gid][g.GDICT_SECTIONS].keys()}')
        
      g.save_json(g.SHATTERS_JSON_TXT)
      pass
    
    else:
      await ctx.send('Invalid operation. Options are `debug, role, deafcheck, susproof, runinfo, afkrelevancy, section`.')
    pass
  
  @commands.command('restart')
  @commands.has_any_role(*g.get_admin_roles())
  async def do_exit(self, ctx: commands.Context):
    """[Admin+] Restarts the bot."""
    self.bot.log('Restart command executed.')
    close_connections()
    g.save_json(g.SHATTERS_JSON_TXT)
    exit(-1)
  
  pass