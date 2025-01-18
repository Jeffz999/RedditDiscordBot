import discord
import os
from dotenv import load_dotenv
from discord.ext import commands
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import asyncio

import urllib.parse 
from reddit_monitor import RedditMonitor

import logging

import responses
load_dotenv()

REDDIT_CLIENT_ID = os.getenv('REDDIT_CLIENT_ID') 
REDDIT_SECRET = os.getenv('REDDIT_SECRET')
USER_AGENT = os.getenv('USER_AGENT')
CHECK_INTERVAL = int(os.getenv('PING_TIMER'))
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
DATABASE_URL = f'mysql+pymysql://{USER}:{encoded_password}@{HOST}:{PORT}/{SCHEMA}'

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

check_reddit_task = None

@bot.event
async def on_ready():
    global check_reddit_task
    print("Initialized")
    logging.info("\n\n Initalized \n\n")
    channel_ids = os.getenv('CHANNEL_ID').split(',')
    
    for channel_id in channel_ids:
        channel = bot.get_channel(int(channel_id.strip()))
        if channel:
            await channel.send("Initialized. Use \"help\" for documentation")
        else:
            logging.error(f"\nerror channel {channel_id} failed to initialize\n")
    
    if check_reddit_task is None or check_reddit_task.done():
        # If the task is not running or is completed, restart it
        logging.info("Created check reddit loop")
        check_reddit_task = bot.loop.create_task(reddit_monitor.check_reddit(bot, CHECK_INTERVAL))

@bot.command()
async def add(ctx, *arr):
    logging.info(f"\nCommand 'add' invoked by {ctx.author}\n")
    sum = 0
    for elem in arr:
        sum += int(elem)
    await ctx.send(f"result = {sum}")
    
@bot.command(name='greet', help="greet then type 'who are you'")
async def greet(ctx, *args):
    message = ' '.join(args).lower()
    if message == 'who are you' or message == 'who are you?':  # Check if the argument is 'hello'
        await ctx.send(responses.RAWLS_PASTA)
    else:
        await ctx.send("and you too")
        

@bot.command(help="Adds a filter for a subreddit. Usage: $add_filter <subreddit> <entry_name> <keywords>. DO NOT INCLUDE the 'r/' in the subreddit name.")
async def add_filter(ctx, *args):
    if len(args) < 3:
        await ctx.send("Insufficient arguments. You need to provide a subreddit, entry name, and at least one keyword.")
        return

    subreddit, entry_name, *keywords = args
    logging.info(f"\nCommand 'add_filter' invoked by {ctx.author} with arguments: subreddit={subreddit}, entry_name={entry_name}, keywords={keywords}\n")
    async def confirmation_check(message):
        return message.author == ctx.author and message.content.lower() in ["yes", "no"]


    # Send back what the bot thinks the arguments are and ask for confirmation
    confirmation_message = await ctx.send(f"Subreddit: {subreddit}\nEntry Name: {entry_name}\nKeywords: {', '.join(keywords)}. Are you sure you want to proceed? (Reply with 'yes' to confirm or 'no' to cancel)")

    try:
        # Wait for the user's response
        confirmation_response = await bot.wait_for('message', check=confirmation_check, timeout=30.0)  # 30 seconds to respond

        # Check the user's response
        if confirmation_response.content.lower() == "yes":
            # Retrieve the Discord username
            discord_username = ctx.author.name

            # Call add_filter with the Discord username
            response = reddit_monitor.add_filter(str(ctx.author.id), discord_username, subreddit, entry_name, keywords)
            await ctx.send(response)
        else:
            await ctx.send("Filter addition cancelled.")

    except asyncio.TimeoutError:
        # If the user does not respond in 30 seconds
        await ctx.send("No response received. Filter addition cancelled.")
        await confirmation_message.delete()


@bot.command(help="Removes a filter from a subreddit. Usage: $remove_filter <subreddit> <entry_name>. DO NOT INCLUDE the 'r/' in the subreddit name.")
async def remove_filter(ctx, subreddit, entry_name):
    logging.info(f"\nCommand 'add_filter' invoked by {ctx.author} with arguments: subreddit={subreddit}, entry_name={entry_name}\n")
    if not subreddit or not entry_name:
        await ctx.send("You must provide both a subreddit and an entry name.")
        return

    # Send back what the bot thinks the arguments are and ask for confirmation
    confirmation_message = await ctx.send(f"Subreddit: {subreddit}\nEntry Name: {entry_name}. Are you sure you want to remove this filter? (Reply with 'yes' to confirm or 'no' to cancel)")

    def confirmation_check(message):
        return message.author == ctx.author and message.content.lower() in ["yes", "no"]

    try:
        # Wait for the user's response
        confirmation_response = await bot.wait_for('message', check=confirmation_check, timeout=30.0)  # 30 seconds to respond

        # Check the user's response
        if confirmation_response.content.lower() == "yes":
            # Call remove_filter
            response = reddit_monitor.remove_filter(str(ctx.author.id), subreddit, entry_name)
            await ctx.send(response)
        else:
            await ctx.send("Filter removal cancelled.")

    except asyncio.TimeoutError:
        # If the user does not respond in 30 seconds
        await ctx.send("No response received. Filter removal cancelled.")
        await confirmation_message.delete()

    
@bot.command()
async def show_profile(ctx):
    user_id = str(ctx.author.id)
    profile_info = reddit_monitor.get_user_profile(user_id)
    await ctx.send(f"Your profile:\n{profile_info}")
    
@bot.command(name='shutdown')
@commands.is_owner()
async def shutdown(ctx):
    """Shuts down the bot. Only the bot owner can use this command."""
    global check_reddit_task
    await ctx.send("Shutting down...")

    # Cancel the check_reddit task
    if check_reddit_task and not check_reddit_task.done():
        check_reddit_task.cancel()
        try:
            await check_reddit_task  # Await the task to handle any exceptions
        except asyncio.CancelledError:
            await ctx.send("Background tasks have been cancelled.")  # Notify that tasks are cancelled

    try:
        await bot.close()
    except asyncio.CancelledError:
        # This block will handle CancelledError raised by bot.close()
        pass  # Optionally, log this event or perform other cleanup actions

    # Additional logging or cleanup can go here if needed
    print("Bot shutdown completed.")


@shutdown.error
async def shutdown_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("You do not have permission to use this command.")


bot.run(os.getenv('DISCORD_TOKEN'))