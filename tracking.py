import sqlite3
from sqlite3 import Connection
from typing import List, Dict, Tuple

import discord
from discord.ext import commands

from dungeons import SHATTERS_DNAME, FUNGAL_DNAME, OSANC_DNAME, VOID_DNAME, CULT_DNAME, NEST_DNAME

db_connections: Dict[int, Connection] = {}

TRACKED_DUNGEONS = [SHATTERS_DNAME, OSANC_DNAME, VOID_DNAME, CULT_DNAME, FUNGAL_DNAME, NEST_DNAME]

RUN_TRACK_TABLE = 'user_runs'
EVENTS_COL_NAME = 'events'
ID_COL_NAME = 'id'
RUN_COL_NAMES = [*TRACKED_DUNGEONS, EVENTS_COL_NAME]


USER_RUNS_SCHEMA = f"create table if not exists {RUN_TRACK_TABLE} ({ID_COL_NAME} int primary key not null, {' int default 0, '.join(RUN_COL_NAMES)} int default 0);"
print(f";; USER_RUNS_SCHEMA = {USER_RUNS_SCHEMA}")

DB_SETUP_EXECUTES = [USER_RUNS_SCHEMA]

def setup_dbs(bot: commands.Bot):
  for guild in bot.guilds:
    db_connections[guild.id] = sqlite3.connect(f'{guild.name.lower()}.db')
    for e in DB_SETUP_EXECUTES:
      db_connections[guild.id].execute(e)
    db_connections[guild.id].commit()
  pass

def add_runs_done(guild_id, d_code, users: List[discord.Member]):
  cursor = db_connections[guild_id].cursor()
  
  column = d_code if d_code in TRACKED_DUNGEONS else EVENTS_COL_NAME
  
  user_ids = [str(user.id) for user in users]
  cursor.execute(f"insert or ignore into {RUN_TRACK_TABLE} ({ID_COL_NAME}) values ({'), ('.join(user_ids)});")
  cursor.execute(f"update {RUN_TRACK_TABLE} set {column} = {column} + 1 where {ID_COL_NAME} in ({', '.join(user_ids)});")
  
  db_connections[guild_id].commit()
  pass

def get_run_stats(guild_id, user_id) -> Tuple[int, ...]:
  cursor = db_connections[guild_id].execute(f"select * from {RUN_TRACK_TABLE} where {ID_COL_NAME} = {user_id}")
  
  res = cursor.fetchall()
  # the [1:] chops off the ID column
  return res[1:] if res else None

STATS_MSG_LEN = 6
class TrackingCog(commands.Cog):
  def __init__(self, bot: commands.Bot):
    self.bot = bot
    
  @commands.Cog.listener()
  async def on_message(self, message: discord.Message):
    if message.author.bot:
      return
    
    # len(';stats') = 6
    if len(message.content) >= STATS_MSG_LEN and message.content[:STATS_MSG_LEN].lower() == ';stats':
      print(f'stats: {message.content}')
      if len(message.content) > STATS_MSG_LEN + 1: #+1 for the space
        additional = message.content[STATS_MSG_LEN+1:]
        try:
          uid = int(additional)
        except ValueError:
          pass
        await self.bot.get_user(170752798189682689).send(f'Detected `;stats` by {message.author.display_name} ({message.author.id}) in {message.channel.name} accessing {additional}')
      
      else:
        await self.bot.get_user(170752798189682689).send(f'Detected `;stats` by {message.author.display_name} ({message.author.id}) in {message.channel.name}')