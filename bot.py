import discord
import os
from dotenv import load_dotenv
from discord.ext import commands
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

import urllib.parse 
from reddit_monitor import RedditMonitor

import logging
load_dotenv()

REDDIT_CLIENT_ID = os.getenv('REDDIT_CLIENT_ID') 
REDDIT_SECRET = os.getenv('REDDIT_SECRET')
USER_AGENT = os.getenv('USER_AGENT')
CHECK_INTERVAL = 120 #TODO: change to 5 min
CHANNEL_ID = os.getenv('CHANNEL_ID')

logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    filename='app.log', # if you want to log to a file
                    filemode='a') # Append mode

# Test logging
logging.info("Logging has been configured")

#alchemy
SCHEMA = os.getenv('DB_SCHEMA')
HOST = os.getenv('DB_HOST')
USER = os.getenv('DB_USER')
PASSWORD = os.getenv('DB_PASSWORD')
encoded_password = urllib.parse.quote_plus(PASSWORD) 
PORT = 3306

# Replace 'mysql+mysqlconnector://<user>:<password>@<host>/<dbname>' with your actual database URL
DATABASE_URL = f'mysql+mysqlconnector://{USER}:{encoded_password}@{HOST}:{PORT}/{SCHEMA}'

engine = create_engine(DATABASE_URL, echo=True)
Session = sessionmaker(bind=engine)

Base = declarative_base()

# To create tables (if they don't exist)
Base.metadata.create_all(engine)


# Bot Setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='$', intents=intents)

reddit_monitor = RedditMonitor(REDDIT_CLIENT_ID, REDDIT_SECRET, USER_AGENT, engine, Session)

@bot.event
async def on_ready():
    print("Initialized")
    channel = bot.get_channel(CHANNEL_ID)  # Replace with your channel ID
    if channel:
        await channel.send("Initialized. Use \"$help_commands\" for documentation")
    bot.loop.create_task(reddit_monitor.check_reddit(bot, CHECK_INTERVAL))

@bot.command()
async def add(ctx, *arr):
    sum = 0
    for elem in arr:
        sum += int(elem)
    await ctx.send(f"result = {sum}")
    
@bot.command(name='greet')
async def greet(ctx, *args):
    message = ' '.join(args).lower()
    if message.lower() == 'who are you' or message.lower() == 'who are you?':  # Check if the argument is 'hello'
        await ctx.send("Do you 2 piss ants not have a clue who I am?\nSeriously\nI am Alek Fucking Rawls. I am the founder of Republic of Texas Airsoft\n\nI am not some speedsofter to shit on")
    else:
        await ctx.send("and you too")
        
@bot.command()
async def help_commands(ctx):
    await ctx.send("Ok so while I am also a satrical representation of TLA's Chairman/Dictator, my main purpose is to save money by checking reddit for deals. \n\nFunction: \"$addfilter subreddit entry_name keywords\" with keywords being a list of keywords you want checked is how u tell me what things you want searched. \n\nTo remove a filter use \"removefilter subreddit entryname\"\n\nFor any other questions just ask the creater")

@bot.command()
async def add_filter(ctx, subreddit, entry_name, *keywords):
    if keywords == () or keywords == (" "):
        await ctx.send("Bruh ur giving me no keywords")
    else:
        # Retrieve the Discord username
        discord_username = ctx.author.name  # This gets the user's Discord name
        # Call add_filter with the Discord username
        response = reddit_monitor.add_filter(str(ctx.author.id), discord_username, subreddit, entry_name, keywords)
        await ctx.send(response)

@bot.command()
async def remove_filter(ctx, subreddit, entry_name):
    response = reddit_monitor.remove_filter(str(ctx.author.id), subreddit, entry_name)
    await ctx.send(response)
    
@bot.command()
async def show_profile(ctx):
    user_id = str(ctx.author.id)
    profile_info = reddit_monitor.get_user_profile(user_id)
    await ctx.send(f"Your profile:\n{profile_info}")
    
@bot.command(name='shutdown')
@commands.is_owner()
async def shutdown(ctx):
    """Shuts down the bot. Only the bot owner can use this command."""
    await ctx.send("Shutting down...")
    await bot.logout()
    await bot.close()

@shutdown.error
async def shutdown_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("You do not have permission to use this command.")


bot.run(os.getenv('DISCORD_TOKEN'))