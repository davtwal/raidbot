import asyncio
from datetime import datetime
from typing import Union

import discord
from discord.ext import commands

import dungeons
from globalvars import REACT_X, REACT_CHECK, REACT_PLAY
from hc_afk_helpers import is_manager, get_field_index, ask_location, get_voice_ch, can_lead_hardmode

REACT_WASTE = '🗑'

HC_PANEL_INFO_STR = """Press {} Convert to convert this headcount to an AFK check.
Press {} Convert (Lazy) to convert this headcount into a drag-first AFK check.
Press {} Abandon to abandon the headcount.

When someone reacts to one of the below reacts, their name will appear.
If they then unreact, their name will appear in brackets.
Example: \"raiderMan\" => \"[raiderMan]\""""

HC_ANNOUNCE_STR = '{} A {} headcount has been started by {{}}.'
HC_AUTO_END = 60 * 60
HC_KEY_ALERT_DELAY = 3
HC_KEY_ALERT_MSG = '{} **Key alert**! {} reacted with a key. *Be sure to double check that their reaction is still there!*\nA reaction has been removed if their name is surrounded by brackets: `[removedReactor]`'

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
    
    self.key_reacts = dungeon.get_key_react_emojis(bot)
    self.care_reacts = self.key_reacts + dungeon.get_early_react_emojis(bot) + dungeon.get_primary_react_emojis(bot)
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
    self.panel_embed.set_footer(text='This headcount will auto end')

    for care in self.care_reacts:
      label = dungeons.get_react_name(care.id, self.dungeon)
      self.panel_embed.add_field(inline=True, name=label, value='None')    
    
    here_ping = '`@here`' if self.bot.is_debug() else '@here'
    ping_role: discord.Role = self.bot.get_dungeon_ping_role(self.ctx.guild.id, self.dungeon.code)
    if ping_role:
      here_ping += f" `{ping_role.mention}`" if self.bot.is_debug() else f" {ping_role.mention}"

    self.status_msg = self.status_ch.send(content=HC_ANNOUNCE_STR.format(here_ping, self.dungeon.name), embed=self.status_embed)
    
    ### Specifically for shatters:
    add_hmconv = None
    if self.dungeon.code == dungeons.HARDSHATTS_DNAME:
      add_hmconv = False
    elif self.dungeon.code == dungeons.SHATTERS_DNAME and can_lead_hardmode(self.ctx):
      add_hmconv = True

    self.panel_msg = self.ctx.send(embed=self.panel_embed, view=HeadcountPanelView(self, add_hmconv))
    
    self.panel_msg = await self.panel_msg
    self.status_msg = await self.status_msg

    await self.status_msg.edit(content=self.status_msg.content.format(self.owner().mention))
    
    self.react_task = asyncio.create_task(self._add_reactions())
    self.loop_task = asyncio.create_task(self._react_wait_loop())
    self.auto_end_task = asyncio.create_task(self._auto_end_loop())
    self.key_alert_task = None
    self.key_alert_user = None
    pass
  
  async def _key_alert(self):
    await asyncio.sleep(HC_KEY_ALERT_DELAY)
    self.key_alert_task = None
    await self.ctx.send(HC_KEY_ALERT_MSG.format(self.owner().mention, self.key_alert_user.mention))

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
        if result.emoji in self.key_reacts:
          if self.key_alert_task is None:
            self.key_alert_user = user
            self.key_alert_task = asyncio.create_task(self._key_alert())
        await self._add_react(field_index, user)
      
      elif result.event_type == 'REACTION_REMOVE':
        if result.emoji in self.key_reacts:
          if self.key_alert_task is not None and user.id == self.key_alert_user.id:
            self.key_alert_task.cancel()
            self.key_alert_task = None
            self.key_alert_user = None
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
      
    self.panel_embed.fields[field_index].value=field_text
    await self.panel_msg.edit(embed=self.panel_embed)
  
  async def _remove_react(self, field_index, user):
    field_text = self.panel_embed.fields[field_index].value
    if field_text == 'None':
      await self.ctx.send("Error: Field text was None on reaction remove")
      return
    
    sections = field_text.split()
    sections = ['[' + sec + ']' if sec == user.mention else sec for sec in sections]
    field_text = ' '.join(sections)
    self.panel_embed.fields[field_index].value=field_text
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
      

  async def _do_convert(self, lazy: bool, dungeon_override=None):
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
    success = await self.manager.try_convert_hc_to_afk(self, voice_ch, lazy, location,
                                                       dungeon_override=dungeon_override)
    
    if not success:
      self.status = self.STATUS_GATHERING
  
  # This needs to return fast so the interaction doesn't fail.
  async def convert_to_afk(self, lazy:bool, dungeon_override=None):
    if self.bot.pending_shutdown:
      return

    if self.status != self.STATUS_GATHERING:
      return
    
    self.status = self.STATUS_CONVERTING
    asyncio.create_task(self._do_convert(lazy, dungeon_override))
    pass  
  pass

class HeadcountPanelTypeConvertSelect(discord.ui.Select):
  LAZY_VALUE = "lazy"
  NORMAL_VALUE = "normal"
  def __init__(self, headcount: Headcount, hm=False):
    super().__init__(placeholder=f'Convert ({"HM" if hm else "Non-HM"})', row=1, min_values=1, max_values=1)
    self.add_option(label=f"Convert to {'Hard Mode' if hm else 'Non-Hard Mode'}", value=self.NORMAL_VALUE)
    self.add_option(label=f"Convert to {'Hard Mode' if hm else 'Non-Hard Mode'} (Lazy)", value=self.LAZY_VALUE)
    self.headcount = headcount
    self.override = dungeons.HARDSHATTS_DNAME if hm else dungeons.SHATTERS_DNAME
    pass

  async def callback(self, interaction: discord.Interaction):
    if interaction.user.id != self.headcount.owner().id:
      await interaction.response.send_message(content="You are not the owner of this AFK check.", ephemeral=True)
      return
    
    await self.headcount.convert_to_afk(self.values[0] == self.LAZY_VALUE, dungeon_override=self.override)
    pass

class HeadcountPanelConvertLazyFollowup(discord.ui.View):
  def __init__(self, headcount: Headcount, dungeon_override=None):
    super().__init__(timeout=None)
    self.headcount = headcount
    self.dungeon_override = dungeon_override

  @discord.ui.button(label='Normal', style=discord.ButtonStyle.green, emoji=REACT_CHECK)
  async def convert_plain(self, button: discord.ui.Button, interaction: discord.Interaction):
    if interaction.user.id != self.headcount.owner().id or not is_manager(interaction.user):
      await interaction.response.send_message(content="You are not the owner of this AFK check.", ephemeral=True)
      return

    await interaction.message.delete()
    await self.headcount.convert_to_afk(False, dungeon_override=self.dungeon_override)
    pass
  
  @discord.ui.button(label='Lazy', style=discord.ButtonStyle.blurple, emoji=REACT_PLAY)
  async def convert_lazy(self, button: discord.ui.Button, interaction: discord.Interaction):
    if interaction.user.id != self.headcount.owner().id:
      await interaction.response.send_message(content="You are not the owner of this AFK check.", ephemeral=True)
      return
    
    await interaction.message.delete()
    await self.headcount.convert_to_afk(True, dungeon_override=self.dungeon_override)
    pass
  
  @discord.ui.button(label='Cancel', style=discord.ButtonStyle.gray, emoji=REACT_WASTE)
  async def abandon(self, button: discord.ui.Button, interaction: discord.Interaction):
    if interaction.user.id != self.headcount.owner().id:
      await interaction.response.send_message(content="You are not the owner of this AFK check.", ephemeral=True)
      return
    
    await interaction.message.delete()
    pass

class HeadcountPanelButton(discord.ui.Button):
  def __init__(self, headcount: Headcount, btype=0):
    # Btype:
    # 0 = Normal
    # 1 = Lazy
    # 2 = Convert to HM
    # 3 = Convert to Normal Shatters
    # 4 = Abandon
    if btype == 0:
      super().__init__(label='Convert', style=discord.ButtonStyle.green,
                       emoji=REACT_CHECK, timeout=None)
    
    elif btype == 1:
      super().__init__(label='Convert (Lazy)', style=discord.ButtonStyle.blurple,
                       emoji=REACT_PLAY, timeout=None)

    elif btype == 4:
      super().__init__(label='Abandon', style=discord.ButtonStyle.grey,
                       emoji=REACT_WASTE, timeout=None)
      
    self.headcount = headcount
    self.btype = btype

  async def callback(self, interaction: discord.Interaction):
    if interaction.user.id != self.headcount.owner().id or is_manager:
      await interaction.response.send_message(content="You are not the owner of this AFK check.", ephemeral=True)
      return
    
    if self.btype == 0:
      await self.headcount.convert_to_afk(False)

    elif self.btype == 1:
      await self.headcount.convert_to_afk(True)
    
    elif self.btype == 2:
      await interaction.response.send_message("What style of AFK check for your Hard Mode AFK?",
                                              view=HeadcountPanelConvertLazyFollowup(self.headcount,
                                                                                     dungeons.HARDSHATTS_DNAME))
      pass

    elif self.btype == 3:
      pass

    elif self.btype == 4:
      self.stop()
      await self.headcount.abandon()

class HeadcountPanelView(discord.ui.View):
  def __init__(self, headcount: Headcount, add_hmconv=None):
    super().__init__(timeout=None)
    self.headcount = headcount
    if add_hmconv is not None:
      self.add_item(HeadcountPanelTypeConvertSelect(headcount, add_hmconv))
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