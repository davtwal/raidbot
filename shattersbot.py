from datetime import datetime
from typing import Any, Dict, List
import pytz
import asyncio
import json

import discord
from discord.ext import commands

from section_manager import SectionAFKCheckManager
from globalvars import RaidingSection, Encoder
from tracking import setup_dbs, add_runs_done, close_connections, get_run_stats

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
#  GDICT_DUNGEON_ROLE_WHITELIST: {},
  GDICT_SECTIONS: {}
}

class ShattersBot(commands.Bot):

  def __init__(self):
    self.gdict: Dict[int, Dict[str, Any]] = {}
    self.managers: Dict[int, Dict[str, SectionAFKCheckManager]] = {}
    self.db_connections: Dict[int, Any] = {}
    self.debugmode: bool = False

    self.load_db()

    intents = discord.Intents.default()
    intents.members = True
    intents.messages = True

    super().__init__(command_prefix="^", intents=intents)
  
  async def _log(self, logstr):
    try:
      #await self.debugch.send(f'`{logstr}`')
      pass
    except:
      print('could not send')
      pass

  def log(self, debugstr):
    logstr = f"({datetime.now(tz=pytz.timezone('US/Pacific')).replace(microsecond=0).time()}) {debugstr}"
    asyncio.create_task(self._log(logstr))
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

  #async def setup_dbs(self):
  #  pass

  ####################
  ## On-Ready
  ####################

  async def on_ready(self):
    try:
      self.debugch = await self.fetch_channel(DEBUG_LOG_CHANNEL)
    except:
      print(f"!!!! COULD NOT FETCH DEBUG CHANNEL: {DEBUG_LOG_CHANNEL}!!!!!")

    self.log('--------------------BOOT UP--------------------')
    self.log(f'Bot logged in: {self.user} (ID {self.user.id})')
    self.log('-----------------------------------------------')
    
    self.startup_time = datetime.now()

    manager_setups: Dict[int, List[str]] = {}

    self.update_dict()

    for guild in self.gdict:
      manager_setups[guild] = []
      for section in self.gdict[guild][GDICT_SECTIONS]:
        manager_setups[guild].append(section)
        
    self.setup_managers(manager_setups)
    self.setup_dbs()

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

  def setup_dbs(self):
    setup_dbs(self)

  def add_runs_done(self, guild_id, d_code, users, leader):
    add_runs_done(self, guild_id, d_code, users, leader)

  def close_connections(self):
    close_connections(self)
  
  def get_run_stats(self, guild_id, user_id):
    return get_run_stats(self, guild_id, user_id)
