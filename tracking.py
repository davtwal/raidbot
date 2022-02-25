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
from dungeons import SHATTERS_DNAME, FUNGAL_DNAME, OSANC_DNAME, VOID_DNAME, CULT_DNAME, NEST_DNAME

db_connections: Dict[int, Connection] = {}

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
      db_connections[guild.id] = mysql.connector.connect(
        host = DB_HOSTNAME,
        user = DB_USERNAME,
        password = DB_PASSWORD,
        port = int(DB_PORT),
        database = "shatters"
      )

      print(f'[SETUPDB]: {guild.name} SHATTERS: {db_connections[guild.id]}')
      pass
    else:
      print(f'[SETUPDB]: {guild.name} setup as {guild.name.lower()}.db')
      db_connections[guild.id] = sqlite3.connect(f'{guild.name.lower()}.db')
      for e in DB_SETUP_EXECUTES:
        print(f'[SETUPDB]: -- Executing {e}')
        db_connections[guild.id].execute(e)
      print('[SETUPDB]: -- Committing')
      db_connections[guild.id].commit()
  pass

def add_runs_done(guild_id, d_code, users: List[discord.Member], leader: discord.Member):
  cursor = db_connections[guild_id].cursor()
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
    
    db_connections[guild_id].commit()
    return

  column = d_code if d_code in TRACKED_DUNGEONS else EVENTS_COL_NAME
  print(f'[ADD_RUNS]: Adding 1 {column} to {[u.display_name for u in users]}')
  
  # add in all members that are part of the participant list
  cursor.execute(f"insert or ignore into {RUN_TRACK_TABLE} ({ID_COL_NAME}) values ({'), ('.join(user_ids)});")
  cursor.execute(f"update {RUN_TRACK_TABLE} set {column} = {column} + 1 where {ID_COL_NAME} in ({', '.join(user_ids)});")

  # update leader's runs led for this type
  cursor.execute(f"update {RUN_TRACK_TABLE} set {LEAD_PREFIX+column} = {LEAD_PREFIX+column} + 1 where {ID_COL_NAME} = {leader.id}")
  db_connections[guild_id].commit()
  pass

def get_run_stats(guild_id, user_id) -> Tuple[int, ...]:
  if guild_id == SHATTERS_DISCORD_ID:
    
    return

  cursor = db_connections[guild_id].execute(f"select * from {RUN_TRACK_TABLE} where {ID_COL_NAME} = {user_id}")
  print('[GET_STATS]: Finding stats for {user_id}')
  res = cursor.fetchone()
  # the [1:] chops off the ID column
  return res[1:] if res else None

def close_connections():
  for con in db_connections:
    db_connections[con].close()

import re
STATS_MSG_LEN = len(';stats')
class TrackingCog(commands.Cog):
  def __init__(self, bot: commands.Bot):
    self.bot = bot
    
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
        
      stats = get_run_stats(message.guild.id, uid)
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