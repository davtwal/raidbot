from typing import Dict, List
from datetime import datetime
import pytz

import sys
import traceback

import discord
from discord.ext import commands
from dotenv import load_dotenv
load_dotenv()

from globalvars import DISCORD_TOKEN, get_raid_roles, get_guild_ids, get_guild_section_names, update_dict
from globalvars import get_veteran_roles
from extra import ExtraCmds
from raiding import RaidingCmds, setup_managers
from admin import AdminCmds
from errorhandler import ErrorHandling
from tracking import TrackingCog, setup_dbs

import random
import re

DEBUG_LOG_CHANNEL = 955912379902861332

class ShattersBot(commands.Bot):
  def __init__(self):
    intents = discord.Intents.default()
    intents.members = True
    intents.messages = True

    super().__init__(command_prefix="^", intents=intents)
  
  async def _log(self, logstr):
    try:
      await self.debugch.send(f'`{logstr}`')
    except:
      print('could not send')
      pass

  def log(self, debugstr):
    logstr = f"({datetime.now(tz=pytz.timezone('US/Pacific')).replace(microsecond=0).time()}) {debugstr}"
    asyncio.create_task(self._log(logstr))
    print(logstr)

  async def on_ready(self):
    try:
      self.debugch = await self.fetch_channel(DEBUG_LOG_CHANNEL)
    except:
      print(f"!!!! COULD NOT FETCH DEBUG CHANNEL: {DEBUG_LOG_CHANNEL}!!!!!")

    self.log('--------------------BOOT UP--------------------')
    self.log(f'Bot logged in: {self.user} (ID {self.user.id})')
    self.log('-----------------------------------------------')
    #super().activity = discord.Game(name='shamters')
    
    manager_setups: Dict[int, List[str]] = {}

    update_dict(self)
    for guild in get_guild_ids():
      manager_setups[guild] = []
      for section in get_guild_section_names(guild):
        manager_setups[guild].append(section)
        
    setup_managers(self, manager_setups)
    setup_dbs(self)

bot = ShattersBot()

def excepthook(*exc_info):
  try:
    bot.log(traceback.format_exception(*exc_info))
  except:
    pass

sys.excepthook = excepthook

sustext = """
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⣠⣴⣶⣿⣿⣷⣶⣄⣀⣀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⣰⣾⣿⣿⡿⢿⣿⣿⣿⣿⣿⣿⣿⣷⣦⡀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⢀⣾⣿⣿⡟⠁⣰⣿⣿⣿⡿⠿⠻⠿⣿⣿⣿⣿⣧⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⣾⣿⣿⠏⠀⣴⣿⣿⣿⠉⠀⠀⠀⠀⠀⠈⢻⣿⣿⣇⠀⠀⠀
⠀⠀⠀⠀⢀⣠⣼⣿⣿⡏⠀⢠⣿⣿⣿⠇⠀ 👁⠀⠀👁 ⠈⣿⣿⣿⡀⠀⠀
⠀⠀⠀⣰⣿⣿⣿⣿⣿⡇⠀⢸⣿⣿⣿⡀⠀⠀  ⠀👄  ⠀⠀⣿⣿⣿⡇⠀⠀
⠀⠀⢰⣿⣿⡿⣿⣿⣿⡇⠀⠘⣿⣿⣿⣧⠀⠀⠀⠀⠀⠀⢀⣸⣿⣿⣿⠁⠀⠀
⠀⠀⣿⣿⣿⠁⣿⣿⣿⡇⠀⠀⠻⣿⣿⣿⣷⣶⣶⣶⣶⣶⣿⣿⣿⣿⠃⠀⠀⠀
⠀⢰⣿⣿⡇⠀⣿⣿⣿⠀⠀⠀⠀⠈⠻⣿⣿⣿⣿⣿⣿⣿⣿⣿⠟⠁⠀⠀⠀⠀
⠀⢸⣿⣿⡇⠀⣿⣿⣿⠀⠀⠀⠀⠀⠀⠀⠉⠛⠛⠛⠉⢉⣿⣿⠀⠀⠀⠀⠀⠀
⠀⢸⣿⣿⣇⠀⣿⣿⣿⠀⠀⠀⠀⠀⢀⣤⣤⣤⡀⠀⠀⢸⣿⣿⣿⣷⣦⠀⠀⠀
⠀⠀⢻⣿⣿⣶⣿⣿⣿⠀⠀⠀⠀⠀⠈⠻⣿⣿⣿⣦⡀⠀⠉⠉⠻⣿⣿⡇⠀⠀
⠀⠀⠀⠛⠿⣿⣿⣿⣿⣷⣤⡀⠀⠀⠀⠀⠈⠹⣿⣿⣇⣀⠀⣠⣾⣿⣿⡇⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠹⣿⣿⣿⣿⣦⣤⣤⣤⣤⣾⣿⣿⣿⣿⣿⣿⣿⣿⡟⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠉⠻⢿⣿⣿⣿⣿⣿⣿⠿⠋⠉⠛⠋⠉⠉⠁⠀⠀⠀⠀"""

sussy_cooldown = []

import asyncio
class RunsWhenCog(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
  
  async def unsussy(self, time, userid):
    await asyncio.sleep(time)
    sussy_cooldown.remove(userid)
  
  @commands.command(name='sus')
  @commands.has_any_role(*get_veteran_roles())
  async def sussybaka(self, ctx):
    if ctx.author.id in sussy_cooldown:
      await ctx.send("You sussy baka no spamming uwu")
    else:
      await ctx.send(sustext)
      sussy_cooldown.append(ctx.author.id)
      asyncio.create_task(self.unsussy(10*60, ctx.author.id))
  
  @commands.Cog.listener()
  async def on_message(self, message: discord.Message):
    if message.author.id == self.bot.user.id:
      return
    
    if (self.bot.user.mentioned_in(message) and not message.mention_everyone) or message.content.lower().find("shattsbot") != -1:
      mention_reacts = ['😳', '😚', '🥰', '😤', '🥴', '🤪', '😵', '🤡', '🤭', '🔨', '🍆', '🍑', '💦', '⁉', '🆗', '🤷‍♀️', '😘', '🤐', '😫', '🤫', '👁', '👀']
      random.seed()
      if message.author.id == 180490033244012545:
        await message.reply("perish, admin")
        return

      await message.add_reaction(mention_reacts[random.randint(0, len(mention_reacts) - 1)])
      
    findme = ['runs when', 'when runs', 'no runs', 'shatts when', 'when shatts', 'where runs', 'runs where', 'shatts where', 'where shatts',
              'shatters when', 'when shatters', 'where shatters', 'shatters where', 'when shatts runs', 'where shatts runs', 'when shatters runs',
              'where shatters runs', 'when shattr']
    
    already_rl = ['Whenever you want, bud.', 'At your leisure.', 'Idk bro you tell me', 'Good question, *RL*.',
                  message.content, 'Something seems off about YOU saying that...', 'xd']

    for msg in findme:
      if message.content.lower().find(msg) != -1:
        if message.author.id == 278663969256898561:
          await message.reply("Justin please come back I'm begging you we need you you are the chosen one :(((((")
          return

        rl_roles = get_raid_roles()
        for role in message.author.roles:
          if str(role) in rl_roles:
            random.seed()
            await message.reply(already_rl[random.randint(0, len(already_rl) - 1)])
            return
          
          if str(role) == 'Trial Raid Leader':
            await message.reply("<@&451176422560497676> someone give this man a TRL")
            return
        
        await message.reply("https://forms.gle/x9Vq2GtMQNZExdGs9")
        break
      pass
    pass

bot.add_cog(ErrorHandling(bot))
bot.add_cog(AdminCmds(bot))
bot.add_cog(ExtraCmds(bot))
bot.add_cog(RaidingCmds(bot))
bot.add_cog(TrackingCog(bot))
bot.add_cog(RunsWhenCog(bot))

bot.run(DISCORD_TOKEN)

class VoteButton(discord.ui.Button):
  def __init__(self, style):
    super().__init__(style=style, label='0')
    self.count = 0
    self.pressed_by = []
  
  async def callback(self, interaction: discord.Interaction):
    assert self.view is not None
    
    if interaction.user not in self.pressed_by:
      self.count += 1
      self.label = str(self.count)
      self.pressed_by.append(interaction.user)
      await interaction.response.edit_message(view=self.view)
  pass

class VoteView(discord.ui.View):
  def __init__(self):
    super().__init__()
    self.add_item(VoteButton(discord.ButtonStyle.green))
    self.add_item(VoteButton(discord.ButtonStyle.red))
    self.add_item(VoteButton(discord.ButtonStyle.gray))
  
  pass
