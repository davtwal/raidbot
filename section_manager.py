from datetime import datetime
from typing import Dict, Tuple
import asyncio

import discord
from discord.ext import commands

import dungeons
import afk_check as ac
from globalvars import RaidingSection
import headcount as hcm

class SectionAFKCheckManager:
  def __init__(self, bot: commands.Bot, guild: discord.Guild, sectionname):
    self.bot = bot
    self.guild = guild
    self.section: RaidingSection = self.bot.get_section(guild.id, sectionname)
    # Keeps track of actively running AFK checks.
    # Key: Owner's ID. Value: AFK check.
    self.active_afks: Dict[int, ac.AFKCheck] = {}

    # Keeps track of actively running headcounts.
    # Key: Owner's ID. Value: Headcount.
    self.active_hcs: Dict[int, hcm.Headcount] = {}

    # Keeps track of the previous AFK checks' owners for each voice channel.
    # This is used for deaf checking, as AFK checks are removed once they are ended
    # but deafen checking is needed _after_ the AFK ends.
    # Key: Voice channel ID. Value: Tuple(Last AFK check's owner's ID, last AFK check datetime)
    self.previous_afks: Dict[int, Tuple[int, datetime]] = {}
    pass
  
  def _log(self, logstr):
    self.bot.log(f'[{self.guild.name}][{self.section.name}] {logstr}')
  
  async def try_create_afk( self, bot: commands.Bot,
                            ctx: commands.Context,
                            status_ch: discord.TextChannel,
                            voice_ch: discord.VoiceChannel, 
                            dungeon: dungeons.Dungeon,
                            lazy: bool,
                            location: str) -> bool:

    self._log(f'Attempting to create {"lazy" if lazy else ""} AFK check')
    if ctx.author.id in self.active_afks:
      self._log(f'{ctx.author.display_name} attempted to create AFK while already having one.')
      await ctx.send("You already have an AFK check running!")
      return False
    
    if ctx.author.id in self.active_hcs:
      if dungeon.code == self.active_hcs[ctx.author.id].dungeon.code:
        # convert it instead
        self._log(f'{ctx.author.display_name} used afk command to convert afk')
        return await self.try_convert_hc_to_afk(self.active_hcs[ctx.author.id], voice_ch, lazy, location)
      else:
        self._log(f'{ctx.author.display_name} tried to afk command while diff dung hc')
        await ctx.send("You already have a headcount up for a different dungeon.")
        return False
    
    for auth_id in self.active_afks:
      if self.active_afks[auth_id].dungeon.code == dungeon.code:
        self._log(f'{ctx.author.display_name} attempted to create a {dungeon.name} AFK while one exists.')
        await ctx.send(f"There is already a(n) {dungeon.name} AFK check up in this section.")
        return False
    
    
    self._log(f'{ctx.author.display_name} started {dungeon.name} raid.')
    
    self.active_afks[ctx.author.id] = ac.AFKCheck(self, bot, ctx, status_ch, voice_ch, dungeon, location)
    
    await self.active_afks[ctx.author.id].start_afk(lazy)
    return True
    pass
  
  async def try_create_headcount(self, bot: commands.Bot,
                                 ctx: commands.Context,
                                 status_ch: discord.TextChannel,
                                 dungeon: dungeons.Dungeon):
    if ctx.author.id in self.active_hcs:
      self._log(f'{ctx.author.display_name} tried to create a headcount while they had one up already.')
      await ctx.send('You already have a headcount up!')
      return False
    
    if ctx.author.id in self.active_afks:
      self._log(f'{ctx.author.display_name} tried to creat a headcount while they had an AFK up')
      await ctx.send('You already have an AFK up! Why make a headcount???')
      return False
    
    for auth_id in self.active_hcs:
      if self.active_hcs[auth_id].dungeon.code == dungeon.code:
        self._log(f'{ctx.author.display_name} attempted to create a {dungeon.name} heacount while one exists.')
        await ctx.send(f'There is already a(n) {dungeon.name} headcount up in this section!')
        return False
    
    self.active_hcs[ctx.author.id] = hcm.Headcount(self, bot, ctx, status_ch, dungeon)
    
    try:
      await self.active_hcs[ctx.author.id].start()
      return True
    except Exception as ex:
      await ctx.send(f"An error occurred while starting up the headcount: ({type(ex).__name__}) {ex.args}")
      del self.active_hcs[ctx.author.id]
      return False
    pass
  
  async def try_convert_hc_to_afk(self, hc: hcm.Headcount, voice_ch: discord.VoiceChannel, lazy:bool, location: str) -> bool:
    for auth_id in self.active_afks:
      if self.active_afks[auth_id].dungeon.code == hc.dungeon.code:
        if self.active_afks[auth_id].status != ac.AFKCheck.STATUS_POST:
          self._log(f'{hc.owner().display_name} attempted to create a {hc.dungeon.name} AFK while one exists.')
          await hc.ctx.send(f"There is already a(n) {hc.dungeon.name} AFK check up in this section. Please try again after it's closed.")
          return False

    await hc._finalize_convert(lazy)
    self.active_afks[hc.owner().id] = ac.AFKCheck(self, hc.bot, hc.ctx, hc.status_ch, voice_ch, hc.dungeon, location)
    await self.active_afks[hc.owner().id].start_afk(lazy)
    
    self.remove_headcount(hc.owner().id)
    return True
  
  def get_raider_role(self):
    role = self.bot.get_vetraider_role(self.guild.id) if self.section.is_vet is True else self.bot.get_raider_role(self.guild.id)
    self._log(f"Get Raider Role: {role} {self.section.is_vet}")
    return self.guild.get_role(role)
  
  def get_section_lounge(self):
    return self.guild.get_channel(self.section.lounge_ch)
  
  def get_section_drag(self, voice_ch_id):
    if self.section.drag_chs:    
      drag = self.guild.get_channel(self.section.drag_chs[self.section.voice_chs.index(voice_ch_id)])
      return drag
    
    else: 
      return None
  
  def has_relevant_afk(self, voice_chid: int) -> int:
    # Return's 0 if no relevant AFK check, or the owner's ID if there is one.
    if voice_chid in self.section.voice_chs:

      # Check active AFKs first. If there's an active AFK, that's more relevant than any previous one.
      for afk_owner in self.active_afks:
        if self.active_afks[afk_owner].voice_ch.id == voice_chid:
          return afk_owner

      # No active AFKs - check for previous ones.
      print(f'checking previous: {voice_chid} in {self.previous_afks.keys()}')
      if voice_chid in self.previous_afks.keys():
        if (datetime.now() - self.previous_afks[voice_chid][1]).total_seconds() <= self.bot.get_afk_relevanttime(self.guild.id):
          return self.previous_afks[voice_chid][0]
    
    return 0

  def get_move_channel_mentions(self, voice_ch_id):
    lounge = self.get_section_lounge()
    drag = self.get_section_drag(voice_ch_id)
    if drag:
      return f"{lounge.mention} or {drag.mention}"
    else:
      return lounge.mention
  #
  def transfer_afk(self, old_owner: discord.Member, new_owner: discord.Member):
    if old_owner.id not in self.active_afks or new_owner.id in self.active_afks:
      return False
    
    self.active_afks[new_owner.id] = self.active_afks.pop(old_owner.id)
    self.active_afks[new_owner.id].actual_owner = new_owner
    return True
    pass
  
  def remove_headcount(self, owner_id: int):
    self.active_hcs.pop(owner_id)
    self._log(f'Removed hc owned by {owner_id}.')
  
  async def remove_afk(self, owner_id: int, report: bool = False):
    try:
      afk = self.active_afks.pop(owner_id)
      self.previous_afks[afk.voice_ch.id] = (owner_id, datetime.now())
    except KeyError:
      self._log(f"Key error removing AFK by {owner_id}")
      return
    
    if report:
      info_ch: discord.TextChannel = self.guild.get_channel(self.section.run_info_ch)
      self._log(f'REPORT: {self.guild.name}, {self.section.name}, {self.section.run_info_ch}')

      if info_ch:
        if isinstance(info_ch, discord.TextChannel):
          info_embed = discord.Embed()
          info_embed.set_author(name=f'Run by {afk.owner().display_name}', icon_url = afk.owner().avatar.url)
          info_embed.set_footer(text=f'Run started at {afk.afk_embed.timestamp}')
          
          key_list = [u.mention for u in afk._keys()]
          early_list = [f"{u.mention}" for u in afk.has_early_loc]
          drag_list = [f"<@{u}>" for u in afk.drag_raiders]
          join_list = [f"{u.mention}" for u in afk.joined_raiders]
          raid_list = [f"{u.mention}" for u in afk.voice_ch.members]
          info_embed.add_field(inline=False, name='Keys', value=f'{key_list if len(key_list) > 0 else "None"}')
          info_embed.add_field(inline=False, name='Early', value=f'{early_list if len(early_list) > 0 else "None"}')
          info_embed.add_field(inline=False, name='Dragged', value=f'{drag_list if len(drag_list) > 0 else "None"}')
          
          if len(join_list) > 25 or len(raid_list) > 25:
            info_embed.add_field(inline=False, name='Joined 1', value=f'{join_list[:25]}')
            info_embed.add_field(inline=False, name='Joined 2', value=f'{join_list[25:]}')
            info_embed.add_field(inline=False, name='Raiders 1', value=f'{raid_list[:25]}')
            info_embed.add_field(inline=False, name='Raiders 2', value=f'{raid_list[25:]}')
          else:
            info_embed.add_field(inline=False, name='Joined', value=f'{join_list if len(join_list) > 0 else "None"}')
            info_embed.add_field(inline=False, name='Raiders', value=f'{raid_list if len(raid_list) > 0 else "None"}')
          
          for f in info_embed.fields:
            if len(str(f.value)) > 1024:
              f.value = "[[field to large to display]]"

          try:
            await info_ch.send(f'AFK Check: https://discord.com/channels/{self.guild.id}/{afk.ctx.channel.id}/{afk.panel_msg.id}',embed=info_embed)
            self._log(f'Run logged.')
          except discord.errors.Forbidden as err:
            self._log(f'Unable to log run (Forbidden): {err}')
          except discord.errors.HTTPException as err:
            self._log(f'Unable to log run (HTTP Error): {err}')
          except discord.errors.InvalidArgument as err:
            self._log(f'Unable to log run (Invalid Arg): {err}')

        else:
          self._log(f'Info is not text: {info_ch.type}')
          
      else:
        self._log('No info ch')

    self._log(f"Removed afk owned by {owner_id}.")
    
  async def handle_lounge_join(self, member: discord.Member):    
    # For each AFK check, check to see if that AFK wants to move in this member.
    for afk_owner in self.active_afks:   
      afk = self.active_afks[afk_owner]
      if member.id in afk.drag_raiders:
        
        #If they do, make sure they're either in lounge or in the correct drag channel.
        try:
          afk_voice_index = self.section.voice_chs.index(afk.voice_ch.id)
          drag_index = self.section.drag_chs.index(member.voice.channel.id)
          if afk_voice_index != drag_index:
            # They're in the wrong drag channel.
            return
        except (AttributeError, ValueError): #.index failed
          # In this scenario, they're in the lounge channel.
          pass
        
        await afk._move_in_user(member, force=True)       
    pass

  pass