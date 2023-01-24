import discord
from discord.ext import commands

import random
from globalvars import get_veteran_roles, get_raid_roles

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