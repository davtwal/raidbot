from datetime import datetime
import sqlite3
from sqlite3 import Connection
from typing import List, Dict, Tuple

import os

import mysql.connector

DB_USERNAME = os.getenv('DB_USERNAME')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_HOSTNAME = os.getenv('DB_HOSTNAME')
DB_PORT = os.getenv('DB_PORT')

import discord
from discord.ext import commands

import dungeons
from dungeons import SHATTERS_DNAME, FUNGAL_DNAME, OSANC_DNAME, VOID_DNAME, CULT_DNAME, NEST_DNAME, get
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

def setup_dbs(bot: commands.Bot):
  print('[SETUPDB]: Setting up databases.')
  for guild in bot.guilds:
    if guild.id == SHATTERS_DISCORD_ID:
      try:
        bot.db_connections[guild.id] = mysql.connector.connect(
          host = DB_HOSTNAME,
          user = DB_USERNAME,
          password = DB_PASSWORD,
          port = int(DB_PORT),
          database = "shatters"
        )

        bot.log(f'[SETUPDB]: {guild.name} SHATTERS: {bot.db_connections[guild.id]}')
      except mysql.connector.errors.DatabaseError:
        bot.log(f'[SETUPDB]: [[ERROR]] Unable to connect to vibot database! Maybe bot is down?')
      pass
    else:
      bot.log(f'[SETUPDB]: {guild.name} setup as {guild.name.lower()}.db')
      bot.db_connections[guild.id] = sqlite3.connect(f'{guild.name.lower()}.db')
      for e in DB_SETUP_EXECUTES:
        #print(f'[SETUPDB]: -- Executing {e}')
        bot.db_connections[guild.id].execute(e)
      bot.log('[SETUPDB]: -- Committing')
      bot.db_connections[guild.id].commit()
  pass

def add_runs_done(bot, guild_id, d_code, users: List[discord.Member], leader: discord.Member):
  def do_update():
    cursor = bot.db_connections[guild_id].cursor()
    user_ids = [str(user.id) for user in users]
  


    if guild_id == SHATTERS_DISCORD_ID:
      if d_code == SHATTERS_DNAME:
        print(f'[ADD_RUNS]: Adding Shatters runs to {[u.display_name for u in users]}')
        sql = f"update users set runs = runs + 1 where id in ({', '.join(user_ids)});"
        print(f"-- {sql}")
        cursor.execute(sql)
      else:
        print(f'[ADD_RUNS]: Adding event runs for {[u.display_name for u in users]}')
        sql = f"update users set eventruns = eventruns + 1 where id in ({', '.join(user_ids)});"
        print(f"-- {sql}")
        cursor.execute(sql)
    
      bot.db_connections[guild_id].commit()

  try:
    do_update()
    return True
  except mysql.connector.errors.OperationalError as e:
    bot.log(f"RUNLOG OP ERROR: {e.msg}")
    bot.log(f"Restarting connections...")
    close_connections(bot)
    setup_dbs(bot)
    try:
      do_update()
      return True
    except mysql.connector.errors.OperationalError as e:
      bot.log(f"RUNLOG OP ERROR: {e.msg}")
      bot.log('Original restart failed!!!')
      return False

  column = d_code if d_code in TRACKED_DUNGEONS else EVENTS_COL_NAME
  print(f'[ADD_RUNS]: Adding 1 {column} to {[u.display_name for u in users]}')
  
  # add in all members that are part of the participant list
  cursor.execute(f"insert or ignore into {RUN_TRACK_TABLE} ({ID_COL_NAME}) values ({'), ('.join(user_ids)});")
  cursor.execute(f"update {RUN_TRACK_TABLE} set {column} = {column} + 1 where {ID_COL_NAME} in ({', '.join(user_ids)});")

  # update leader's runs led for this type
  cursor.execute(f"update {RUN_TRACK_TABLE} set {LEAD_PREFIX+column} = {LEAD_PREFIX+column} + 1 where {ID_COL_NAME} = {leader.id}")
  bot.db_connections[guild_id].commit()
  pass

def get_run_stats(bot, guild_id, user_id) -> Tuple[int, ...]:
  cursor = bot.db_connections[guild_id].execute(f"select * from {RUN_TRACK_TABLE} where {ID_COL_NAME} = {user_id}")
  print('[GET_STATS]: Finding stats for {user_id}')
  res = cursor.fetchone()
  # the [1:] chops off the ID column
  return res[1:] if res else None

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

STATS_MSG_LEN = len(';stats')
class TrackingCog(commands.Cog):
  def __init__(self, bot: commands.Bot):
    self.bot = bot

  #@commands.has_any_role(*get_manager_roles())
  #@commands.command(name='claw')  
  async def claw(self, ctx: commands.Context, type):
    """[Manager+] Runs through a channel looking for specific messages.

    Things to claw for:
     - "afk": Searches for AFK check panels from either ShattsBot (this bot) or ViBot.
    """
    if type.lower() == 'afk':
      since_date = datetime.now()
      since_date = since_date.replace(month=(since_date.month-3)%11, year=(since_date.year - 1 if since_date.month < 3 else since_date.year))

      msg = await ctx.send(embed=discord.Embed("Searching for ended AFK checks..."))

      found = await claw_fn(ctx.channel, "AFK", self.bot.user, since_date)
      
      embed = discord.Embed()
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