from datetime import datetime
from shutil import move
from typing import Dict
import asyncio

import discord
from discord.ext import commands

import dungeons
from globalvars import get_section, get_vetraider_role, get_raider_role
import afk_check as ac
from headcount import Headcount
from hc_afk_helpers import log

class SectionAFKCheckManager:
  def __init__(self, guild: discord.Guild, sectionname):
    self.guild = guild
    self.section = get_section(guild.id, sectionname)
    self.active_afks: Dict[int, ac.AFKCheck] = {}
    self.active_hcs: Dict[int, Headcount] = {}
    pass
  
  def _log(self, logstr):
    log(f'[{self.guild.name}][{self.section.name}] {logstr}')
  
  async def try_create_afk( self, bot: commands.Bot,
                            ctx: commands.Context,
                            status_ch: discord.TextChannel,
                            voice_ch: discord.VoiceChannel, 
                            dungeon: dungeons.Dungeon,
                            lazy: bool,
                            location: str) -> bool:

    log(f'Attempting to create {"lazy" if lazy else ""} AFK check')
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
    
    self.active_hcs[ctx.author.id] = Headcount(self, bot, ctx, status_ch, dungeon)
    await self.active_hcs[ctx.author.id].start()
    return True
    
    pass
  
  async def try_convert_hc_to_afk(self, hc: Headcount, voice_ch: discord.VoiceChannel, lazy:bool, location: str) -> bool:
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
    role = get_vetraider_role(self.guild.id) if self.section.is_vet is True else get_raider_role(self.guild.id)
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
      if report:
        afk = self.active_afks[owner_id]
        info_ch: discord.TextChannel = self.guild.get_channel(self.section.run_info_ch)
        self._log(f'REPORT: {self.guild.name}, {self.section.name}, {self.section.run_info_ch}')
        if info_ch:
          if isinstance(info_ch, discord.TextChannel):
            info_embed = discord.Embed()
            info_embed.set_author(name=f'Run by {afk.owner().display_name}', icon_url = afk.owner().avatar.url)
            info_embed.set_footer(text=f'Run started at {afk.afk_embed.timestamp}')
            
            key_list = [u.mention for u in afk._keys()]
            early_list = [u.mention for u in afk.has_early_loc]
            raid_list = [f"{u.mention}`{u.display_name}`" for u in afk.joined_raiders]
            info_embed.add_field(inline=False, name='Keys', value=f'{key_list if len(key_list) > 0 else "None"}')
            info_embed.add_field(inline=False, name='Early', value=f'{early_list if len(early_list) > 0 else "None"}')
            info_embed.add_field(inline=False, name='Joined', value=f'{raid_list if len(raid_list) > 0 else "None"}')
            await info_ch.send(embed=info_embed)
          else:
            self._log(f'Info is not text: {info_ch.type}')
        else:
          self._log('No info ch')
              
      self.active_afks.pop(owner_id)
    except:
      pass
    self._log(f"Removed afk owned by {owner_id}.")
    
  async def handle_voice_update(self, member: discord.Member):
    self._log(f'User lounge/drag detected:')
    
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