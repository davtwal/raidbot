import asyncio
from typing import Tuple

import discord
from discord.ext import commands

import dungeons
from globalvars import get_veteran_roles, find_channel, REACT_X, REACT_CHECK, RaidingSection
#def check_vetleader(ctx: commands.Context):
#  """Checks to see if the user is a veteran leader.
#
#  Args:
#      ctx (commands.Context): Context
#
#  Returns:
#      bool: Whether or not the user is a veteran leader.
#  """
#  for role in ctx.author.roles:
#    if role.name in get_vetleader_roles():
#      return True
#      
#  return False

async def can_lead_hardmode(ctx: commands.Context):
  hm_role = ctx.guild.get_role(1071247034583097384) # HM Leader
  if hm_role and hm_role in ctx.author.roles:
    return True

  for role in get_veteran_roles():
    if role in [r.name for r in ctx.author.roles]:
      return True

  return False
  pass

class ConfirmView(discord.ui.View):
  def __init__(self):
    super().__init__(timeout=30)
    self.value = None
  
  async def on_timeout(self) -> None:
    self.stop()
  
  @discord.ui.button(label='Yes', style=discord.ButtonStyle.green, emoji=REACT_CHECK)
  async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction):
    self.value = True
    self.stop()
    
  @discord.ui.button(label='No', style=discord.ButtonStyle.red, emoji=REACT_X)
  async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
    self.value = False
    self.stop()

#from datetime import datetime
#def log(logstr):
#  print(f'({datetime.now().replace(microsecond=0).time()}){logstr}')

DCHECK_OK = 0
DCHECK_LIST = -1
DCHECK_INVALID = -2

def dungeon_checks(dungeon) -> Tuple[int, dungeons.Dungeon]:
  # Check to see if no dungeon was given or they want a list
  if dungeon == None or dungeon == 'list':
    return -1, None
    
  d = None
  for d_type in dungeons.dungeonlist:
    if dungeon in dungeons.dungeonlist[d_type]:
      d = dungeons.dungeonlist[d_type][dungeon]
      break

  # Confirm the dungeon is actually an option
  if d is None:
    return -2, None
  
  return 0, d

async def channel_checks(ctx: commands.Context) -> Tuple[bool, RaidingSection]:
  """Performs checks to see if this command channel can be used by the user for headcount and afk check commands.

  Args:
      ctx (commands.Context): Context

  Returns:
      [bool, RaidingSection]: Whether to continue with the headcount/afk, and if yes, what section it is in.
  """
  
  section = ctx.bot.get_section_from_cmd_ch(ctx.guild.id, ctx.channel.id)
  if section is None:
    await ctx.send("This is not a valid channel for this command.")
    return False, None
  
  if section.role_check(ctx.author.roles) is False:
    await ctx.send("You do not have the required roles to use this command here.")
    return False, None
    
  statuschannel = find_channel(ctx.guild.channels, section.status_ch)
  if statuschannel is None:
    await ctx.send("Error: statuschannel for this section was None. Please contact an admin.")
    return False, None
  
  return True, section

async def ask_location(bot: commands.Bot, ctx: commands.Context):
  print("Asking location.")
  embed = discord.Embed(description=f'Please enter a location (or press {REACT_X} to cancel):')
  ask_msg = await ctx.send(embed=embed)
  await ask_msg.add_reaction(REACT_X)
  
  def msg_check(msg: discord.Message):
    return msg.author.id == ctx.author.id
  
  def react_check(react: discord.Reaction, user: discord.User):
    return user.id == ctx.author.id and react.emoji == REACT_X
  
  done, pending = await asyncio.wait([bot.wait_for('message', check=msg_check), bot.wait_for('reaction_add', check=react_check)], return_when=asyncio.FIRST_COMPLETED)
  
  for future in pending:
    future.cancel()
    
  res = done.pop().result()
  await ask_msg.delete()
  
  if isinstance(res, discord.Message):
    print(f"Returning msg: {res.content}")
    return res.content
  
  return None # only other option is an X reaction

async def create_list(bot: commands.Bot, ctx: commands.Context, allow_continue=True, show_shatters=False) -> Tuple[bool, dungeons.Dungeon]:
  """Creates the list of dungeons and shows it to the user.

  Args:
      bot (commands.Bot): The bot.
      ctx (commands.Context): Context.
      allow_continue (bool): Whether to ask if the user wants to created a headcount or AFK check.
      show_shatters (bool): Whether or not to show Shatters on the list.

  Returns:
      bool, continue_dungeon_msg: Whether to continue with headcount/afk creation, and the message the user specified with.
        If allow_continue is False, then only a boolean will be returned, and it will be False.
  """
  # Create the embed list, separated by dungeon type
  embed = discord.Embed()
  for d_code in dungeons.dungeonlist:
    field_str = ""
    for d_name in dungeons.dungeonlist[d_code]:
      if show_shatters is False and d_name == dungeons.SHATTERS_DNAME:
        continue
      cur_dungeon = dungeons.dungeonlist[d_code][d_name]
      field_str += str(bot.get_emoji(cur_dungeon.react_portals[0])) + cur_dungeon.name + ': `' + d_name + '`\n'
    
    embed.add_field(name=d_code, value=field_str)
  
  list_msg = await ctx.send(embed=embed)
  
  # If we just want to show the message, we're done
  if allow_continue is False:
    return False, None
  
  cont_msg = await ctx.send('Type in which dungeon code you would like or press the :x: to cancel:')
  await cont_msg.add_reaction(REACT_X)
  
  # Now we wait for either the author of the command to send a message, or for them to react with the X on the continue message.
  def msg_check(m):
    return m.author == ctx.author
  
  def react_check(react, user):
    return user == ctx.author and str(react.emoji) == REACT_X and react.message == cont_msg
  
  while True:
    done,pending = await asyncio.wait([
      bot.wait_for('message', check=msg_check),
      bot.wait_for('reaction_add', check=react_check),
      ], return_when=asyncio.FIRST_COMPLETED, timeout=30)
  
    # Something happened that checked out, so stop waiting for the other thing
    for future in pending:
      future.cancel()
  
    if len(done) == 0:
      await cont_msg.delete(delay=2)
      await list_msg.delete(delay=2)
      await ctx.send("Timeout. Please try again later.")
      return False, None
    
    result = done.pop().result()
    
    # If it was a message, assume it was a dungeon.
    if type(result) == discord.Message:
      dcheck_res, d = dungeon_checks(result.content)
    
      if dcheck_res == DCHECK_INVALID:
        await ctx.send(f"Dungeon invalid. Please type a valid dungeon or press the {REACT_X}.")
        continue

      if dcheck_res == DCHECK_LIST:
        await ctx.send("No, I'm not making another list. Please type a valid dungeon.")
        continue
      
      assert dcheck_res == DCHECK_OK
      
      # If we aren't allowing Shatters, then don't let them pick it. Instead, make them pick something else.
      if result.content.lower() == dungeons.SHATTERS_DNAME and show_shatters is False:
        await ctx.send("You cannot choose shatters.")
        continue
    
      # Delete the messages - they're no longer needed and are massive.
      await cont_msg.delete()
      await list_msg.delete()
      return True, d
  
    # If it was a react, we no longer want to do anything.
    else:
      # Delete the messages - they're no longer needed and are massive.
      await cont_msg.delete()
      await list_msg.delete()
      return False, None

def get_field_index(x, list_of_lists):
  cur_count = 0
  for l in list_of_lists:
    if x in l:
      return cur_count + [i for i, val in enumerate(l) if val==x][0]
    cur_count += len(l)
  return -1

NUMBER_REACTS = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']

async def get_voice_ch(bot: commands.Bot, ctx: commands.Context, raid_section: RaidingSection):
  voice_ch = ctx.author.voice.channel if ctx.author.voice and ctx.author.voice.channel else None
  
  # If the user isn't connected to a voice channel or the voice channel they're currently connected to isn't valid for this section,
  # then ask which voice channel they want to start the AFK check in.
  if voice_ch is None or voice_ch.id not in raid_section.voice_chs:
    
    # Get all of the voice channels, removing any that are invalid/None for some reason.
    available_voices = [ctx.guild.get_channel(vchid) for vchid in raid_section.voice_chs]
    available_voices = [x for x in available_voices if x]
    
    # Build the embed. It should have the following format:
    # Which would you blah blah
    # 1: Voice Ch 1
    # 2: Voice Ch 2
    # ...
    # X: Cancel
    
    embed_txt = f"Which voice channel would you like to use?\nReact with {REACT_X} if you would like to cancel.\n"
    
    for number_voice in enumerate(available_voices):
      embed_txt += f'{NUMBER_REACTS[number_voice[0]]}: {number_voice[1].mention}\n'
      
    embed_txt += f'{REACT_X}: Cancel'
    
    msg = await ctx.send(embed=discord.Embed(description=embed_txt))
    
    # Add the reactions asynchronously so we can wait on reactions from the user.
    async def add_reacts():
      for emoji in enumerate(NUMBER_REACTS):
        if emoji[0] >= len(available_voices):
          break
        await msg.add_reaction(emoji[1])
      await msg.add_reaction(REACT_X)
      
    add_react_awaitable = asyncio.create_task(add_reacts())
    
    def react_check(react: discord.Reaction, user):
      return user.id == ctx.author.id and react.message.id == msg.id and react.emoji in [*NUMBER_REACTS[:len(available_voices)], REACT_X]
    
    # Wait for a valid reaction.
    react, user = await bot.wait_for('reaction_add', check=react_check)
    
    # Stop adding reacts, we're done.
    add_react_awaitable.cancel()
    
    # Cancel.
    if react.emoji == REACT_X:
      await msg.clear_reactions()
      await msg.edit(embed=discord.Embed(description="Cancelled."))
      return None
    
    # Make sure a valid react made it through, and get the actual voice channel.
    number = NUMBER_REACTS.index(react.emoji)
    
    if number < 0 or number > len(available_voices):
      await ctx.send(f"Error: Number react was invalid @ `{number}`. Please contact an admin.")
      await msg.clear_reactions()
      return None
    
    await msg.delete()
    
    voice_ch = available_voices[number]
  
  # Done.
  return voice_ch