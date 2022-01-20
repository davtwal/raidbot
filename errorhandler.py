from discord.ext import commands

class ErrorHandling(commands.Cog):
  def __init__(self, bot: commands.Bot):
    self.bot = bot
    
  @commands.Cog.listener()
  async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
      return
      #msg = "Command not found."
    if isinstance(error, commands.MissingAnyRole):
      msg = "You do not have a required role for this command."
    elif isinstance(error, commands.MissingPermissions):
      msg = "You do not have permissions for this command."
    elif isinstance(error, commands.CommandError):
      msg = "Command error: " + str(error)
    else:
      msg = "An error has occurred O////O"
      
    await ctx.send(msg)