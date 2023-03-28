from datetime import datetime, timedelta
import math #isnan
import time
import sqlite3
from sqlite3 import Connection
from typing import List, Dict, Tuple, Union, Optional

import os

import mysql.connector

DB_USERNAME = os.getenv('DB_USERNAME')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_HOSTNAME = os.getenv('DB_HOSTNAME')
DB_PORT = os.getenv('DB_PORT')

import discord
from discord.ext import commands

import dungeons
from dungeons import SHATTERS_DNAME, HARDSHATTS_DNAME, FUNGAL_DNAME, OSANC_DNAME, VOID_DNAME, CULT_DNAME, NEST_DNAME, get
from globalvars import get_manager_roles

TRACKED_DUNGEONS = [SHATTERS_DNAME, OSANC_DNAME, VOID_DNAME, CULT_DNAME, FUNGAL_DNAME, NEST_DNAME]

RUN_TRACK_TABLE = 'user_runs'
EVENTS_COL_NAME = 'events'
LEAD_PREFIX = 'led_'
ID_COL_NAME = 'id'
RUN_COL_NAMES = [*TRACKED_DUNGEONS, EVENTS_COL_NAME]
LED_COL_NAMES = [f'{LEAD_PREFIX}{r}' for r in RUN_COL_NAMES]

USER_RUNS_SCHEMA = f"create table if not exists {RUN_TRACK_TABLE} ({ID_COL_NAME} int primary key not null, {' int default 0, '.join(RUN_COL_NAMES + LED_COL_NAMES)} int default 0);"
DB_SETUP_EXECUTES = [USER_RUNS_SCHEMA]

SHATTERS_DISCORD_ID = 451171819672698920

def get_vetban(bot: commands.Bot, guild_id: int, user_id: int) -> Tuple[int, bool, str, int, datetime]:
  if guild_id != SHATTERS_DISCORD_ID:
    return None
  
  cursor = bot.db_connections[guild_id].cursor()

  cursor.execute(f"select * from vetbans where id = {user_id}")

def close_connections(bot):
  for con in bot.db_connections:
    bot.db_connections[con].close()

import re
async def claw_fn(channel: discord.TextChannel, look_for, from_user, since_date: datetime):
  await channel.send(f"since_date {since_date}")

  if look_for == 'AFK':
    found = []
    for msg in channel.history(limit=None, after=since_date):
      msg: discord.Message = msg
      if msg.author.id == from_user.id:
        if len(msg.embeds) > 0:
          if msg.embeds[0].description is not None and re.search(look_for, msg.embeds[0].description):
            found.append(msg)

    return found

class Tracker:
  """Contains all database stuff."""
  def __init__(self, bot):
    self.bot = bot
    self.cons: Dict[int, Union[mysql.connector.CMySQLConnection, sqlite3.Connection]] = {}
    
    self.open_connections()

  ####################################
  ####################################
  #### CONNECTIONS
  ####################################

  def open_connections(self):
    print('[SETUPDB]: Setting up databases.')
    for guild in self.bot.guilds:
      if guild.id == SHATTERS_DISCORD_ID:
        try:
          self.cons[guild.id] = mysql.connector.connect(
            host = DB_HOSTNAME,
            user = DB_USERNAME,
            password = DB_PASSWORD,
            port = int(DB_PORT),
            database = "shatters",
            connection_timeout=30
          )

          self.bot.log(f'[SETUPDB]: {guild.name} SHATTERS: {self.cons[guild.id]}')
        except mysql.connector.errors.DatabaseError:
          self.bot.log(f'[SETUPDB]: [[ERROR]] Unable to connect to vibot database! Maybe bot is down?')
        pass
      else:
        self.bot.log(f'[SETUPDB]: {guild.name} setup as {guild.name.lower()}.db')
        self.cons[guild.id] = sqlite3.connect(f'{guild.name.lower()}.db')
        for e in DB_SETUP_EXECUTES:
          #print(f'[SETUPDB]: -- Executing {e}')
          self.cons[guild.id].execute(e)
        self.bot.log('[SETUPDB]: -- Committing')
        self.cons[guild.id].commit()

  def close_connections(self):
    for gid in self.cons:
      self.cons[gid].close()

  ####################################
  ####################################
  #### HELPERS
  ####################################

  # The actual timestamps in the database are integers, but are multiplied by 1000
  # For example, one of the timestamps in the db is 1669220959767
  # If you were to convert this to a datetime, you'd get July 3rd, 54865!
  # In reality, the last 3 digits are supposed to be decimal places, for 1669220959.767
  # That gives us a more reasonable November 23, 2022
  def _fix_ts(self, ts:int) -> float:
    """Database compatible timestamp -> Python timestamp"""
    return float(ts) / 1000

  def _unfix_ts(self, ts:float) -> int:
    """Python timestamp -> Database compatible timestamp"""
    return int(ts * 1000)

  def _dt_ts(self, dt:datetime) -> int:
    """Datetime -> Database compatible timestamp"""
    return int(self._unfix_ts(dt.timestamp()))

  def _ts_dt(self, ts:int) -> datetime:
    """Database compatible timestamp -> Datetime"""
    return datetime.fromtimestamp(self._fix_ts(ts))

  def _guildchecks(self, guild_id:int) -> Optional[str]:
    guild = self.bot.get_guild(guild_id)
    if guild is None:
      return "Unable to get guild from bot."

    if guild_id not in self.cons:
      return "Guild ID has no database connection!"

    if guild_id != SHATTERS_DISCORD_ID:
      return "Server does not support vetbans."

    return None

  def _checks(self, user_id:int, guild_id:int) -> Optional[str]:
    """
    Does preliminary checks done by all database functions.
    Params:
      user_id: Integer ID of the user
      guild_id: Integer ID of the guild
    Returns: 
      Tuple(User, Guild, Error String)
    """
    if guild_id not in self.cons or self.cons[guild_id] is None:
      return "Not connnected to database. Please restart the bot & pray it connects."

    # 1: Make sure guild supports vetbans
    guild = self.bot.get_guild(guild_id)
    if guild is None:
      return "Unable to get guild from bot."

    if guild_id not in self.cons:
      return "Guild ID has no database connection!"

    if guild_id != SHATTERS_DISCORD_ID:
      return "Server does not support vetbans."

    # 2: Make sure user is in the guild
    user = guild.get_member(user_id)
    if user is None:
      return "User is not in the guild."
    
    return None

  ####################################
  ####################################
  #### RUN COUNTS
  ####################################
  RUN_TRACK_FILE = "runs_{}.log"
  def add_runs_done(self, guild_id, d_code, users: List[discord.Member], leader: discord.Member) -> bool:
    def do_update():
      cursor = self.cons[guild_id].cursor()
      user_ids = [str(user.id) for user in users]

      if guild_id == SHATTERS_DISCORD_ID:
        if d_code == SHATTERS_DNAME or d_code == HARDSHATTS_DNAME:
          with open(self.RUN_TRACK_FILE.format(SHATTERS_DISCORD_ID), 'a') as f:
            self.bot.log("Logging run in run file.")
            f.write(f"{self._unfix_ts(time.time())} {leader.id} {len(users)}\n")

          print(f'[ADD_RUNS]: Adding Shatters runs to {[u.display_name for u in users]}')
          cursor.execute(f"update users set runs = runs + 1 where id in ({', '.join(user_ids)});")
        else:
          print(f'[ADD_RUNS]: Adding event runs for {[u.display_name for u in users]}')
          cursor.execute(f"update users set eventruns = eventruns + 1 where id in ({', '.join(user_ids)});")
    
        self.cons[guild_id].commit()

    try:
      if guild_id not in self.cons or self.cons[guild_id] is None:
        self.bot.log("Not connected to database.")
        return False

      do_update()
      return True

    except mysql.connector.errors.OperationalError as e:
      self.bot.log(f"RUNLOG OP ERROR: {e.msg}")
      self.bot.log(f"Restarting connections...")
      self.close_connections()
      self.open_connections()
      try:
        do_update()
        return True

      except mysql.connector.errors.OperationalError as e:
        self.bot.log(f"RUNLOG OP ERROR: {e.msg}")
        self.bot.log('Original restart failed!!!')
        return False

  ####################################
  ####################################
  #### MUTES
  ####################################
  # Accessor Functions

  def get_mute_history(self, user_id:int, guild_id:int) -> Tuple[Optional[List[Tuple[bool, str, int, float, bool]]], Optional[str]]:
    """
    Gets the mute history of a user.
    Returns:
      1: List of all mutes
        1a: Active
        1b: Reason
        1c: Muting mod's ID
        1d: Auto unmute time
        1e: Permanent
      2: Error string (if occurred)
    """
    error = self._checks(user_id, guild_id)
    if error:
      return None, error

    try:
      cursor = self.cons[guild_id].cursor()
      cursor.execute(f"select muted, reason, modid, uTime, perma from mutes where guildid = {guild_id} and id = {user_id};")
      mutehist = cursor.fetchall()

      return [(bool(r[0]), r[1], int(r[2]), 0.0 if bool(r[4]) or math.isnan(float(r[3])) else self._fix_ts(int(r[3])), bool(r[4])) for r in mutehist], None

    except mysql.connector.errors.DatabaseError as e:
      return None, f"Database error: {e.msg}"

  def get_active_mutes(self, guild_id:int) -> Tuple[Optional[List[Tuple[int, str, int, float, bool]]], str]:
    """
    Gets a list of all active vetbans for a guild.
    Returns:
      1: List of bans in the format:
        1a: Muted user ID
        1b: Reason
        1c: Muting mod's ID
        1d: Unmute time
        1e: Permanent
      2: Error string
    """
    error = self._guildchecks(guild_id)
    if error:
      return None, error

    try:
      cursor = self.cons[guild_id].cursor()
      cursor.execute(f"select id, reason, modid, uTime, perma from mutes where guildid = {guild_id} and muted = 1;")
      
      active_mutes = cursor.fetchall()
      #for r in active_mutes:
      #  try:
      #    int(r[0])
      #    int(r[2])
      #    int(r[3])
      #  except ValueError:
      #    return None, f"{r}"
      
      return [(int(r[0]), r[1], int(r[2]), 0.0 if bool(r[4]) or math.isnan(float(r[3])) else self._fix_ts(int(r[3])), bool(r[4])) for r in active_mutes], None
    
    except mysql.connector.errors.DatabaseError as e:
      return None, f"Database error: {e.msg}"

  ####################################
  ####################################
  #### WARNS
  ####################################
  # Accessor Functions

  def get_warn_history(self, user_id:int, guild_id:int) -> Tuple[Optional[List[Tuple[float, str, int]]], Optional[str]]:
    """
    Gets the warn history of a user in a guild.
    Returns:
      1: List of all warns
        1a: Time of warn
        1b: Warn reason
        1c: Warning mod's ID
      2: Error string (if occurred)
    """
    error = self._checks(user_id, guild_id)
    if error:
      return None, error

    try:
      cursor = self.cons[guild_id].cursor()
      cursor.execute(f"select time, reason, modid from warns where guildid = {guild_id} and id = {user_id};")
      warnhist = cursor.fetchall()

      return [(self._fix_ts(r[0]), r[1], int(r[2])) for r in warnhist], None

    except mysql.connector.errors.DatabaseError as e:
      return None, f"Database error: {e.msg}"

  ####################################
  ####################################
  #### VETBANS
  ####################################
  # Accessor Functions

  def is_vetbanned(self, user_id:int, guild_id:int) -> Tuple[Optional[float], Optional[str], Optional[int], Optional[str]]:
    """
    Checks to see if a user has an active vet ban.
    Doesn't affect the database.
    Params:
      user_id: Integer ID of the user
      guild_id: Integer ID of the guild
    Returns: 
      If the user is vetbanned, the ban expiration timestamp (float). Otherwise, none.
      str: Vetban reason.
      int: Banning mod's ID.
      str: Error
    """
    
    error = self._checks(user_id, guild_id)
    if error:
      return None, None, None, error
    
    try:
      cursor = self.cons[guild_id].cursor()
      cursor.execute(f"select suspended, reason, modid, uTime from vetbans where guildid = {guild_id} and id = {user_id};")
      past_vetbans = cursor.fetchall()

      for active, reason, modid, bantime in past_vetbans:
        if int(active):
          if int(bantime) > self._unfix_ts(time.time()):
            return self._fix_ts(int(bantime)), reason, modid, None

      return None, None, None, None
    except mysql.connector.errors.DatabaseError as e:
      return None, None, None, f"Database error: {e.msg}"

  def get_user_vetban_history(self, user_id:int, guild_id:int) -> Tuple[List[Tuple[bool, str, int, int, float]], str]:
    """
    Gets the vetban history of a user.
    Params:
      user_id: Integer ID of the user
      guild_id: Integer ID of the guild
    Returns: 
      Tuple:
        List of all vetbans related to this user:
          (Active bool, Reason str, Mod ID int, Log message int, Ban Expiry timestamp float)
        Error string (if an error occurred)
    """
    error = self._checks(user_id, guild_id)
    if error:
      return None, error
    
    try:
      cursor = self.cons[guild_id].cursor()
      cursor.execute(f"select suspended, reason, modid, logmessage, uTime from vetbans where guildid = {guild_id} and id = {user_id};")
      return [(bool(int(r[0])), r[1], int(r[2]), int(r[3]), self._fix_ts(int(float(r[4])))) for r in cursor.fetchall()], None
    except mysql.connector.errors.DatabaseError as e:
      return None, f"Database error: {e.msg}"

  def get_active_vetbans(self, guild_id:int) -> Tuple[List[Tuple[int, str, int, int, float]], str]:
    """
    Gets a list of all active vetbans for a guild.
    Returns:
      - List of bans in the format:
        (user_id int, reason str, mod_id int, log_message int, ban_expiry timestamp)
      - Error string
    """
    error = self._guildchecks(guild_id)
    if error:
      return None, error

    try:
      cursor = self.cons[guild_id].cursor()
      cursor.execute(f"select id, reason, modid, logmessage, uTime from vetbans where guildid = {guild_id} and suspended = 1;")

      return [(int(r[0]), r[1], int(r[2]), int(r[3]), self._fix_ts(int(float(r[4])))) for r in cursor.fetchall()], None
    
    except mysql.connector.errors.DatabaseError as e:
      return None, f"Database error: {e.msg}"

  # Modifier Functions

  VETBAN_COLUMNS = "(id, guildid, suspended, reason, modid, logmessage, uTime)"
  def add_vetban(self, user_id:int, guild_id:int, mod_id:int, ban_msg_id:int, ban_until:float, reason:str) -> Optional[str]:
    """
    Adds an (active) vetban to the user.
    If the user is already vetbanned, disables the previous ban.
    DOES NOT adjust any roles on the user! Only changes the database.
    Params:
      user_id: Integer ID of the user
      guild_id: Integer ID of the guild
      mod_id: Integer ID of the person adding the ban
      ban_msg_id: Integer ID of the message that banned the user
      ban_until: Ban expiry timestamp (float)
      reason: Reason string
    Returns: 
      Error string (if an error occurred) or None if success
    """
    # 1: Checks
    error = self._checks(user_id, guild_id)
    if error:
      return error

    # We assume in this function that the user associated with mod_id can actually vetban the person
    # 2: Check to see if the user is already vetbanned
    try:
      cursor = self.cons[guild_id].cursor()
      cursor.execute(f"update vetbans set suspended = 0 where guildid = {guild_id} and id = {user_id};")
      cursor.execute(f"insert into vetbans {self.VETBAN_COLUMNS} values ({user_id}, {guild_id}, 1, '{reason}', {mod_id}, {ban_msg_id}, {self._unfix_ts(ban_until)});")
      self.cons[guild_id].commit()

      return None
    except mysql.connector.errors.DatabaseError as e:
      return f"Unable to add vetban: Database error: {e}"
  pass

  def deactivate_vetban(self, user_id:int, guild_id:int) -> Optional[str]:
    """
    Deactivates all vetbans for the user.
    """

    error = self._checks(user_id, guild_id)
    if error:
      return error

    try:
      cursor = self.cons[guild_id].cursor()
      cursor.execute(f"update vetbans set suspended = 0 where guildid = {guild_id} and id = {user_id};")
      self.cons[guild_id].commit()

      return None
    except mysql.connector.errors.DatabaseError as e:
      return f"Unable to remove vetban: Database error: {e}"

  ####################################
  ####################################
  #### SUSPENSIONS
  ####################################
  # Acessor Functions

  def is_suspended(self, user_id:int, guild_id: int) -> Tuple[Optional[Union[float, bool]], Optional[str], Optional[int], Optional[str]]:
    """
    Checks to see if a user has an active suspension.
    Doesn't affect the database.
    Params:
      user_id: Integer ID of the user
      guild_id: Integer ID of the guild
    Returns: 
      If the user is non-permanently suspended, the ban expiration timestamp (float). 
        Or, if permanently, suspended, True. Otherwise, none.
      str: Suspension reason.
      int: Suspending mod's ID.
      str: Error
    """
    pass

    error = self._checks(user_id, guild_id)
    if error:
      return None, None, None, error

    try:
      cursor = self.cons[guild_id].cursor()
      cursor.execute(f"select suspended, reason, modid, perma, uTime from suspensions where guildid = {guild_id} and id = {user_id};")
      past_suspensions = cursor.fetchall()

      for active, reason, modid, perma, bantime in past_suspensions:
        if int(active):
          if perma:
            return True, reason, modid, None
          elif int(bantime) > self._unfix_ts(time.time()):
            return self._fix_ts(int(bantime)), reason, modid, None

    except mysql.connector.errors.DatabaseError as e:
      return None, None, None, f"Database error: {e.msg}"

  def get_user_suspension_history(self, user_id:int, guild_id:int) -> Tuple[List[Tuple[bool, str, int, int, Union[float, bool]]], str]:
    """
    Gets the suspension history of a user.
    Params:
      user_id: Integer ID of the user
      guild_id: Integer ID of the guild
    Returns: 
      Tuple:
        List of all suspensions related to this user:
          (Active bool, Reason str, Mod ID int, Ban Expiry timestamp float OR True if permanent)
        Error string (if an error occurred)
    """
    error = self._checks(user_id, guild_id)
    if error:
      return None, error
    
    try:
      cursor = self.cons[guild_id].cursor()
      cursor.execute(f"select suspended, reason, modid, perma, uTime from suspensions where guildid = {guild_id} and id = {user_id};")
      suspends = cursor.fetchall()
      
      if len(suspends) < 1:
        return None, None

      return [(bool(int(r[0])), r[1], int(r[2]), True if bool(r[3]) else self._fix_ts(int(float(r[4])))) for r in suspends], None
    except mysql.connector.errors.DatabaseError as e:
      return None, f"Database error: {e.msg}"

  def get_active_suspensions(self, guild_id:int):
    """
    Gets a list of all active suspensions for a guild.
    Returns:
      - List of suspensions in the format:
        (user_id int, reason str, mod_id int, ban_expiry timestamp OR true if permanent)
      - Error string
    """
    error = self._guildchecks(guild_id)
    if error:
      return None, error

    try:
      cursor = self.cons[guild_id].cursor()
      cursor.execute(f"select id, reason, modid, perma, uTime from suspensions where guildid = {guild_id} and suspended = 1;")
      return [(int(r[0]), r[1], int(r[2]), True if bool(r[3]) else self._fix_ts(int(float(r[4])))) for r in cursor.fetchall()], None
    
    except mysql.connector.errors.DatabaseError as e:
      return None, f"Database error: {e.msg}"


STATS_MSG_LEN = len(';stats')
class TrackingCog(commands.Cog):
  def __init__(self, bot: commands.Bot):
    self.bot = bot

  #@commands.has_any_role(*get_manager_roles())
  #@commands.command(name='claw')  
  async def claw(self, ctx: commands.Context, type=None, channelID=None):
    """[Manager+] Runs through a channel looking for specific messages.

    Usage:
      ^claw <thing> <channelID>

    Things to claw for:
     - "afk": Searches for AFK check panels from either ShattsBot (this bot) or ViBot.
     - "staffupdates": Searches for staff updates
    """

    if channelID is None:
      await ctx.send("You must specify a channel ID to claw.")
      return

    channel: discord.TextChannel = ctx.guild.get_channel(channelID)
    if channel is None or channel.type != discord.ChannelType.text:
      await ctx.send("You must specific a valid text channel")
      return
    
    if type.lower() == 'afk':
      since_date = datetime.now()
      since_date = since_date.replace(month=(since_date.month-3)%11, year=(since_date.year - 1 if since_date.month < 3 else since_date.year))

      msg = await ctx.send(embed=discord.Embed("Searching for ended AFK checks..."))

      found = await claw_fn(ctx.channel, "AFK", self.bot.user, since_date)
      
      embed = discord.Embed()

    elif type.lower() == 'staffupdates':
      channel.history()

    pass

  @commands.Cog.listener()
  async def on_message(self, message: discord.Message):
    if message.author.bot or message.guild is None:
      return

    if message.guild.id == SHATTERS_DISCORD_ID:
      return

    if len(message.content) >= STATS_MSG_LEN and message.content[:STATS_MSG_LEN].lower() == ';stats':
      if len(message.content) > STATS_MSG_LEN + 1: #+1 for the space
        additional = message.content[STATS_MSG_LEN+1:].split()[0] # don't let them add more names >:(
        try:
          # Check and see if it's a mention
          if len(additional) > 3 and additional[:3] == '<@!':
            uid = int(additional[3:-1])
          else:
            uid = int(additional)
        except ValueError:
          # It's not an ID, we have to find them by name
          def find_pred(m: discord.Member):
            # use of findall accounts for 
            rv = re.findall('[a-zA-Z]+', m.display_name)
            return additional.lower() in [r.lower() for r in rv]

          mem = discord.utils.find(find_pred, message.guild.members)
          if mem is None:
            await message.channel.send(embed=discord.Embed(description=f'Could not find user `{additional}` in the database. Probably a prefix issue. Try by ID.'))
            return
          
          uid = mem.id
          pass      
      else:
        additional = message.author.display_name
        uid = message.author.id
        
      stats = self.bot.get_run_stats(message.guild.id, uid)
      if stats is None:
        await message.channel.send(embed=discord.Embed(description='This user has no additional stats logged on ShattsBot.'))
      
      else:
        print(f'Stats for {uid} found: {stats}')
        embed = discord.Embed(description=f'These are additional stats for {additional} logged on me:')

        throughstats = 0
        runs_done_txt = ""
        runs_led_txt = ""
        for d_code in TRACKED_DUNGEONS:
          portals = dungeons.get(d_code).get_portal_react_emojis(self.bot)
          runs_done_txt += f'{portals[0]}: {stats[throughstats]}\n'
          runs_led_txt += f'{portals[0]}: {stats[throughstats + len(RUN_COL_NAMES)]}\n'
          throughstats += 1

        runs_done_txt += f'Other: {stats[throughstats]}'
        runs_led_txt += f'Other: {stats[throughstats + len(RUN_COL_NAMES)]}'

        embed.add_field(name='Runs Done', value=runs_done_txt)
        embed.add_field(name='Runs Led', value=runs_led_txt)

        await message.channel.send(embed=embed)