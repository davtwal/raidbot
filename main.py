
from datetime import datetime
import pytz

import sys
import traceback

import discord
from discord.ext import commands

from dotenv import load_dotenv
load_dotenv()

from globalvars import DISCORD_TOKEN, get_raid_roles, get_veteran_roles
from extra import ExtraCmds
from raiding import RaidingCmds
from admin import AdminCmds
from errorhandler import ErrorHandling
from funnystuff import RunsWhenCog
#from tracking import TrackingCog
from shattersbot import ShattersBot
from security import SecurityCog

import sys

if len(sys.argv) > 1:
  cmd_prefix = "]"
else:
  cmd_prefix = "^"

bot = ShattersBot(cmd_prefix)
#bot = commands.Bot(command_prefix="^")

def excepthook(*exc_info):
  try:
    bot.log(traceback.format_exception(*exc_info))
  except:
    pass

sys.excepthook = excepthook

bot.add_cog(ErrorHandling(bot))
bot.add_cog(AdminCmds(bot))
bot.add_cog(ExtraCmds(bot))
bot.add_cog(RaidingCmds(bot))
##bot.add_cog(TrackingCog(bot))
bot.add_cog(RunsWhenCog(bot))
bot.add_cog(SecurityCog(bot))

if len(sys.argv) > 1:
  import os
  bot.run(os.getenv("DEBUG_TOKEN"))
else:
  bot.run(DISCORD_TOKEN)