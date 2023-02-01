import os
from dotenv import load_dotenv
load_dotenv()

import discord
from discord.ext import commands

bot = commands.Bot(command_prefix="^")

@bot.command()
async def test(ctx: commands.Context):
    await ctx.send("Test Ping command works.")

bot.run(os.getenv('DISCORD_TOKEN'))

