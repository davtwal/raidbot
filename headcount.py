import asyncio
from datetime import datetime
from typing import Union

import discord
from discord.ext import commands

import dungeons
from globalvars import REACT_X, REACT_CHECK, REACT_PLAY
from hc_afk_helpers import get_field_index, ask_location, get_voice_ch

REACT_WASTE = '🗑'

HC_PANEL_INFO_STR = """Press {} Convert to convert this headcount to an AFK check.
Press {} Convert (Lazy) to convert this headcount into a drag-first AFK check.
Press {} Abandon to abandon the headcount.

When someone reacts to one of the below reacts, their name will appear.
If they then unreact, their name will appear in brackets.
Example: \"raiderMan\" => \"[raiderMan]\""""

HC_ANNOUNCE_STR = '{} A {} headcount has been started by {}.'
HC_AUTO_END = 60 * 60

class Headcount:
  STATUS_GATHERING = 0
  STATUS_CONVERTING = 1
  STATUS_ENDED = 2
  
  def __init__(self, manager,
                     bot,
                     ctx: commands.Context,
                     status_ch: discord.TextChannel,
                     dungeon: dungeons.Dungeon):
    self.manager = manager
    self.bot = bot
    self.ctx = ctx
    self.status_ch = status_ch
    self.dungeon = dungeon
    
    self.care_reacts = dungeon.get_key_react_emojis(bot) + dungeon.get_early_react_emojis(bot) + dungeon.get_primary_react_emojis(bot)
    pass
  
  def owner(self) -> Union[discord.User, discord.Member]:
    try:
      return self.actual_owner
    except AttributeError:
      return self.ctx.author
  
  async def start(self):
    self.status = self.STATUS_GATHERING
    self.status_embed = discord.Embed(description=self.dungeon.get_hc_text(self.bot, self.owner()), timestamp=datetime.now())
    self.status_embed.set_author(name=self.dungeon.get_hc_title(self.bot, self.owner()), icon_url=self.owner().display_avatar.url)
    
    time = datetime.now()
    self.panel_embed = discord.Embed(description=HC_PANEL_INFO_STR.format(REACT_CHECK, REACT_PLAY, REACT_WASTE), timestamp=time.replace(hour=(time.hour+1)%24))
    self.panel_embed.set_author(name='Control Panel', icon_url=self.owner().display_avatar.url)
    self.panel_embed.set_footer(text='This headcount will auto end at')

    for care in self.care_reacts:
      label = dungeons.get_react_name(care.id, self.dungeon)
      self.panel_embed.add_field(inline=True, name=label, value='None')    
    
    here_ping = '`@here`' if self.bot.is_debug() else '@here'
    self.status_msg = self.status_ch.send(content=HC_ANNOUNCE_STR.format(here_ping, self.dungeon.name, self.owner().mention), embed=self.status_embed)
    
    self.panel_msg = self.ctx.send(embed=self.panel_embed, view=HeadcountPanelView(self))
    
    self.panel_msg = await self.panel_msg
    self.status_msg = await self.status_msg
    
    
    self.react_task = asyncio.create_task(self._add_reactions())
    self.loop_task = asyncio.create_task(self._react_wait_loop())
    self.auto_end_task = asyncio.create_task(self._auto_end_loop())
    pass
  
  async def _react_wait_loop(self):
    def react_check(payload: discord.RawReactionActionEvent):
      return payload.message_id == self.status_msg.id and payload.user_id != self.bot.user.id and payload.emoji in self.care_reacts
    
    def add_react_check(payload: discord.RawReactionActionEvent):
      return payload.event_type == 'REACTION_ADD' and react_check(payload)
    
    def rem_react_check(payload: discord.RawReactionActionEvent):
      return payload.event_type == 'REACTION_REMOVE' and react_check(payload)
     
    while True:
      done, pending = await asyncio.wait([self.bot.wait_for('raw_reaction_add', check=add_react_check), self.bot.wait_for('raw_reaction_remove', check=rem_react_check)], return_when=asyncio.FIRST_COMPLETED)
      
      for future in pending:
        future.cancel()
        
      result = done.pop().result()
      
      user = await self.bot.fetch_user(result.user_id)
      field_index = get_field_index(result.emoji, [self.care_reacts])
      
      if result.event_type == 'REACTION_ADD':
        await self._add_react(field_index, user)
      
      elif result.event_type == 'REACTION_REMOVE':
        await self._remove_react(field_index, user)
  
  async def _auto_end_loop(self):
    await asyncio.sleep(HC_AUTO_END)
    await self.abandon(auto_end=True)
    pass
  
  async def _add_reactions(self):
    for react in self.dungeon.get_hc_reacts():
      emoji = self.bot.get_emoji(react)
      if emoji is not None:
        await self.status_msg.add_reaction(emoji)
  
  async def _add_react(self, field_index: int, user: discord.Member):
    field_text = self.panel_embed.fields[field_index].value
    if field_text == 'None':
      field_text = user.mention
    
    else:
      sections = field_text.split()
      sections = [sec[1:-1] if sec[0] == '[' and sec[1:-1] == user.mention else sec for sec in sections]
      if user.mention not in sections:
        sections.append(user.mention)
      field_text = ' '.join(sections)
      
    self.panel_embed._fields[field_index]['value'] = field_text
    await self.panel_msg.edit(embed=self.panel_embed)
  
  async def _remove_react(self, field_index, user):
    field_text = self.panel_embed.fields[field_index].value
    if field_text == 'None':
      await self.ctx.send("Error: Field text was None on reaction remove")
      return
    
    sections = field_text.split()
    sections = ['[' + sec + ']' if sec == user.mention else sec for sec in sections]
    field_text = ' '.join(sections)
    self.panel_embed._fields[field_index]['value'] = field_text
    await self.panel_msg.edit(embed=self.panel_embed)
  
  async def abandon(self, auto_end=False):
    """Abandons the headcount."""
    if self.status != self.STATUS_GATHERING:
      return
    self.status = self.STATUS_ENDED    
    
    self.react_task.cancel()
    self.loop_task.cancel()
    if not auto_end:
      self.auto_end_task.cancel()
      
    new_cp_embed = discord.Embed(title=self.panel_embed.title, description=f"This headcount has been {'automatically ended' if auto_end else 'cancelled'}.", timestamp=datetime.now())
    new_cp_embed.set_author(name=self.panel_embed.author.name, icon_url=self.panel_embed.author.icon_url)
    new_hc_embed = discord.Embed(title=self.status_embed.title, description=f'This headcount was started by {self.owner().mention}, but abandoned.', timestamp=datetime.now())
    new_hc_embed.set_author(name=self.status_embed.author.name, icon_url=self.status_embed.author.icon_url)
    
    self.manager.remove_headcount(self.owner().id)
    
    await asyncio.wait([
      self.panel_msg.edit(embed=new_cp_embed, view=None),
      self.panel_msg.clear_reactions(),
      self.status_msg.edit(content=f'This headcount was abandoned. {REACT_WASTE}', embed=new_hc_embed),
      self.status_msg.clear_reactions()
    ])
    
    await self.status_msg.add_reaction(REACT_WASTE)
    await self.panel_msg.add_reaction(REACT_WASTE)
    pass
  
  async def _finalize_convert(self, lazy):
    self.status = self.STATUS_ENDED
      
    self.react_task.cancel()
    self.loop_task.cancel()
    self.auto_end_task.cancel()
      
    self.panel_embed.description = 'This headcount has been converted.'
    self.panel_embed.timestamp = datetime.now()
    await self.panel_msg.edit(embed=self.panel_embed, view=None)
    await self.panel_msg.add_reaction(REACT_PLAY if lazy else REACT_CHECK)
      
    self.status_embed.description = 'This headcount was converted into an AFK check.'
    await self.status_msg.edit(content='Headcount converted.', embed=self.status_embed)
      

  async def _do_convert(self, lazy):
    location = await ask_location(self.bot, self.ctx)
    if location is None:
      self.status = self.STATUS_GATHERING
      return
    
    voice_ch = await get_voice_ch(self.bot, self.ctx, self.manager.section)
    if voice_ch is None:
      self.status = self.STATUS_GATHERING
      return
    
    # try_convert calls _finalize_convert for us
    # as that function can also be called from a command.
    success = await self.manager.try_convert_hc_to_afk(self, voice_ch, lazy, location)
    
    if not success:
      self.status = self.STATUS_GATHERING
  
  # This needs to return fast so the interaction doesn't fail.
  async def convert_to_afk(self, lazy):
    if self.bot.pending_shutdown:
      return

    if self.status != self.STATUS_GATHERING:
      return
    
    self.status = self.STATUS_CONVERTING
    asyncio.create_task(self._do_convert(lazy))
    pass  
  pass

class HeadcountPanelView(discord.ui.View):
  def __init__(self, headcount: Headcount):
    super().__init__(timeout=None)
    self.headcount = headcount
    pass
  
  @discord.ui.button(label='Convert', style=discord.ButtonStyle.green, emoji=REACT_CHECK)
  async def convert_plain(self, button: discord.ui.Button, interaction: discord.Interaction):
    if interaction.user.id != self.headcount.owner().id:
      await interaction.response.send_message(content="You are not the owner of this AFK check.", ephemeral=True)
      return

    await self.headcount.convert_to_afk(False)
    pass
  
  @discord.ui.button(label='Convert (Lazy)', style=discord.ButtonStyle.blurple, emoji=REACT_PLAY)
  async def convert_lazy(self, button: discord.ui.Button, interaction: discord.Interaction):
    if interaction.user.id != self.headcount.owner().id:
      await interaction.response.send_message(content="You are not the owner of this AFK check.", ephemeral=True)
      return
    
    await self.headcount.convert_to_afk(True)
    pass
  
  @discord.ui.button(label='Abandon', style=discord.ButtonStyle.gray, emoji=REACT_WASTE)
  async def abandon(self, button: discord.ui.Button, interaction: discord.Interaction):
    if interaction.user.id != self.headcount.owner().id:
      await interaction.response.send_message(content="You are not the owner of this AFK check.", ephemeral=True)
      return
    
    self.stop()
    await self.headcount.abandon()
    pass
  
  pass