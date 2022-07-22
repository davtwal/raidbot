from json.encoder import JSONEncoder
import os
import discord
from discord.ext import commands
from typing import List, Dict

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
REACT_X = '❌'
REACT_CHECK = '✅'
REACT_HOOK = '↪'
REACT_PLAY = '▶'
HC_PANEL_REACTS = ['▶', '🕓', '🗑']

HC_PANEL_INFO_STR = """React with {} to convert this headcount to an AFK check.
React with {} to convert this headcount to a reactable-first AFK check.
React with {} to cancel the headcount.

When someone reacts to one of the below reacts, their name will appear.
If they then unreact, their name will appear in brackets.
Example: \"raiderMan\" => \"[raiderMan]\""""

# Roles separated by tier
# Tier 0: Staff           (Won't get moved out by the Clean command, but have no other perms)
# Tier 1: Event Leaders   (Can lead any dungeon that isn't role whitelisted)
# Tier 2: Raid Leaders    (Can lead any dungeon that is whitelisted so long as they have any other required roles)
# Tier 3: Veteran Leaders (Can do runs in Veteran section, but can't put up shatters without one of the Shatters roles)
# Tier 4: Managers        (Have all perms except bot dev & setup)
# Tier 5: Dev/Owner       (All perms)

# Role Types:
# Type 0: Administrtators and Developers. Has full control over the bot.
# Type 1: Managers. Can do everything except debug / setup commands. Has perms of Type 2 a/b/c and Type 3.
# Type 2: Leaders. Can lead raids.
#      2a: Veteran Leaders. Can lead raids in 'Veteran' sections. Has no effect on what dungeons they can run. Can vet-ban.
#      2b: Whitelisted Leaders. Can lead any dungeon in any non-veteran section that allows them.
#      2c: Event Leaders. Can lead non-whitelisted dungeons in non-veteran sections that allow them.
# Type 3: Security / Management.
#      3a: Helpers. Can warn and suspend. 
#      3b: Vet Control. Can warn, suspend, and vetban. 
#      3c: Security. Can verify (all kinds) and blacklist from Mod-Mail.
# Type 4: Other Staff

ROLES = [
  ['Developer', 'Admin', 'Administrator', 'Moderator', 'Owner'], # Type 0: Admin/Dev
  ['Head Raid Leader', 'Officer'], # Type 1: Manager
  ['Veteran Raid Leader', 'Veteran Event Leader'], # Type 2a: Vet ;eaders
  ['Almost Raid Leader', 'Raid Leader'], # Type 2b: Whitelist leaders
  ['Event Raid Leader', 'Security'], # Type 2c: Event leaders
  ['Almost Raid Leader', 'Raid Leader'], # Type 3a: Helpers
  ['Helper', 'Veteran Raid Leader', 'Veteran Event Leader'], # Type 3b: Vet controllers
  ['Security', 'Verifier'], # Type 3c: Security
  ['Trial Raid Leader'] # Type 4: Other
]

         #Shatters                                                  #Fungal           #Dungeoneer
#ROLES = [['Trial Raid Leader', 'Verifier', 'Security', 'Officer',   'Helper',         'Trial Leader'],
#         ['Event Raid Leader',                                      'Event Master',   'Event Leader'],
#         ['Almost Raid Leader', 'Raid Leader',                                        'Oryx Leader', 'Almost Oryx Leader', 'Shatters Leader', 'Almost Shatters Leader', 'Void Leader', 'Almost Void Leader'],
#         ['Veteran Raid Leader', 'Veteran Event Leader'],
#         ['Head Raid Leader'],
#         ['Developer', 'Admin', 'Owner',                            'Moderator',      'Administrator']]

# Dungeon Role Whitelist
# 'dungeon_role_whitelist': {'<dung_code>': [role_id0, role_id1...]}
# For each dungeon code, only those with a given role in the list will be able to lead them.
# Roles should be IDs, but for example's sake they're names
# E.g:
# 'shatters': ['Almost Shatters Leader', 'Shatters Leader']
# This has not been implemented yet.

def get_admin_roles() -> List[str]:
  return ROLES[0]

def get_manager_roles() -> List[str]:
  return ROLES[1] + get_admin_roles()

def get_veteran_roles() -> List[str]:
  return ROLES[2] + get_manager_roles()

def get_raid_roles() -> List[str]:
  return ROLES[3] + get_manager_roles()

def get_event_roles() -> List[str]:
  return ROLES[4] + get_raid_roles()

def get_security_roles() -> List[str]:
  return ROLES[7] + get_manager_roles()

def get_vetcontrol_roles() -> List[str]:
  return ROLES[6] + get_security_roles()

def get_helper_roles() -> List[str]:
  return ROLES[5] + get_vetcontrol_roles()

def get_staff_roles() -> List[str]:
  x = []
  for i in range(0, len(ROLES)):
    x += ROLES[i]
  return x

bot_debugmode = False


#def get_role_whitelist(guild_id) -> Dict[str, List[int]]:
#  return gdict[guild_id][GDICT_DUNGEON_ROLE_WHITELIST]

#def can_do_dungeon(guild_id, dungeon_code, ) -> bool:
#  pass

class RaidingSection:
  def __init__(self, name:str, input_dict:dict):    
    self.name = name
    self.cmd_ch:int           = self._try_add(input_dict, 'cmd_ch')         # Raid announcement channel
    self.status_ch:int        = self._try_add(input_dict, 'status_ch')      # Bot command channel
    self.run_info_ch:int      = self._try_add(input_dict, 'run_info_ch')    # 'Run info' channel
    self.min_role_tier:int    = self._try_add(input_dict, 'min_role_tier')  # [[UNUSED]] Minimum role tier required to put up runs/headcounts
    self.lounge_ch:int        = self._try_add(input_dict, 'lounge_ch')      # Lounge voice channel
    self.voice_chs:List[int]  = self._try_add(input_dict, 'voice_chs')      # Raiding voice channels
    self.drag_chs:List[int]   = self._try_add(input_dict, 'drag_chs')       # Respective drag channels
    self.is_vet:bool          = self._try_add(input_dict, 'is_vet', False)        # Veteran-only channel
    self.allow_unlock:bool    = self._try_add(input_dict, 'allow_unlock', True)   # If the voice channel can be locked/unlocked with ^lock
    self.allow_setcap:bool    = self._try_add(input_dict, 'allow_setcap', True)   # If the voice channel cap can be altered
    self.vc_min:int           = self._try_add(input_dict, 'min_vc_cap', 25) # Minimum VC cap
    self.vc_max:int           = self._try_add(input_dict, 'max_vc_cap', 50) # Maximum VC cap
    self.max_overcap:int      = self._try_add(input_dict, 'max_overcap', 5) # Maximum amount of people that can be draged in over the VC cap
    self.deafcheck:bool       = self._try_add(input_dict, 'deafcheck', False)      # If we care about people being deafened in runs for too long
    self.deafcheck_vet:bool   = self._try_add(input_dict, 'deafcheck_vet', False)  # If we care about veterans being deafened in runs for too long
    
    if 'whitelist' in input_dict and input_dict['whitelist'] is not None:
      self.whitelist:List[str] = input_dict['whitelist']
      self.blacklist = None
      print('-- Section had a whitelist.')
    
    elif 'blacklist' in input_dict and input_dict['blacklist'] is not None:
      self.blacklist:List[str] = input_dict['blacklist']   
      self.whitelist = None
      print('-- Section had a blacklist.')
      
    else:
      self.blacklist = None
      self.whitelist = None
      print('-- Section had no white or blacklist.')
    
    pass
  
  def _try_add(self, d, i, default=None):
    try:
      return d[i]
    except:
      return default
  
  def __dict__(self):
    d = {
      'cmd_ch': self.cmd_ch,
      'status_ch': self.status_ch,
      'run_info_ch': self.run_info_ch,
      'min_role_tier': self.min_role_tier,
      'lounge_ch': self.lounge_ch,
      'voice_chs': self.voice_chs,
      'drag_chs': self.drag_chs,
      'is_vet': self.is_vet,
      'allow_unlock': self.allow_unlock,
      'allow_setcap': self.allow_setcap,
      'min_vc_cap': self.vc_min,
      'max_vc_cap': self.vc_max,
      'max_overcap': self.max_overcap,
      'deafcheck': self.deafcheck,
      'deafcheck_vet': self.deafcheck_vet
    }
    if self.whitelist is not None:
      d['whitelist'] = self.whitelist
    if self.blacklist is not None:
      d['blacklist'] = self.blacklist
    return d
  
  def __getitem__(self, key):
    if key == 'cmd_ch':           return self.cmd_ch
    elif key == 'status_ch':      return self.status_ch
    elif key == 'run_info_ch':    return self.run_info_ch
    elif key == 'min_role_tier':  return self.min_role_tier
    elif key == 'lounge_ch':      return self.lounge_ch
    elif key == 'voice_chs':      return self.voice_chs
    elif key == 'drag_chs':       return self.drag_chs
    elif key == 'is_vet':         return self.is_vet
    elif key == 'allow_unlock':   return self.allow_unlock
    elif key == 'allow_setcap':   return self.allow_setcap
    elif key == 'min_vc_cap':     return self.vc_min
    elif key == 'max_vc_cap':     return self.vc_max
    elif key == 'max_overcap':    return self.max_overcap
    elif key == 'whitelist':      return self.whitelist
    elif key == 'blacklist':      return self.blacklist
    elif key == 'deafcheck':      return self.deafcheck
    elif key == 'deafcheck_vet':  return self.deafcheck_vet

  def __setitem__(self, key, value:str):
    try:
      print(f'setting {key} to {value}')
      if key == 'cmd_ch':           self.cmd_ch         = int(value)
      elif key == 'status_ch':      self.status_ch      = int(value)
      elif key == 'run_info_ch':    self.run_info_ch    = int(value)
      elif key == 'min_role_tier':  self.min_role_tier  = int(value)
      elif key == 'lounge_ch':      self.lounge_ch      = int(value)
      elif key == 'voice_chs':      self.voice_chs      = [int(x) for x in value.split()] if isinstance(value, str) else value
      elif key == 'drag_chs':       self.drag_chs       = [int(x) for x in value.split()] if isinstance(value, str) else value
      elif key == 'is_vet':         self.is_vet         = bool(value)
      elif key == 'allow_unlock':   self.allow_unlock   = bool(value)
      elif key == 'allow_setcap':   self.allow_setcap   = bool(value)
      elif key == 'min_vc_cap':     self.vc_min         = int(value)
      elif key == 'max_vc_cap':     self.vc_max         = int(value)
      elif key == 'max_overcap':    self.max_overcap    = int(value)
      elif key == 'whitelist':      self.whitelist      = [x for x in value.split()] if isinstance(value, str) else value
      elif key == 'blacklist':      self.blacklist      = [x for x in value.split()] if isinstance(value, str) else value
      elif key == 'deafcheck':      self.deafcheck      = bool(value)
      elif key == 'deafcheck_vet':  self.deafcheck_vet  = bool(value)
    except:
      print(f'error in setting {key} to {value}')
    
  def __delitem__(self, key):
    print(f'delete {key}')
    if key == 'cmd_ch':           del self.cmd_ch
    elif key == 'status_ch':      del self.status_ch
    elif key == 'run_info_ch':    del self.run_info_ch
    elif key == 'min_role_tier':  del self.min_role_tier
    elif key == 'lounge_ch':      del self.lounge_ch
    elif key == 'voice_chs':      del self.voice_chs
    elif key == 'drag_chs':       del self.drag_chs
    elif key == 'is_vet':         del self.is_vet
    elif key == 'allow_unlock':   del self.allow_unlock
    elif key == 'allow_setcap':   del self.allow_setcap
    elif key == 'min_vc_cap':     del self.vc_min
    elif key == 'max_vc_cap':     del self.vc_max
    elif key == 'max_overcap':    del self.max_overcap
    elif key == 'whitelist':      del self.whitelist
    elif key == 'blacklist':      del self.blacklist
    elif key == 'deafcheck':      del self.deafcheck
    elif key == 'deafcheck_vet':  del self.deafcheck_vet
  
  def __str__(self):
    return str(self.__dict__())
  
  def toJSON(self):
    return self.__str__()
  
  def role_check(self, user_roles: List[discord.Role]):
    """Checks to see if the user can put up runs in this section.
    """
    # n^2 :dead:

    vet_req = not self.is_vet
    whitelist_role = self.whitelist is None
    has_rl_role = False

    for role in user_roles:
      if not vet_req and role.name in get_veteran_roles():
        vet_req = True
        has_rl_role = True

      if not whitelist_role and role.name in get_raid_roles():
        whitelist_role = True
        has_rl_role = True

      if not has_rl_role and role.name in get_event_roles():
        has_rl_role = True

      if vet_req and whitelist_role and has_rl_role:
        return True
    return False
  
  def dungeon_allowed(self, dungeon):
    print(f"Dcheck {dungeon} {self.whitelist} {self.blacklist}")
    if self.whitelist:
      return dungeon in self.whitelist
    
    if self.blacklist:
      return dungeon not in self.blacklist

    return True
  
  pass

## OLD CODE
#def get_channelpairs(guild_id):
#  return gdict[guild_id][GDICT_CHANNELPAIRS]
#
#def get_clean_links(guild_id):
#  return gdict[guild_id][GDICT_CLEANLINKS]
#
#def get_unlockables(guild_id):
#  return gdict[guild_id][GDICT_UNLOCKABLES]
#
#def get_setcap_max(guild_id):
#  return gdict[guild_id][GDICT_SETCAP_MAX]
#
#def get_setcap_min(guild_id):
#  return gdict[guild_id][GDICT_SETCAP_MIN]
#
#def get_setcap_vetmax(guild_id):
#  return gdict[guild_id][GDICT_SETCAP_VETMAX]
#
#def get_setcap_vetmin(guild_id):
#  return gdict[guild_id][GDICT_SETCAP_VETMIN]
#
#def get_vetchannels(guild_id):
#  return gdict[guild_id][GDICT_VETCHANNELS]
#
#def get_vetonlycmd(guild_id):
#  return gdict[guild_id][GDICT_VETONLYCMD]

def find_channel(channel_list, ch_id):
  for channel in channel_list:
    if channel.id == ch_id:
      return channel
  return None

async def confirmation(ctx: commands.Context, bot: commands.Bot, text, checktext=None, denytext=None, auth_override=None, timeout=None):
  msg = await ctx.send(embed=discord.Embed(description=text))
  await msg.add_reaction(REACT_CHECK)
  await msg.add_reaction(REACT_X)
  
  def react_check(react: discord.Reaction, user: discord.User):
    auth = auth_override or ctx.author
    return not user.bot and user.id == auth.id and react.message == msg and react.emoji in [REACT_CHECK, REACT_X]
  
  try:
    react, _ = await bot.wait_for('reaction_add', check=react_check, timeout=timeout)
    await msg.clear_reactions()
  
    if react.emoji == REACT_CHECK:
      if checktext is not None:
        await msg.edit(embed=discord.Embed(description=checktext))
      else: await msg.delete()
      return True
    else:
      if denytext is not None:
        await msg.edit(embed=discord.Embed(description=denytext))
      else: await msg.delete()
      return False
  except TimeoutError:
    await msg.clear_reactions()
    await msg.edit(embed=discord.Embed(description='Check timed out.'),delete_after=5)
    return False

class Encoder(JSONEncoder):
  def default(self, o):
    return o.__dict__()

