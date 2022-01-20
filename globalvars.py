from json.encoder import JSONEncoder
import os
import json
from unittest.mock import DEFAULT
import discord
from discord.ext import commands
from typing import List, Dict

from discord.ext.commands.bot import when_mentioned

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
REACT_X = '❌'
REACT_CHECK = '✅'
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

         #Shatters                                                  #Fungal           #Dungeoneer
ROLES = [['Trial Raid Leader', 'Verifier', 'Security', 'Officer',   'Helper',         'Trial Leader'],
         ['Event Raid Leader',                                      'Event Master',   'Event Leader'],
         ['Almost Raid Leader', 'Raid Leader',                                        'Oryx Leader', 'Almost Oryx Leader', 'Shatters Leader', 'Almost Shatters Leader', 'Void Leader', 'Almost Void Leader'],
         ['Veteran Raid Leader', 'Veteran Event Leader'],
         ['Head Raid Leader'],
         ['Developer', 'Admin', 'Owner',                            'Moderator',      'Administrator']]

# Dungeon Role Whitelist
# 'dungeon_role_whitelist': {'<dung_code>': [role_id0, role_id1...]}
# For each dungeon code, only those with a given role in the list will be able to lead them.
# Roles should be IDs, but for example's sake they're names
# E.g:
# 'shatters': ['Almost Shatters Leader', 'Shatters Leader']

def get_admin_roles() -> List[str]:
  return ROLES[-1]

def get_manager_roles() -> List[str]:
  return ROLES[-2] + get_admin_roles()

def get_veteran_roles() -> List[str]:
  return ROLES[-3] + get_manager_roles()

def get_raid_roles() -> List[str]:
  return ROLES[2] + get_veteran_roles()

def get_event_roles() -> List[str]:
  return ROLES[1] + get_raid_roles()

def get_staff_roles() -> List[str]:
  return ROLES[0] + get_event_roles()

gdict = {}

bot_debugmode = False

#single items
GDICT_RAIDSTREAM_ROLE = 'raidstream'
GDICT_RAIDER_ROLE = 'raiderrole'
GDICT_VETRAIDER_ROLE = 'vetrole'
GDICT_NITRO_ROLE = 'nitro'
GDICT_EARLY_ROLES = 'earlies'

# raiding sections
GDICT_SECTIONS = 'sections'
GDICT_SECTION_EVENTS = 'event'
GDICT_SECTION_RAIDING = 'raiding'
GDICT_SECTION_VETERAN = 'veteran'

#GDICT_DUNGEON_ROLE_WHITELIST = 'dung_role_wlist'

DEFAULT_GUILD_DICT = {
  GDICT_RAIDSTREAM_ROLE: '',
  GDICT_RAIDER_ROLE: '',
  GDICT_VETRAIDER_ROLE: '',
  GDICT_NITRO_ROLE: '',
  GDICT_EARLY_ROLES: [],
#  GDICT_DUNGEON_ROLE_WHITELIST: {},
  GDICT_SECTIONS: {}
}

def get_guild_ids():
  return gdict.keys()

def get_guild_section_names(guild_id):
  return gdict[guild_id][GDICT_SECTIONS].keys()

def get_raidstream_role(guild_id) -> str:
  return gdict[guild_id][GDICT_RAIDSTREAM_ROLE]

def get_raider_role(guild_id) -> str:
  return gdict[guild_id][GDICT_RAIDER_ROLE]

def get_vetraider_role(guild_id) -> str:
  return gdict[guild_id][GDICT_VETRAIDER_ROLE]

def get_nitro_role(guild_id) -> str:
  return gdict[guild_id][GDICT_NITRO_ROLE]

def get_early_roles(guild_id) -> List[str]:
  return gdict[guild_id][GDICT_EARLY_ROLES]

#def get_role_whitelist(guild_id) -> Dict[str, List[int]]:
#  return gdict[guild_id][GDICT_DUNGEON_ROLE_WHITELIST]

#def can_do_dungeon(guild_id, dungeon_code, ) -> bool:
#  pass

def get_role_tier(role) -> int:
  for i in range(len(ROLES)):
    if role in ROLES[i]:
      return i
  return -1

class RaidingSection:
  def __init__(self, name:str, input_dict:dict):    
    self.name = name
    self.cmd_ch:int           = self._try_add(input_dict, 'cmd_ch')
    self.status_ch:int        = self._try_add(input_dict, 'status_ch')
    self.run_info_ch:int      = self._try_add(input_dict, 'run_info_ch')
    self.min_role_tier:int    = self._try_add(input_dict, 'min_role_tier')
    self.lounge_ch:int        = self._try_add(input_dict, 'lounge_ch')
    self.voice_chs:List[int]  = self._try_add(input_dict, 'voice_chs')
    self.drag_chs:List[int]   = self._try_add(input_dict, 'drag_chs')
    self.is_vet:bool          = self._try_add(input_dict, 'is_vet')
    self.allow_unlock:bool    = self._try_add(input_dict, 'allow_unlock')
    self.allow_setcap:bool    = self._try_add(input_dict, 'allow_setcap')
    self.vc_min:int           = self._try_add(input_dict, 'min_vc_cap')
    self.vc_max:int           = self._try_add(input_dict, 'max_vc_cap')
    
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
  
  def _try_add(self, d, i):
    try:
      return d[i]
    except:
      return None
  
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
    elif key == 'whitelist':      return self.whitelist
    elif key == 'blacklist':      return self.blacklist
    
  def __setitem__(self, key, value:str):
    try:
      if key == 'cmd_ch':           self.cmd_ch         = int(value)
      elif key == 'status_ch':      self.status_ch      = int(value)
      elif key == 'run_info_ch':    self.run_info_ch    = int(value)
      elif key == 'min_role_tier':  self.min_role_tier  = int(value)
      elif key == 'lounge_ch':      self.lounge_ch      = int(value)
      elif key == 'voice_chs':      self.voice_chs      = [int(x) for x in value.split()]
      elif key == 'drag_chs':       self.drag_chs       = [int(x) for x in value.split()]
      elif key == 'is_vet':         self.is_vet         = bool(value)
      elif key == 'allow_unlock':   self.allow_unlock   = bool(value)
      elif key == 'allow_setcap':   self.allow_setcap   = bool(value)
      elif key == 'min_vc_cap':     self.vc_min         = int(value)
      elif key == 'max_vc_cap':     self.vc_max         = int(value)
      elif key == 'whitelist':      self.whitelist      = [x for x in value.split()]
      elif key == 'blacklist':      self.blacklist      = [x for x in value.split()]
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
    elif key == 'whitelist':      del self.whitelist
    elif key == 'blacklist':      del self.blacklist
  
  def __str__(self):
    return str(self.__dict__())
  
  def toJSON(self):
    return self.__str__()
  
  def role_check(self, user_roles: List[discord.Role]):
    # n^2 :dead:
    for role in user_roles:
      if get_role_tier(role.name) >= self.min_role_tier:
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

def get_section(guild_id, name) -> RaidingSection:
  try:
    return gdict[guild_id][GDICT_SECTIONS][name]
  except KeyError:
    return None

def get_event_section(guild_id) -> RaidingSection:
  return gdict[guild_id][GDICT_SECTIONS][GDICT_SECTION_EVENTS]

def get_raiding_section(guild_id) -> RaidingSection:
  return gdict[guild_id][GDICT_SECTIONS][GDICT_SECTION_RAIDING]

def get_veteran_section(guild_id) -> RaidingSection:
  return gdict[guild_id][GDICT_SECTIONS][GDICT_SECTION_VETERAN]

# NEW CODE
def get_cmd_channels(guild_id) -> list:
  ch_list = []
  for section in gdict[guild_id][GDICT_SECTIONS]:
    ch_list.append(section.cmd_ch)
  return ch_list

def get_section_from_cmd_ch(guild_id, ch_id) -> RaidingSection:
  for section in gdict[guild_id][GDICT_SECTIONS]:
    if gdict[guild_id][GDICT_SECTIONS][section].cmd_ch == ch_id:
      return gdict[guild_id][GDICT_SECTIONS][section]
    
  return None

def get_section_from_voice_ch(guild_id, ch_id) -> RaidingSection:
  for section in gdict[guild_id][GDICT_SECTIONS]:
    for voice_ch in gdict[guild_id][GDICT_SECTIONS][section].voice_chs:
      if voice_ch == ch_id:
        return gdict[guild_id][GDICT_SECTIONS][section]
      
  return None  

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
    react, ignored = await bot.wait_for('reaction_add', check=react_check, timeout=timeout)
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

def load_json(json_txt):
  with open(json_txt, "r") as f:
    global gdict
    
    print(f"LOADING JSON: {json_txt}")
    
    gdict = {}
    tempdict = json.loads(str(f.read()))
    
    for guild in tempdict:
      print(f'Fixing Guild: {guild}')
      gdict[int(guild)] = tempdict[guild]
      
      for item in DEFAULT_GUILD_DICT:
        if item not in gdict[int(guild)]:
          print(f'++ {item} not found; adding')
          gdict[int(guild)][item] = DEFAULT_GUILD_DICT[item]
      
      for section in gdict[int(guild)][GDICT_SECTIONS]:
        print(f'- Fixing Section: {section}')
        gdict[int(guild)][GDICT_SECTIONS][section] = RaidingSection(name=section, input_dict=gdict[int(guild)][GDICT_SECTIONS][section])

def update_dict(bot: commands.Bot):
  for guild in bot.guilds:
    if guild.id not in gdict:
      print(f'Guild {guild.name} has been added')
      gdict[guild.id] = DEFAULT_GUILD_DICT
      
  save_json(SHATTERS_JSON_TXT)
  pass

def is_debug() -> bool:
  return bot_debugmode

class Encoder(JSONEncoder):
  def default(self, o):
    return o.__dict__()

def save_json(json_text):
  with open(json_text, "w") as f:
    f.write(json.dumps(gdict, cls=Encoder))

SHATTERS_JSON_TXT = "database.json"

load_json(SHATTERS_JSON_TXT)

#print(channelpairs)