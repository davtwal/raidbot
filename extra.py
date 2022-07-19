
import discord
import asyncio
from discord.ext import commands

from globalvars import get_veteran_roles, get_staff_roles, get_event_roles, get_manager_roles
from globalvars import confirmation

from shattersbot import ShattersBot

#from globalvars import get_vetchannels, get_clean_links, get_staff_roles, get_unlockables, get_event_roles, get_admin_roles, get_manager_roles, get_raider_role, get_raidstream_role, confirmation, get_setcap_max, get_setcap_min
#from globalvars import get_setcap_vetmax, get_setcap_vetmin
#import globalvars as g

import re

class ExtraCmds(commands.Cog, name='Extra Commands'):
  def __init__(self, bot: ShattersBot):
    self.bot = bot
  
  @commands.command(name='setcap')
  @commands.has_any_role(*get_event_roles())
  async def set_vc_cap(self, ctx: commands.Context, cap=None):
    """[ERL+] Sets the cap of the voice chat. Maximum and minimum are set by the admins. Can only be used in raiding channels where it's allowed.
    
    Args:
        cap (int): The cap to put.
    """
    if cap is None:
      await ctx.send("You must input a number as the new voice channel cap.")
      return
    
    try:
      cap = int(cap)
    except ValueError:
      await ctx.send("The new cap must be an integer.")
      return
    
    voice_ch = ctx.author.voice.channel if ctx.author.voice and ctx.author.voice.channel else None
    if voice_ch is None:
      await ctx.send("You must be connected to a voice channel to use this command.")
      return
    
    section = self.bot.get_section_from_voice_ch(ctx.guild.id, voice_ch.id)
    if section is None or section.allow_setcap is False or section.role_check(ctx.author.roles) is False:
      await ctx.send(f"You are not allowed to set the cap of {voice_ch.mention}.")
      return
    
    if cap > section.vc_max:
      cap = section.vc_max
      await ctx.send(f"{voice_ch.mention}'s cap has been set to the maximum of {section.vc_max}.")
    elif cap < section.vc_min:
      cap = section.vc_min
      await ctx.send(f"{voice_ch.mention}'s cap has been set to the minimum of {section.vc_min}.")
    else:
      await ctx.send(f"{voice_ch.mention}'s cap has been set to {cap}.")
      
    await voice_ch.edit(user_limit=cap, reason=f'Setcap by {ctx.author.display_name}')
  
  @commands.command(name='unlock')
  @commands.has_any_role(*get_event_roles())
  async def unlock_channel(self, ctx: commands.Context):
    """[ERL+] Unlocks the current voice channel, allowing raiders to join in. Can be used only in Event channels."""
    
    voice_ch = ctx.author.voice.channel if ctx.author.voice and ctx.author.voice.channel else None
    if voice_ch is None:
      await ctx.send("You must be connected to a voice channel to use this command.")
      return
    
    section = self.bot.get_section_from_voice_ch(ctx.guild.id, voice_ch.id)
    if section is None or section.allow_unlock is False  or section.role_check(ctx.author.roles) is False:
      await ctx.send(f"You are not allowed to unlock {voice_ch.mention}.")
      return

    #TODO: Check and see if this channel has an AFK check up.
    raider_role = ctx.guild.get_role(self.bot.get_vetraider_role(ctx.guild.id)) if section.is_vet else ctx.guild.get_role(self.bot.get_raider_role(ctx.guild.id))
    if raider_role is None:
      await ctx.send('Error: Raider role not found. Please contact an admin.')
      return
    
    await voice_ch.set_permissions(raider_role, connect=True, reason=f'Channel unlock by {ctx.author.display_name}')
    await ctx.send(f'{voice_ch.mention} has been unlocked.')
    
    pass
  
  @commands.command(name='lock')
  @commands.has_any_role(*get_event_roles())
  async def lock_channel(self, ctx: commands.Context):
    """[ERL+] Locks the current voice channel, preventing raiders from joining. Can only be used in Event channels."""
    voice_ch = ctx.author.voice.channel if ctx.author.voice and ctx.author.voice.channel else None
    if voice_ch is None:
      await ctx.send("You must be connected to a voice channel to use this command.")
      return
      
    section = self.bot.get_section_from_voice_ch(ctx.guild.id, voice_ch.id)
    if section is None or section.allow_unlock is False or section.role_check(ctx.author.roles) is False:
      await ctx.send(f"You are not allowed to lock {voice_ch.mention}.")
      return
      
    #TODO: Check and see if this channel has an AFK check up.
    raider_role = ctx.guild.get_role(self.bot.get_raider_role(ctx.guild.id))
    if raider_role is None:
      await ctx.send('Error: Raider role not found. Please contact an admin.')
      return
    
    await voice_ch.set_permissions(raider_role, connect=False, reason=f'Channel lock by {ctx.author.display_name}')
    await ctx.send(f'{voice_ch.mention} has been locked.')
  
  @commands.command(name='patience')
  async def give_patience(self, ctx: commands.Context):
    await ctx.message.delete()
    await ctx.send("https://media.discordapp.net/attachments/451181425115398184/897237811168690316/Shatters_Patience_DirectionsV1.1.gif?width=374&height=375")
  
  @commands.command(name='clean')
  @commands.has_any_role(*get_event_roles())
  async def clean_channel(self, ctx: commands.Context):
    """[ERL+] Removes all non-staff from the voice channel the user is in."""
    
    voice_ch: discord.VoiceChannel = ctx.author.voice.channel if ctx.author.voice and ctx.author.voice.channel else None
    if voice_ch is None:
      await ctx.send("You must be connected to a voice channel to use this command.")
      return
    
    section = self.bot.get_section_from_voice_ch(ctx.guild.id, voice_ch.id)
    if section is None or section.role_check(ctx.author.roles) is False:
      await ctx.send(f"You are not allowed to clean {voice_ch.mention}")
      return
    
    lounge_ch = ctx.guild.get_channel(section.lounge_ch)
    if lounge_ch is None or lounge_ch.type is not discord.ChannelType.voice:
      await ctx.send(f"Error: {lounge_ch} is either unavailable or not a voice channel. Please ping an admin.")
      return
          
    staff_roles = get_staff_roles()
    if self.bot.is_debug():
      await ctx.send("Staff Roles: " + str(staff_roles))
      
    move_awaits = []
    for member in voice_ch.members:
      if self.bot.is_debug():
        await ctx.send("Analyzing member: " + member.mention)
      skip = False
      for role in member.roles:
        if role.name in staff_roles:
          skip = True
          break
        
      if skip: continue
      
      move_awaits.append(asyncio.create_task(member.move_to(lounge_ch, reason=f'Channel cleaned by {ctx.author.display_name}')))
      
    if len(move_awaits) > 0:
      try:
        await asyncio.wait(move_awaits)
      except: # dont care if anything failed
        pass
    await ctx.send("Finished cleaning.")
    pass
  
  @commands.command(name='trl')
  @commands.has_any_role(*get_manager_roles())
  async def trl_vote(self, ctx, *nameparts):
    """[Manager+] Starts a TRL to ARL vote.

    Args:
        name (str): The text to put within the embed (typically a name).
    """
    await ctx.message.delete()
    if len(nameparts) == 0:
      msg = await ctx.send("Please input a name.")
      await asyncio.sleep(5)
      await msg.delete()
      return
  
    embed = discord.Embed(color=0x44bb88, description=' '.join(nameparts))
    msg = await ctx.send(embed=embed)
  
    emojis = ['✅', '❌', self.bot.get_emoji(924809116755587112)]
  
    for emoji in emojis:
      await msg.add_reaction(emoji)
      
  @commands.command(name='arl')
  @commands.has_any_role(*get_manager_roles())
  async def arl_vote(self, ctx, *nameparts):
    """[Manager+] Starts an ARL to RL vote.

    Args:
        name (str): The text to put within the embed (typically a name).
    """
    await ctx.message.delete()
    if len(nameparts) == 0:
      msg = await ctx.send("Please input a name.")
      await asyncio.sleep(5)
      await msg.delete()
      return
  
    embed = discord.Embed(color=0x3333aa, description=' '.join(nameparts))
  
    #btn = discord.Button({'type': 2, 'style': 2})
    msg = await ctx.send(embed=embed)
  
    emojis = ['✅', '❌', '❔']
  
    for emoji in emojis:
      await msg.add_reaction(emoji)

  @commands.Cog.listener()
  async def on_voice_state_update(self, member: discord.Member, before, after: discord.VoiceState):
    if after.channel is None or after.channel.id != before.channel.id:
      member_rsrole = member.get_role(self.bot.get_raidstream_role(member.guild.id))
      if member_rsrole is not None:
        await member.remove_roles(member_rsrole)
      
  @commands.command(name='allowstream')
  @commands.has_any_role(*get_event_roles())
  async def give_streaming_role(self, ctx: commands.Context, *nameparts):
    """[ERL+] Gives someone the designated 'Streaming' role, which gives them permission to stream video.
    !!This role is automatically removed when members change, leave, or join voice channels.!!

    Args:
        name (str): The name / nickname of the member.
    """    
    if nameparts is None:
      await ctx.send("Please enter a name")
      return
    
    member = None
    try:
      member = ctx.guild.get_member(int(nameparts[0]))
      if member is None:
        await ctx.send("Member not found.")
        return
      
    except ValueError:
      names = re.findall('[a-zA-Z]+', ' '.join(nameparts))
      for n in names:
        member = ctx.guild.get_member_named(n)
        if member is not None:
          break
    
      if member is None:
        member = ctx.guild.get_member_named(' '.join(nameparts))
        if member is None:
          await ctx.send("Member not found. Try using the raiders ID.")
          return
    
    if await confirmation(ctx, self.bot, "Give " + member.mention + " temporary streaming perms?", member.mention + " was given streaming perms."):
      role = ctx.guild.get_role(self.bot.get_raidstream_role(ctx.guild.id))
      if role is None:
        await ctx.send("Error: Raid streaming role not found. Please contact the bot dev or an admin.")
      
      else:
        await member.add_roles(role, reason=f'Add Streaming role, by {ctx.author.display_name}')
    
  @commands.command(name='countrole')
  @commands.has_any_role(*get_veteran_roles())
  async def countrole(self, ctx: commands.Context, *id_or_nameparts):
    """[Vet RL+] Counts the number of people who have a role. Arguments can either be a single role ID (integer), or a role name.
    Some roles have aliases:
      Vet -> Veteran Raider
      Sec -> Security
      ERL -> Event Raid Leader
      TRL -> Trial Raid Leader
      ARL -> Almost Raid Leader
      RL -> Raid Leader
      VRL -> Veteran Raid Leader
      VERL -> Veteran Event Raid Leader
      HRL -> Head Raid Leader
    """

    g: discord.Guild = ctx.guild
    if len(id_or_nameparts) < 1:
      await ctx.send('You must give an role ID or name.')
      return

    found_role = None

    try:
      id = int(id_or_nameparts[0])
      found_role = g.get_role(id)
      if found_role is None:
        await ctx.send(f"Role with ID `{id}` not found.")
        return
        
    except:
      name = ' '.join(id_or_nameparts)
      
      aliases = {
        'sec': 'Security',
        'erl': 'Event Raid Leader',
        'trl': 'Trial Raid Leader',
        'arl': 'Almost Raid Leader',
        'rl': 'Raid Leader',
        'vrl': 'Veteran Raid Leader',
        'verl': 'Veteran Event Raid Leader',
        'hrl': 'Head Raid Leader',
        'vet': 'Veteran Raider'
      }

      if name.lower() in aliases:
        name = aliases[name]

      role_list = await g.fetch_roles()
      for role in role_list:
        if role.name.lower() == name.lower():
          found_role = role
          break

      if found_role is None:
        await ctx.send(f"Role with name `{name}` not found.")
        return

    await ctx.send(embed=discord.Embed(description=f"__**{len(found_role.members)}**__ members have the role {found_role.mention}."))
    
    pass