from datetime import datetime
from typing import Any, Dict, List, Optional
import pytz
import asyncio
import json

import discord
from discord.ext import commands

from section_manager import SectionAFKCheckManager
from globalvars import RaidingSection, Encoder
from tracking import Tracker

DEBUG_LOG_CHANNEL = 955912379902861332
DATABASE_FNAME = "database.json"

#single items
GDICT_RAIDSTREAM_ROLE = 'raidstream'
GDICT_RAIDER_ROLE = 'raiderrole'
GDICT_VETRAIDER_ROLE = 'vetrole'
GDICT_VETBANNED_ROLE = 'bannedvetrole'
GDICT_NITRO_ROLE = 'nitro'
GDICT_EARLY_ROLES = 'earlies'
GDICT_SUSPROOF_CH = 'susproof'
GDICT_RUNINFO_CH = 'runinfo'
GDICT_DEAFCHECK_WARNTIME = 'deafch_warn'      # Amount of time after deafening where a raider gets warned (s).
GDICT_DEAFCHECK_SUSTIME = 'deafch_susp'       # Amount of time after being warned where the RL is notified (s).
GDICT_AFK_RELEVANTTIME = 'afk_relevant_time'  # Amount of time an AFK check is considered 'relevant' for a voice channel.
GDICT_EVENTPING_TIMEOUT = 'eventping_timeout' # Amount of time allowed in between event pings.

#dungeon related
GDICT_DUNGEON_PING_ROLE = 'dungeonpings'

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
  GDICT_VETBANNED_ROLE: '',
  GDICT_NITRO_ROLE: '',
  GDICT_EARLY_ROLES: [],
  GDICT_SUSPROOF_CH: 0,
  GDICT_RUNINFO_CH: 0,
  GDICT_DEAFCHECK_WARNTIME: 2,
  GDICT_DEAFCHECK_SUSTIME: 90,
  GDICT_AFK_RELEVANTTIME: 30 * 60, # 30 minutes
  GDICT_EVENTPING_TIMEOUT: 2 * 60 + 30, # 2.5 minutes
#  GDICT_DUNGEON_ROLE_WHITELIST: {},
  GDICT_DUNGEON_PING_ROLE: {},
  GDICT_SECTIONS: {}
}

GDICT_INDIV_ROLES = [
  GDICT_RAIDSTREAM_ROLE,
  GDICT_RAIDER_ROLE,
  GDICT_VETRAIDER_ROLE,
  GDICT_VETBANNED_ROLE,
  GDICT_NITRO_ROLE
]

GDICT_CHANNELS = [
  GDICT_SUSPROOF_CH,
  GDICT_RUNINFO_CH
]

class ShattersBot(commands.Bot):
  def __init__(self, cmd_prefix):
    self.gdict: Dict[int, Dict[str, Any]] = {}
    self.managers: Dict[int, Dict[str, SectionAFKCheckManager]] = {}
    self.db_connections: Dict[int, Any] = {}
    self.debugmode: bool = False
    self.pending_shutdown: bool = False
    self.ready: bool = False

    self.load_db()

    intents = discord.Intents.default()
    intents.members = True
    intents.messages = True

    if hasattr(intents, 'message_content'):
      intents.message_content = True
    self.log("Booting up")
    super().__init__(command_prefix=cmd_prefix, intents=intents)
  
  async def _log(self, logstr):
    try:
      #await self.debugch.send(f'`{logstr}`')
      pass
    except:
      print('could not send')
      pass

  def log(self, debugstr):
    logstr = f"({datetime.now(tz=pytz.timezone('US/Pacific')).replace(microsecond=0).time()}) {debugstr}"
    #asyncio.create_task(self._log(logstr))
    print(logstr)

  ####################
  ## State Database
  ####################

  def load_db(self):
    with open(DATABASE_FNAME, "r") as f:
      tempdict = json.loads(str(f.read()))

      for guild in tempdict:
        gid = int(guild)
        self.gdict[gid] = tempdict[guild]

        for item in DEFAULT_GUILD_DICT:
          if item not in self.gdict[gid]:
            self.gdict[gid][item] = DEFAULT_GUILD_DICT[item]

        for sect in self.gdict[gid][GDICT_SECTIONS]:
          self.gdict[gid][GDICT_SECTIONS][sect] = RaidingSection(name=sect, input_dict=self.gdict[gid][GDICT_SECTIONS][sect])
    pass

  def save_db(self):
    with open(DATABASE_FNAME, "w") as f:
      f.write(json.dumps(self.gdict, cls=Encoder))

  def update_dict(self):
    # Load & fix dictionary
    for guild in self.guilds:
      if guild.id not in self.gdict:
        self.log(f'Guild {guild.name} has been added.')
        self.gdict[guild.id] = DEFAULT_GUILD_DICT

    self.save_db()

  ####################
  ## Setup Functions
  ####################

  def setup_managers(self, manager_setups):
    for gid in manager_setups:
      self.managers[gid] = {}
      guild = self.get_guild(gid)
      if guild is None:
        continue

      self.log(f'Guild {guild.name} (ID {gid}):')
      for section_name in manager_setups[gid]:
        self.log(f'- Section "{section_name}"')
        self.managers[gid][section_name] = SectionAFKCheckManager(self, guild, section_name)

    self.log("Finshed setting up raid managers.")
    pass

  ####################
  ## On-Ready
  ####################

  async def on_error(self, event, *args, **kwargs):
    self.log(f'ERROR: {event} {args} {kwargs}')

  async def on_connect(self):
    self.log("---------Connection to Bot Established---------")

  async def on_ready(self):
    if self.ready:
      return
    #try:
    #  self.debugch = await self.fetch_channel(DEBUG_LOG_CHANNEL)
    #except:
    #  print(f"!!!! COULD NOT FETCH DEBUG CHANNEL: {DEBUG_LOG_CHANNEL}!!!!!")

    self.log('--------------------BOOT UP--------------------')
    self.log(f'Bot logged in: {self.user} (ID {self.user.id})')
    self.log('-----------------------------------------------')
    
    self.startup_time = datetime.now()
    
    self.get_cog("Security Commands").start_auto_check()
    self.tracker = Tracker(self)

    manager_setups: Dict[int, List[str]] = {}

    self.update_dict()

    for guild in self.gdict:
      manager_setups[guild] = []
      for section in self.gdict[guild][GDICT_SECTIONS]:
        manager_setups[guild].append(section)
        
    self.setup_managers(manager_setups)
    self.ready = True

  #async def shutdown(self):

  ####################
  ## Get Functions
  ####################

  def is_debug(self) -> bool:
    return self.debugmode

  def get_raidstream_role(self, guild_id) -> int:
    return self.gdict[guild_id][GDICT_RAIDSTREAM_ROLE]

  def get_raider_role(self, guild_id) -> int:
    return self.gdict[guild_id][GDICT_RAIDER_ROLE]

  def get_vetraider_role(self, guild_id) -> int:
    return self.gdict[guild_id][GDICT_VETRAIDER_ROLE]

  def get_vetbanned_role(self, guild_id) -> int:
    return self.gdict[guild_id][GDICT_VETBANNED_ROLE]

  def get_nitro_role(self, guild_id) -> int:
    return self.gdict[guild_id][GDICT_NITRO_ROLE]

  def get_early_roles(self, guild_id) -> List[str]:
    return self.gdict[guild_id][GDICT_EARLY_ROLES]

  def get_susproof_channel(self, guild_id) -> int:
    return self.gdict[guild_id][GDICT_SUSPROOF_CH]

  def get_deafcheck_warntime(self, guild_id) -> int:
    return self.gdict[guild_id][GDICT_DEAFCHECK_WARNTIME]

  def get_deafcheck_sustime(self, guild_id) -> int:
    return self.gdict[guild_id][GDICT_DEAFCHECK_SUSTIME]

  def get_afk_relevanttime(self, guild_id) -> int:
    return self.gdict[guild_id][GDICT_AFK_RELEVANTTIME]

  def get_runinfo_channel(self, guild_id) -> int:
    return self.gdict[guild_id][GDICT_RUNINFO_CH]

  def get_dungeon_ping_role_list(self, guild_id) -> Dict[str, int]:
    return self.gdict[guild_id][GDICT_DUNGEON_PING_ROLE]

  def get_dungeon_ping_role(self, guild_id, dcode) -> Optional[discord.Role]:
    if dcode not in self.gdict[guild_id][GDICT_DUNGEON_PING_ROLE]:
      print(f"Dungeon get ping role no dcode: {dcode} in {self.gdict[guild_id][GDICT_DUNGEON_PING_ROLE]}")
      return None
    
    if self.get_guild(guild_id) is None:
      print("Dungeon get ping role no guild")
      return None
    
    return self.get_guild(guild_id).get_role(self.gdict[guild_id][GDICT_DUNGEON_PING_ROLE][dcode])

  def get_section(self, guild_id, name) -> RaidingSection:
    try:
      return self.gdict[guild_id][GDICT_SECTIONS][name]
    except KeyError:
      return None

  def get_event_section(self, guild_id) -> RaidingSection:
    return self.gdict[guild_id][GDICT_SECTIONS][GDICT_SECTION_EVENTS]

  def get_raiding_section(self, guild_id) -> RaidingSection:
    return self.gdict[guild_id][GDICT_SECTIONS][GDICT_SECTION_RAIDING]

  def get_veteran_section(self, guild_id) -> RaidingSection:
    return self.gdict[guild_id][GDICT_SECTIONS][GDICT_SECTION_VETERAN]

  # NEW CODE
  def get_cmd_channels(self, guild_id) -> list:
    ch_list = []
    for section in self.gdict[guild_id][GDICT_SECTIONS]:
      ch_list.append(section.cmd_ch)
    return ch_list

  def get_section_from_cmd_ch(self, guild_id, ch_id) -> RaidingSection:
    for section in self.gdict[guild_id][GDICT_SECTIONS]:
      if self.gdict[guild_id][GDICT_SECTIONS][section].cmd_ch == ch_id:
        return self.gdict[guild_id][GDICT_SECTIONS][section]

    return None

  def get_section_from_voice_ch(self, guild_id, ch_id) -> RaidingSection:
    for section in self.gdict[guild_id][GDICT_SECTIONS]:
      for voice_ch in self.gdict[guild_id][GDICT_SECTIONS][section].voice_chs:
        if voice_ch == ch_id:
          return self.gdict[guild_id][GDICT_SECTIONS][section]

    return None

  ####################
  ## Logging Database
  ####################

  def add_runs_done(self, guild_id, d_code, users, leader):
    self.tracker.add_runs_done(guild_id, d_code, users, leader)

  def close_connections(self):
    self.tracker.close_connections()

