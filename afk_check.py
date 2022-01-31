import asyncio
from code import interact
from typing import Optional, List, Dict
from datetime import datetime
import time

import discord
from discord import PermissionOverwrite, PartialEmoji
from discord.ext import commands

import dungeons
from globalvars import REACT_X, REACT_CHECK, REACT_PLAY
from globalvars import is_debug, get_staff_roles, get_nitro_role, get_early_roles, get_manager_roles
#from section_manager import SectionAFKCheckManager
from hc_afk_helpers import ConfirmView, get_field_index, ask_location
from tracking import add_runs_done

CHANNEL_OPENING_WARNING_TIME = 5
POST_AFK_TIME = 20
NITRO_EMOJI_ID = 931079445933096980
REACT_CHANGE_LOC='🗺'
AFK_AUTO_OPEN_TIMER = 4 *60 #Time till auto open if the AFK is lazy.
AFK_AUTO_END_TIMER = 6 *60# Time till auto end if the AFK wasn't lazy.
AFK_AUTO_END_TIMER_LAZY = 4 *60# Time till auto end if the AFK was lazy.
AFK_TIMER_INTERVAL = 15

class AFKCheck:
  STATUS_CLOSED = 0
  STATUS_OPENING = 1
  STATUS_OPEN = 2
  STATUS_POST = 3
  STATUS_ENDED = 4
  
  AFK_PANEL_INFO = "Raiders that have clicked one of the buttons and confirmed (if necessary) will show up below.\n"
  AFK_PANEL_INFO_OPEN = f"{REACT_PLAY} Press the `Open Channel` button to open the channel to all raiders.\n"
  AFK_PANEL_INFO_END = f"{REACT_CHECK} " + "Press the `End AFK` button{} to end the AFK check, moving players that haven't clicked the Join button out of the voice chat.\n"
  AFK_PANEL_INFO_ABORT = f"{REACT_X} Press the `Abort AFK` button to abort the AFK check, keeping players in the channel."
  
  # 1: join button emoji; 2: drag channel mentions
  AFK_DESC_LAZY = "\nOnly keys and important reacts will be moved in first. When the leader is ready, those who have already pressed {}Join will be moved in if they are in {} and there is room, then the voice channel will open."
  # 1: vc name; 2/3: join button emoji
  AFK_DESC_NOTLAZY = "\nJoin {} and press the {}Join button to participate.\nIf you don't press {}Join, you may be moved out at the end of the AFK check."
  AFK_DESC_WARN_RULES = "\n*(Clicking any button technically counts as joining as well)*\n\n**__Make sure to read #raiding-rules before joining a raid!__**"
  
  def __init__(self,  manager,
                      bot: commands.Bot,
                      ctx: commands.Context,
                      status_ch: discord.TextChannel,
                      voice_ch: discord.VoiceChannel,
                      dungeon: dungeons.Dungeon,
                      location: str):
    """Initializes an AFK check. Not that this does NOT start the AFK check.
    All this does is set up the AFK check to be started.

    Parameters:
      manager: The SectionAFKCheckManager that manages the afks in the section
      bot: Bot
      ctx: Context in which the AFK was started
      status_ch: The status channel where the AFK will be posted
      voice_ch: The voice channel to open/close
      dungeon: The associated dungeon
      location: The location of the run
    """
    self.manager = manager
    self.bot = bot
    self.ctx = ctx
    self.status_ch = status_ch
    self.voice_ch = voice_ch
    self.dungeon = dungeon
    self.location = location
    
    self.status = self.STATUS_CLOSED
    
    self.reacts_key = dungeon.get_key_react_emojis(self.bot)
    self.reacts_early = dungeon.get_early_react_emojis(self.bot)
    self.reacts_prim = dungeon.get_primary_react_emojis(self.bot)
    self.reacts_second = dungeon.get_secondary_react_emojis(self.bot)
    
    # Key poppers is a list of Members who have reacted with a Key button and confirmed.
    # Because there can be multiple key buttons, this is separate from the button reacts.
    self.key_poppers: List[discord.Member] = []

    # Keeps track of everyone who clicked a button.
    self.button_reacts: Dict[int, List[discord.Member]] = {}
    
    # Creates a list for each button react.
    for react in self.reacts_key + self.reacts_early + self.reacts_prim:
      self.button_reacts[react.id] = []
    
    self.joined_raiders: list[discord.Member] = []
    self.drag_raiders: list[int] = []
    self.has_early_loc: list[discord.Member] = []
    pass
  
  #########################################
  ### General Helpers
  #########################################

  def _log(self, logstr):
    if self.manager:
      self.manager._log(f'[afk:{self.owner().display_name}] {logstr}')

  def _accepting_joins(self):
    return self.status == self.STATUS_OPEN or self.status == self.STATUS_POST or self.status == self.STATUS_OPENING

  def _keys(self):
    l = []
    for r in self.reacts_key:
      l.extend(self.button_reacts[r.id])
    return l

  def owner(self):
    try:
      return self.actual_owner
    except AttributeError:
      return self.ctx.author

  #########################################
  ### Starting the AFK check
  #########################################

  def _build_afk_react_text(self):
    txt = ""
    for react in self.button_reacts:
      txt += f'{self.bot.get_emoji(react)}:  '
      for _ in range(len(self.button_reacts[react])):
        txt += REACT_CHECK + " "
      txt += '\n'
    return txt
  
  def _build_afk_list_react_text(self):
    txt = "None"
    for react in self.button_reacts:
      r = self.bot.get_emoji(react)
      if len(self.button_reacts[react]) > 0:
        for _ in range(len(self.button_reacts[react])):
          txt += str(r)
        txt += " "
    
    if len(txt) > len("None"):
      return txt[len("None"):]
    else: return txt
  
  def _build_afk_desc(self, lazy):
    ret = self.dungeon.get_afk_text(self.bot, self.owner(), self.voice_ch)
    if lazy:
      ret += self.AFK_DESC_LAZY.format(self.join_emoji, self.manager.get_move_channel_mentions(self.voice_ch.id))
    else:
      ret += self.AFK_DESC_NOTLAZY.format(self.voice_ch.mention, self.join_emoji, self.join_emoji)
    ret += self.AFK_DESC_WARN_RULES
    return ret
  
  def _build_afk_panel_desc(self, lazy):
    ret = self.AFK_PANEL_INFO
    if lazy:
      ret += self.AFK_PANEL_INFO_OPEN + self.AFK_PANEL_INFO_END.format(" after opening")
    else:
      ret += self.AFK_PANEL_INFO_END.format("")
    ret += self.AFK_PANEL_INFO_ABORT
    return ret
  
  AFK_FOOTER_AUTO_OPEN = 'This AFK check will open automatically in {}'
  AFK_FOOTER_AUTO_END = 'This AFK check will end automatically in {}'
  
  async def start_afk(self, lazy):
    here_ping = '`@here`' if is_debug() else '@here'
    self.join_emoji = self.bot.get_emoji(self.dungeon.react_portals[0])
    
    # Create auto-end/open timers
    
    # Create views
    if lazy:
      self.timer = asyncio.create_task(self._timer(AFK_AUTO_OPEN_TIMER, AFK_TIMER_INTERVAL, lazy))
      confirm_reacts = self.reacts_key + self.reacts_early + self.reacts_prim
      noconfirm_reacts = None
      footer_text = self.AFK_FOOTER_AUTO_OPEN.format(f'{int(AFK_AUTO_OPEN_TIMER / 60)} minutes')
    else:
      self.timer = asyncio.create_task(self._timer(AFK_AUTO_END_TIMER, AFK_TIMER_INTERVAL, lazy))
      confirm_reacts = self.reacts_key + self.reacts_early
      noconfirm_reacts = self.reacts_prim
      footer_text = self.AFK_FOOTER_AUTO_END.format(f'{int(AFK_AUTO_END_TIMER / 60)} minutes')
      await self._open_voice()
    
    # Create embeds    
    self.afk_embed = discord.Embed(description=self._build_afk_desc(lazy), timestamp=datetime.now())
    self.afk_embed.set_author(name=f'{self.dungeon.name} raid by {self.owner().display_name}', icon_url=self.owner().avatar.url)
    self.afk_embed.add_field(name='Reacts', value=self._build_afk_react_text())
    self.afk_embed.set_footer(text=footer_text)
    
    self.panel_embed = discord.Embed(description=self._build_afk_panel_desc(lazy))
    self.panel_embed.set_author(name='Control Panel', icon_url=self.owner().avatar.url)
    self.panel_embed.add_field(inline=False, name='Location', value=f'*{self.location}*')

    for react in self.reacts_key + self.reacts_early + self.reacts_prim:
      self.panel_embed.add_field(inline=True, name=dungeons.get_react_name(react.id, self.dungeon), value='None')
    
    self.panel_view = AFKCheckPanelView(self, lazy, self.reacts_key)
    self.afk_view = AFKCheckAFKView(self, self.dungeon, self.join_emoji, confirm_reacts, noconfirm_reacts)
    
    # Send messages
    afk_content = f"{here_ping} An AFK check has been started by {self.owner().mention} in {self.voice_ch.mention}."
    
    self.panel_msg = self.ctx.send(embed=self.panel_embed, view=self.panel_view)
    self.afk_msg = self.status_ch.send(content=afk_content, embed=self.afk_embed, view=self.afk_view)
    
    self.panel_msg: discord.Message = await self.panel_msg
    self.afk_msg: discord.Message = await self.afk_msg
    
    # Add reactions
    for react in self.reacts_second:
      await self.afk_msg.add_reaction(react)
    
    pass

  #########################################
  ### AFK Status Helpers
  #########################################

  async def _timer(self, time_wait: int, interval: int, lazy):
    time_left = time_wait - interval
    self._log(f'Timer: {time_wait/60}')
    await asyncio.sleep(interval)
    while time_left > 0:
      left_str = f'{int(time_left / 60)} minute(s) and {time_left % 60} seconds.'
      self._log(f'Timer: {time_left}')
      
      if lazy:
        self.afk_embed.set_footer(text=self.AFK_FOOTER_AUTO_OPEN.format(left_str))
      else:
        self.afk_embed.set_footer(text=self.AFK_FOOTER_AUTO_END.format(left_str))
        
      await self.afk_msg.edit(embed=self.afk_embed)
      await asyncio.sleep(interval)
      time_left -= interval
      
    if lazy:
      asyncio.create_task(self.open_channel())
    else:
      asyncio.create_task(self.close())
    pass
  
  async def _open_voice(self):
    self.status = self.STATUS_OPEN
    
    overwrite = PermissionOverwrite()
    overwrite.view_channel = True
    overwrite.connect = True
      
    await self.voice_ch.set_permissions(self.manager.get_raider_role(), overwrite=overwrite)
    pass
  
  async def _close_voice(self):
    overwrite = PermissionOverwrite()
    overwrite.view_channel = True
    overwrite.connect = False
    
    await self.voice_ch.set_permissions(self.manager.get_raider_role(), overwrite=overwrite)
  
  async def _update_afk_reacts(self, react_emoji, user):
    # update afk panel
    self.afk_embed._fields[0]['value'] = self._build_afk_react_text()
    await self.afk_msg.edit(embed=self.afk_embed)
    
    # update control panel
    field_index = 1 + get_field_index(react_emoji, [self.reacts_key, self.reacts_early, self.reacts_prim])
    if field_index == 0:
      await self.ctx.send(f"Error: field_index of {react_emoji} was -1")
      
    else:
      if self.panel_embed._fields[field_index]['value'] == 'None':
        self.panel_embed._fields[field_index]['value'] = user.mention
        
      else:
        self.panel_embed._fields[field_index]['value'] += f" {user.mention}"
      
      await self.panel_msg.edit(embed=self.panel_embed)

  #########################################
  ### AFK Status Modifiers
  #########################################

  async def open_channel(self):    
    self._log("Channel opening.")
    
    self.timer.cancel()
    
    self.panel_embed.description = self._build_afk_panel_desc(False)
    await self.panel_msg.edit(embed=self.panel_embed)
    
    self.afk_embed.set_footer(text='AFK check opening...')
    await self.afk_msg.edit(embed=self.afk_embed)
    
    self._log("Checking joined members...")
    for member in self.joined_raiders:
      drag_ch = self.manager.get_section_drag(self.voice_ch.id)
      ids = [self.manager.get_section_lounge().id, drag_ch.id if drag_ch else None]
      if member.voice and member.voice.channel and member.voice.channel.id in ids:
        self._log(f"- {member.display_name} found and attempted to move.")
        await self._move_in_user(member)
      else:
        self._log(f"- {member.display_name} not found.")
    
    self.status = self.STATUS_OPENING
    
    opening_embed = discord.Embed(description='Click Join now to get moved in!')
    opening_embed.set_author(name='Channel Opening in', icon_url=self.owner().avatar.url)
    opening_msg = await self.status_ch.send(content='Channel opening!', embed=opening_embed)
    
    for i in range(CHANNEL_OPENING_WARNING_TIME):
      opening_embed._author['name'] = f"Channel Opening in {CHANNEL_OPENING_WARNING_TIME - i}..."
      await opening_msg.edit(embed=opening_embed)
      await asyncio.sleep(1)
    
    self._log("Channel open.")
    await self._open_voice()
    
    self.timer = asyncio.create_task(self._timer(AFK_AUTO_END_TIMER_LAZY, AFK_TIMER_INTERVAL, False))
    
    opening_embed._author['name'] = 'Channel opened!'
    await opening_msg.edit(embed=opening_embed)
    await opening_msg.delete(delay=5)
    
    self.afk_view.change_to_noconfirm(self.reacts_prim)
    self.afk_embed.description = self._build_afk_desc(False)
    self.afk_embed.set_footer(text=self.AFK_FOOTER_AUTO_END.format(f'{int(AFK_AUTO_END_TIMER_LAZY / 60)} minutes'))
    self.afk_embed.timestamp = datetime.now()
    await self.afk_msg.edit(embed=self.afk_embed, view=self.afk_view)
    pass

  AFK_ENDED_TEXT = f"This AFK check has been ended. Please wait for the next one to start."
  AFK_ENDED_KEY_THANK_TEXT = "\nThank you to {} for popping a key for us."
  AFK_ENDED_KEY_THANKS_TEXT = "\nThank you to {} for popping keys for us."
  AFK_TITLE_STARTED_TEXT = "{} by {} already started."
  
  async def update_location(self, newloc):
    self.location = newloc
    self.panel_embed._fields[0]['value'] = f"*{newloc}*"
    await self.panel_msg.edit(embed=self.panel_embed)
    
    for user in self.has_early_loc:
      try:
        await user.send(f'The location for the raid has been changed to `{self.location}`')
      except:
        pass
  
  async def _end_afk(self):
    self._log("End AFK")
    self.status = self.STATUS_ENDED
    self.afk_view.stop()
    
    self.afk_embed.description = self.AFK_ENDED_TEXT
    self.afk_embed.set_footer(text='This AFK check ended ')
    self.afk_embed.timestamp = datetime.now()
    
    # Thank any key poppers we have
    if len(self.key_poppers) > 0:
      if len(self.key_poppers) == 1:
        self.afk_embed.description += self.AFK_ENDED_KEY_THANK_TEXT.format(self.key_poppers[0].mention)

      else:
        popper_thank = ""

        if len(self.key_poppers) == 2:
          popper_thank = f"{self.key_poppers[0].mention} and {self.key_poppers[1].mention}"

        else:
          for popper in self.key_poppers[:-1]:
            popper_thank += f"{popper.mention}, "
          popper_thank += f"and {self.key_poppers[-1].mention}"
          
        self.afk_embed.description += self.AFK_ENDED_KEY_THANKS_TEXT.format(popper_thank)
    
    # Set the author name to the started title.
    self.afk_embed._author['name'] = self.AFK_TITLE_STARTED_TEXT.format(self.dungeon.name, self.owner().display_name)
    
    
    # update messages
    self.panel_embed.description = 'This AFK check has ended.'
    await self.afk_msg.edit(content='This AFK has ended.', embed=self.afk_embed, view=None)
    await self.panel_msg.edit(embed=self.panel_embed)
    
    await self.manager.remove_afk(self.owner().id, report=self.dungeon.code == dungeons.SHATTERS_DNAME)

    # Add runs to those who are currently in the voice chat.
    add_runs_done(self.manager.guild.id, self.dungeon.code, self.voice_ch.members, self.owner())

  async def close(self):
    self._log("Close channel")
    self.status = self.STATUS_POST
    await self._close_voice()
    self.timer.cancel()
    
    # Move out everyone that didn't click join, is not a staff member, and isn't a bot.
    staff_roles = get_staff_roles()
    lounge_ch = self.ctx.guild.get_channel(self.manager.section.lounge_ch)
    for member in self.voice_ch.members:
      if member in self.joined_raiders or member.bot:
        continue
      
      staff = False
      for role in member.roles:
        if role.name in staff_roles:
          staff = True
      
      if staff is False:
        # they don't have a staff role and they didn't click join, move them out
        # they could've moved out in the time it took to move other members out
        # so recheck that they're in vc
        try:
          if member.voice and member.voice.channel and member.voice.channel.id == self.voice_ch.id:
            await member.move_to(lounge_ch, reason='Did not click Join.')
        except:
          pass
    
    self.afk_view.strip_all_but_join()
    
    self.afk_embed.description = f"If you've been moved out or would like to join, join {self.manager.get_move_channel_mentions(self.voice_ch.id)} and press `Join` to get moved back in."
    self.afk_embed.set_field_at(0, name='Reacts', value=self._build_afk_list_react_text())
    self.afk_embed.set_footer(text='This AFK check is ending...')
    await self.afk_msg.edit(view=AFKCheckAFKView(self, self.dungeon, self.join_emoji))
    
    for i in range(POST_AFK_TIME):
      self.afk_embed._author['name'] = f"AFK Ending in {POST_AFK_TIME - i} seconds..."
      await self.afk_msg.edit(embed=self.afk_embed)
      await asyncio.sleep(1)
    
    await self._end_afk()
    pass
  
  async def abort(self):
    self._log("Abort afk")
    self.afk_embed.set_field_at(0, name='Reacts', value=self._build_afk_list_react_text())
    self.timer.cancel()
    await self._close_voice()
    await self._end_afk()
    pass
  
  #########################################
  ### Button Press Helpers
  #########################################

  MOVE_SUCCESS = 0      # The user was successfully moved in.
  MOVE_NOT_IN_VOICE = 1 # The user was not in a voice channel.
  MOVE_ALREADY_IN = 2   # The user was already in the correct voice channel.
  MOVE_CAPPED = 3       # The destination channel was at its cap, and force was False.
  async def _move_in_user(self, user: discord.Member, force:bool=False):
    if user.voice and user.voice.channel:
      if user.voice.channel.id != self.voice_ch.id:
        if self.voice_ch.user_limit < len(self.voice_ch.members) or force:
          try:
            await user.move_to(self.voice_ch)
            return self.MOVE_SUCCESS
          except:
            return self.MOVE_NOT_IN_VOICE

        return self.MOVE_CAPPED

      return self.MOVE_ALREADY_IN

    elif self.voice_ch.user_limit >= len(self.voice_ch.members) and not force:
      return self.MOVE_CAPPED

    return self.MOVE_NOT_IN_VOICE
    
  # True:   They were added.
  # False:  They already were added.
  def _user_join(self, user:discord.Member) -> bool:
    if user not in self.joined_raiders:
      self._log(f"New user joined: {user.display_name}")
      self.joined_raiders.append(user)
      return True
    
    self._log(f"Return user joined: {user.display_name}")
    return False

  #########################################
  ### Button Press Acknowledgements
  #########################################

  # The default maximum confirms for normally non-early/non-confirming buttons.
  # Only used in lazy AFKs.
  AFK_PRIMARY_CONFIRM_MAX = 2
  
  ACK_BUTTON_SUCCESS = False
  ACK_BUTTON_DRAG = True
  ACK_BUTTON_CAPPED = 2
  ACK_BUTTON_CONFIRMED = 3
  ACK_BUTTON_MUST_BE_IN_VC = 4
  async def ack_button(self, react_emoji: discord.PartialEmoji, user:discord.Member, confirmed=None):
    """Acknowledges a button press.

    Parameters:
      react_emoji: The emoji that the user react with.
      user: The member that clicked the button.
      confirmed: If the user had to confirm the button press or not.

    Returns:
      ACK_BUTTON_SUCCESS: If the interaction fully succeeded. If confirmed, the person was in vc or was dragged in, if not confirmed the person was in VC.
      ACK_BUTTON_DRAG: If the user needs to join a voice channel to get dragged in. Only returned if the button needed confirming. 
      ACK_BUTTON_CAPPED: If the button has reached maximum capacity for early location / drags. Only returned if the button needed confirming.
      ACK_BUTTON_CONFIRMED: If the user has already confirmed this button. Only returned if the button needed confirming.
      ACK_BUTTON_MUST_BE_IN_VC: If the user must be in the voice channel to react with the button. Only returned if the button doesn't need confirming.
      [str]: The location to give. This is only returned if 1) the button was confirmed, 2) the button was not capped, and 3) the user has any required roles to get early location.
    """
    print('ack button afk')
    self._log(f'Button: E:{react_emoji.name} U:{user.display_name} C:{confirmed} J:{user.id in self.drag_raiders}')

    # We also treat this as a "join" of sorts.
    self._user_join(user) 
    
    # Check to see if they already confirmed.
    if user in self.button_reacts[react_emoji.id]:
      return self.ACK_BUTTON_CONFIRMED
    
    give_location = False
    
    # The only things that can be returned in this if/else are errors.
    if confirmed is True:
      if react_emoji in self.reacts_key:
        if self.dungeon.max_keys == 0 or len(self.key_poppers) < self.dungeon.max_keys:
          self.key_poppers.append(user)
          self._log(f'Key #{len(self.key_poppers)} accepted. (Max {self.dungeon.max_keys})')
        else:
          self._log(f'Key denied. (Max of {self.dungeon.max_keys} reached)')
          return self.ACK_BUTTON_CAPPED
        
        # If we reach here, they need location.
        give_location = True
        
      elif react_emoji in self.reacts_early:
        # check for cap / necessary role
        needed = self.dungeon.react_early[react_emoji.id]
        self._log(f'Checking early react: {needed[0]} {needed[1]}')

        # needed[0] is the maximum for this early react.
        # needed[1] is the name of the role that's required.
        if len(self.button_reacts[react_emoji.id]) >= needed[0]:
          return self.ACK_BUTTON_CAPPED

        # if no role is needed then simply give them early location.
        if needed[1] is None or needed[1] in [role.name for role in user.roles]:
          give_location = True
      
      else:
        # This is only reached if the AFK check is lazy and the button pressed was a primary react.
        if len(self.button_reacts[react_emoji.id]) >= self.AFK_PRIMARY_CONFIRM_MAX:
          return self.ACK_BUTTON_CAPPED
    else:
      # Non-confirmed reacts only require that people be in the VC.
      # If they are, then they succeed. That easy. 
      if user not in self.voice_ch.members:
        return self.ACK_BUTTON_MUST_BE_IN_VC
    
    # Add them
    self.button_reacts[react_emoji.id].append(user)
    await self._update_afk_reacts(react_emoji, user)

    # If they confirmed, move them in to voice chat.
    if confirmed and user.id not in self.drag_raiders:
      self.drag_raiders.append(user.id)
      await self._move_in_user(user, force=True)
    
    if give_location:
      # Keeps track of who has location so we can update them if it changes.
      if user not in self.has_early_loc:
        self.has_early_loc.append(user)
      return self.location
    
    # Returns TRUE if the need a drag.
    # FALSE if they don't need one.
    return self.status != self.STATUS_OPEN and user not in self.voice_ch.members
    pass
  
  ACK_JOIN_SUCCESS = 0
  ACK_JOIN_NEED_DRAG = 1
  ACK_JOIN_SAY_NOTHING = 2
  ACK_JOIN_WAIT = 3
  ACK_JOIN_CANNOT_JOIN = 4
  async def ack_join(self, user: discord.Member):
    """Acknowledges clicking the Join button.

    Parameters:
      user: the member that clicked the button

    Returns:
      ACK_JOIN_SUCCESS: They were either in VC and not joined, or they were moved in and joined.
      ACK_JOIN_NEED_DRAG: They could not be dragged in, but will be dragged in once the VC opens.
      ACK_JOIN_SAY_NOTHING: They've already clicked the join button and they're in the voice channel.
      ACK_JOIN_WAIT: They've already clicked the join button, they aren't in the voice channel, and the voice channel is not open.
      ACK_JOIN_CANNOT_JOIN: They aren't in the voice channel and cannot join the raid due to the run being capped.
    """
    for early_role in get_early_roles(self.ctx.guild.id):
      if early_role in [role.id for role in user.roles]:
        await self._move_in_user(user, force=True)
        if user.id not in self.drag_raiders:
          self.drag_raiders.append(user.id)
        if user not in self.has_early_loc:
          self.has_early_loc.append(user)
        return self.location if self._user_join(user) else self.ACK_JOIN_SAY_NOTHING

    if self._user_join(user):
      # First click
      if self._accepting_joins():
        move_res = await self._move_in_user(user)
        
        if move_res == self.MOVE_CAPPED:
          return self.ACK_JOIN_CANNOT_JOIN

        if move_res == self.MOVE_NOT_IN_VOICE:
          return self.ACK_JOIN_NEED_DRAG
        
        return self.ACK_JOIN_SUCCESS

      # If we aren't accepting joins but they're already in the voice channel, success
      elif user.voice and user.voice.channel and user.voice.channel.id == self.voice_ch.id:
        return self.ACK_JOIN_SUCCESS
      
      # They will be dragged later.
      return self.ACK_JOIN_NEED_DRAG
    
    else:
      # Repeat click
      if self._accepting_joins():
        move_res = await self._move_in_user(user)
        
        if move_res == self.MOVE_CAPPED:
          return self.ACK_JOIN_CANNOT_JOIN
        
        return self.ACK_JOIN_SAY_NOTHING
      
      # If we aren't accepting joins but they're already in the voice channel, say nothing
      elif user.voice and user.voice.channel and user.voice.channel.id == self.voice_ch.id:
        return self.ACK_JOIN_SAY_NOTHING
      
      return self.ACK_JOIN_WAIT   
  
  ACK_NITRO_FAIL = 0
  ACK_NITRO_SUCCESS = 1
  ACK_NITRO_REPEAT = 2
  async def ack_nitro(self, user: discord.Member) -> int:
    """Acknowledges a nitro button.

    Parameters:
      user: The person who clicked the button.
    
    Returns:
      ACK_NITRO_FAIL: The user doesn't have an appropriate role.
      ACK_NITRO_SUCCESS: The user has an appropriate role and this is their first click.
      ACK_NITRO_REPEAT: The user has an appropriate role and this is a repeat click.
    """
    nitro_role = get_nitro_role(self.ctx.guild.id)
    early_roles = get_early_roles(self.ctx.guild.id)
    if nitro_role != '' or len(early_roles) > 0:
      nitro_role = self.ctx.guild.get_role(nitro_role)
      early = False
      for role in early_roles:
        if role in [x.id for x in user.roles]:
          early = True
          break
      
      if early or (nitro_role and nitro_role in user.roles):
        self._user_join(user)
        await self._move_in_user(user, force=True)

        # this isn't 100% perfect but it works
        if user not in self.has_early_loc:
          self.has_early_loc.append(user)

        if user.id not in self.drag_raiders:
          self.drag_raiders.append(user.id)
          return self.ACK_NITRO_SUCCESS
        
        return self.ACK_NITRO_REPEAT
    return self.ACK_NITRO_FAIL

class AFKCheckPanelEndButton(discord.ui.Button):
  STYLE = discord.ButtonStyle.green
  LABEL = 'End AFK Check'
  EMOJI = REACT_CHECK
  
  def __init__(self):
    super().__init__(style=self.STYLE, label=self.LABEL, emoji=self.EMOJI)
    
  async def callback(self, interaction: discord.Interaction):
    assert self.view is not None
    if interaction.user.id != self.view.afk_check.owner().id:
      for role in get_manager_roles():
        if role in [r.name for r in interaction.user.roles]:
          await self.view.close_afk(interaction)

      await interaction.response.send_message(content="You are not the owner of this AFK check.")

    await self.view.close_afk(interaction)

class AFKCheckPanelOpenButton(discord.ui.Button):  
  def __init__(self):
    super().__init__(style=discord.ButtonStyle.blurple, label='Open Channel', emoji=REACT_PLAY)
    self.click = False
    
  async def callback(self, interaction: discord.Interaction):
    assert self.view is not None
    if interaction.user.id != self.view.afk_check.owner().id:
      manager = False
      for role in get_manager_roles():
        if role in [r.name for r in interaction.user.roles]:
          break

      if not manager:
        await interaction.response.send_message(content="You are not the owner of this AFK check.", ephemeral=True)
    
    if self.click:
      if self.view.afk_check.status == AFKCheck.STATUS_OPENING:
        await interaction.response.send_message(content='Please wait for the AFK to open first.', ephemeral=True)
      else:
        await self.view.close_afk(interaction)
    
    else:
      self.label = AFKCheckPanelEndButton.LABEL
      self.style = AFKCheckPanelEndButton.STYLE
      self.emoji = AFKCheckPanelEndButton.EMOJI
      self.click = True
      await interaction.response.edit_message(view=self.view)
      await self.view.open_channel(interaction)
  
  pass

class AFKCheckPanelAbortButton(discord.ui.Button):
  def __init__(self):
    super().__init__(style=discord.ButtonStyle.red, label='Abort', emoji=REACT_X)
    
  async def callback(self, interaction: discord.Interaction):
    assert self.view is not None
    
    if interaction.user.id != self.view.afk_check.owner().id:
      for role in get_manager_roles():
        if role in [r.name for r in interaction.user.roles]:
          await self.view.abort_afk(interaction)

      await interaction.response.send_message(content="You are not the owner of this AFK check.")
    
    await self.view.abort_afk(interaction)

class AFKCheckPanelLocationButton(discord.ui.Button):
  def __init__(self):
    super().__init__(style=discord.ButtonStyle.gray, label='Update Loc.', emoji=REACT_CHANGE_LOC)
  
  async def callback(self, interaction: discord.Interaction):
    assert self.view is not None
    
    if interaction.user.id != self.view.afk_check.owner().id:
      await interaction.response.send_message(content="You are not the owner of this AFK check.")
      
    asyncio.create_task(self.view.update_loc())

class AFKCheckPanelView(discord.ui.View):
  def __init__(self, afk_check: AFKCheck, lazy: bool, requests: list):
    super().__init__(timeout=None)
    self.afk_check = afk_check
    
    if lazy:
      self.add_item(AFKCheckPanelOpenButton())
    else:
      self.add_item(AFKCheckPanelEndButton())
    
    self.add_item(AFKCheckPanelLocationButton())
    self.add_item(AFKCheckPanelAbortButton())
  
  async def open_channel(self, interaction: discord.Interaction):
    await self.afk_check.open_channel()
    pass
  
  async def close_afk(self, interaction: discord.Interaction):
    self.stop()
    await interaction.response.edit_message(view=None)   
    await self.afk_check.close()
  
  async def abort_afk(self, interaction: discord.Interaction):
    self.stop()
    await interaction.response.edit_message(view=None)
    await self.afk_check.abort()
  
  async def update_loc(self):
    newloc = await ask_location(self.afk_check.bot, ctx=self.afk_check.ctx)
    if newloc:
      await self.afk_check.update_location(newloc)
  
  pass

AFK_RSP_TELL_DRAG_OPEN = "\nWhen the AFK check opens, you will be dragged into the channel if you're in {} and there is room."
AFK_RSP_TELL_DRAG_NOW = "\nIf you aren't already in the voice channel, join {} to be moved in."
AFK_RSP_TELL_LOCATION = "\nThe raid location is __**{}**__."

AFK_RSP_CONFIRM = "Confirm: You are bringing a {}?\nConfirming and not bringing this will result in a suspension."
AFK_RSP_CONFIM_CANCELLED = 'Cancelled.'
AFK_RSP_CONFIRM_TIMEOUT = "Confirmation timed out. Please try again."
AFK_RSP_CONFIRM_CAPPED = "\nSadly, we've hit the cap for this react. Feel free to bring it, but you won't be moved in or given early location for it."
AFK_RSP_ALREADY_CONFIRMED = "You've already confirmed and cannot confirm again!"
AFK_RSP_ALREADY_CLICKED = "You've already clicked this button!"

AFK_RSP_WAIT = "Please wait for the channel to open."
AFK_RSP_MUST_BE_IN_VC = "You must be in the voice channel to react with {}."
AFK_RSP_CANNOT_JOIN = "Sadly you cannot join the raid at this time. Please wait for the next raid to start or for a spot to open up."

AFK_RSP_THANKS_PARTICIPATE = "Thanks for participating!"
AFK_RSP_THANKS_CONFIRM = "Thank you for confirming."
AFK_RSP_THANKS_NOCONF = "Thank you!"
AFK_RSP_THANKS_NITRO = "Thanks for supporting the server!" + AFK_RSP_TELL_DRAG_NOW
AFK_RSP_THANKS_KEYLITE = "Thanks for participating! If you aren't already in the voice channel, join {} to get dragged in."

class AFKCheckAFKButton(discord.ui.Button):
  def __init__(self, label, emoji:PartialEmoji, style, confirm:bool):
    super().__init__(label=label, emoji=emoji, style=style)
    self.emoji = emoji
    self.confirm = confirm
    
  async def callback(self, interaction: discord.Interaction):
    drag_channel_mentions = self.view.afk_check.manager.get_move_channel_mentions(self.view.afk_check.voice_ch.id)
    
    print(f'button click {self.emoji.name}')

    ##########
    # Nitro
    if self.confirm == 'nitro':
      nitro = await self.view.ack_nitro(interaction.user)
      
      if nitro == AFKCheck.ACK_NITRO_SUCCESS:
        await interaction.response.send_message(content=AFK_RSP_THANKS_NITRO.format(drag_channel_mentions), ephemeral=True)
    
    elif self.confirm == 'join':
      drag = await self.view.ack_join(interaction.user)
      
      if drag == AFKCheck.ACK_JOIN_SAY_NOTHING:
        return
      
      rsp = AFK_RSP_THANKS_PARTICIPATE
      if drag == AFKCheck.ACK_JOIN_NEED_DRAG:
        rsp += AFK_RSP_TELL_DRAG_OPEN.format(drag_channel_mentions)
        
      elif drag == AFKCheck.ACK_JOIN_WAIT:
        rsp = AFK_RSP_WAIT
        
      elif drag == AFKCheck.ACK_JOIN_CANNOT_JOIN:
        rsp = AFK_RSP_CANNOT_JOIN
        
      # Keylite gets loc upon joining
      elif isinstance(drag, str):
        rsp = AFK_RSP_THANKS_KEYLITE.format(drag_channel_mentions) + AFK_RSP_TELL_LOCATION.format(drag)
      
      await interaction.response.send_message(content=rsp, ephemeral=True)
    
    elif self.confirm:
      confirm_view = ConfirmView()
      await interaction.response.send_message(content=AFK_RSP_CONFIRM.format(self.label), view=confirm_view, ephemeral=True)
      await confirm_view.wait()
      
      if confirm_view.value is None:
        await interaction.edit_original_message(content=AFK_RSP_CONFIRM_TIMEOUT, view=None)
        return
      
      elif confirm_view.value:
        drag = await self.view.ack_button(self.emoji, interaction.user, True)
        rsp = AFK_RSP_THANKS_CONFIRM
        
        if drag is AFKCheck.ACK_BUTTON_CONFIRMED:
          rsp = AFK_RSP_ALREADY_CONFIRMED
        
        elif drag == AFKCheck.ACK_BUTTON_CAPPED:
          rsp += AFK_RSP_CONFIRM_CAPPED
        
        elif drag is True or isinstance(drag, str):
          rsp += AFK_RSP_TELL_DRAG_NOW.format(drag_channel_mentions)
          if isinstance(drag, str):
            rsp += AFK_RSP_TELL_LOCATION.format(drag)
          
        await interaction.edit_original_message(content=rsp, view=None)
        
      else:
        await interaction.edit_original_message(content=AFK_RSP_CONFIM_CANCELLED, view=None)
    
    else:
      drag = await self.view.ack_button(self.emoji, interaction.user, False)
      
      rsp = ""
      if drag is AFKCheck.ACK_BUTTON_MUST_BE_IN_VC:
        rsp = AFK_RSP_MUST_BE_IN_VC.format(self.label)
      else:
        rsp = AFK_RSP_ALREADY_CLICKED if drag is AFKCheck.ACK_BUTTON_CONFIRMED else AFK_RSP_THANKS_NOCONF
      await interaction.response.send_message(content=rsp, ephemeral=True)
    
    pass
    
  pass

class AFKCheckAFKView(discord.ui.View):
  def __init__(self, afk_check: AFKCheck, dungeon:dungeons.Dungeon, join_emoji: PartialEmoji, add_confirm: Optional[List[PartialEmoji]] = None, add_noconfirm: Optional[List[PartialEmoji]] = None):
    super().__init__(timeout=None)
    self.afk_check = afk_check
    
    self.add_item(AFKCheckAFKButton(label='Join', emoji=join_emoji, style=discord.ButtonStyle.blurple, confirm='join'))
    
    if add_confirm:
      for add in add_confirm:
        label = dungeons.get_react_name(add.id, dungeon)
        self.add_item(AFKCheckAFKButton(label=label, emoji=add, style=discord.ButtonStyle.green, confirm=True))
        
    if add_noconfirm:
      for add in add_noconfirm:
        label = dungeons.get_react_name(add.id, dungeon)
        self.add_item(AFKCheckAFKButton(label=label, emoji=add, style=discord.ButtonStyle.grey, confirm=False))

    if add_confirm or add_noconfirm:
      self._add_nitro()
      
  def _add_nitro(self):
    nitro = self.afk_check.bot.get_emoji(NITRO_EMOJI_ID)
    self.add_item(AFKCheckAFKButton(label='Nitro', emoji=nitro, style=discord.ButtonStyle.blurple, confirm='nitro'))
  
  async def ack_join(self, user):
    print('view ack join')
    return await self.afk_check.ack_join(user)
    
  async def ack_button(self, react_emoji, user, confirm=None):
    print('view ack button')
    return await self.afk_check.ack_button(react_emoji, user, confirm)
  
  async def ack_nitro(self, user):
    return await self.afk_check.ack_nitro(user)
  
  def strip_all_but_join(self):
    remove = self.children[1:]
    for child in remove:
      self.remove_item(child)
      
  def change_to_noconfirm(self, items: List[PartialEmoji]):    
    for child in self.children:
      if child.emoji in items:
        child.style = discord.ButtonStyle.grey
        child.confirm = False
        
