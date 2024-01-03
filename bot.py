import discord
import os
from dotenv import load_dotenv
from discord.ext import commands
import asyncio
import asyncpraw
import asyncprawcore
import logging
import csv
import aiofiles
load_dotenv()

REDDIT_CLIENT_ID = os.getenv('REDDIT_CLIENT_ID') 
REDDIT_SECRET = os.getenv('REDDIT_SECRET')
USER_AGENT = os.getenv('USER_AGENT')
CHECK_INTERVAL = 60 #TODO: change to 5 min

logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    filename='app.log', # if you want to log to a file
                    filemode='a') # Append mode

# Test logging
logging.info("Logging has been configured")

class RedditMonitor:
    def __init__(self, client_id, client_secret, user_agent):
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent
        self.user_profiles = {}

    def add_filter(self, user_id:str, subreddit:str, entry_name: str, keywords):
        keywords_set = set(keywords)  # Create a set of keywords
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = {}
        if subreddit not in self.user_profiles[user_id]:
            self.user_profiles[user_id][subreddit] = {}
        if entry_name not in self.user_profiles[user_id][subreddit]:
            self.user_profiles[user_id][subreddit][entry_name] = set()
        # Append this new set of keywords to the list for the subreddit
        self.user_profiles[user_id][subreddit][entry_name].update(keywords_set)
        return f"New filter added for {subreddit}: {', '.join(keywords)}"
    
    def remove_filter(self, user_id:str, subreddit:str, entry_name):
        try:
            del self.user_profiles[user_id][subreddit][entry_name]
            if not self.user_profiles[user_id][subreddit]:
                del self.user_profiles[user_id][subreddit]
            return f"Filter removed for {subreddit}, {entry_name}"
        except KeyError:
            return "No such filter found"
    
    
    async def load_filters(self, filename):
        self.user_profiles = {}
        try:
            async with aiofiles.open(filename, mode='r', newline='', encoding='utf-8') as file:
                lines = await file.readlines()
                reader = csv.reader(lines)
                for row in reader:
                    user_id, subreddit, entry_name, keywords_joined = row
                    keywords = set(keywords_joined.strip('"').split(','))  # Remove quotes and split
                    self.user_profiles.setdefault(user_id, {}).setdefault(subreddit, {})[entry_name] = keywords
        except FileNotFoundError:
            print(f"No existing file found: {filename}. Starting with empty filters.")

    async def save_filters(self, filename):
        try:
            async with aiofiles.open(filename, mode='w', newline='', encoding='utf-8') as file:
                for user_id, filters in self.user_profiles.items():
                    for subreddit, entries in filters.items():
                        for entry_name, keywords in entries.items():
                            keywords_joined = '"' + ','.join(keywords) + '"'  # Encapsulating with quotes
                            line = f"{user_id},{subreddit},{entry_name},{keywords_joined}\n"
                            await file.write(line)
        except IOError as e:
            logging.error(f"Error saving filters to file {filename}: {e}")


    async def check_reddit(self, client, interval):
        await client.wait_until_ready()
        while not client.is_closed():
            try:
                async with asyncpraw.Reddit(client_id=self.client_id, 
                                            client_secret=self.client_secret, 
                                            user_agent=self.user_agent) as reddit:
                    user_profiles_snapshot = list(self.user_profiles.items())
                    for user_id, filters in user_profiles_snapshot:
                        for subreddit, entries in filters.items():
                            try:
                                async_subreddit = await reddit.subreddit(subreddit)
                                async for submission in async_subreddit.new(limit=100):
                                    for entry_name, keywords in entries.items():
                                        if all(keyword.lower() in submission.title.lower() for keyword in keywords):
                                            try:
                                                user = await client.fetch_user(user_id)
                                                post_url = f"https://reddit.com{submission.permalink}"
                                                await user.send(f"Deal found: {submission.title}\n{post_url}")
                                            except discord.HTTPException as e:
                                                logging.error(f"Error sending message to user {user_id}: {e}")
                            except asyncprawcore.exceptions.Forbidden:
                                logging.error(f"Access to subreddit '{subreddit}' is forbidden. It might be private.")
                            except asyncprawcore.exceptions.NotFound:
                                logging.error(f"Subreddit '{subreddit}' not found. It might be banned or non-existent.")
            except asyncprawcore.exceptions.PrawcoreException as e:
                logging.error(f"Reddit API error: {e}")
            except discord.errors.HTTPException as e:
                logging.error(f"Discord network error: {e}")
            except Exception as e:
                logging.error(f"Unexpected error in check_reddit: {e}")
            await asyncio.sleep(interval)

            
    def get_user_profile(self, user_id):
        user_profile = self.user_profiles.get(str(user_id), {})
        if not user_profile:
            return "No filters set for this user."
        profile_info = []
        for subreddit, entries in user_profile.items():
            for entry_name, keywords in entries.items():
                profile_info.append(f"{subreddit} - {entry_name}: {', '.join(keywords)}")
        return "\n".join(profile_info)


# Bot Setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='$', intents=intents)

reddit_monitor = RedditMonitor(REDDIT_CLIENT_ID, REDDIT_SECRET, USER_AGENT)

@bot.event
async def on_ready():
    print("Initialized")
    await reddit_monitor.load_filters('filters.csv')
    print("loaded filters")
    channel = bot.get_channel(1172792075566202890)  # Replace with your channel ID
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
    await ctx.send("Ok so while I am also a satrical representation of TLA's Chairman/Dictator, my main purpose is to save money by checking reddit for deals. \n\nFunction: \"$addfilter subreddit entry_name keywords\" with keywords being a list of keywords you want checked is how u tell me what things you want searched. To remove a filter use \"removefilter subreddit entryname\"\n\nFor any other questions just ask the creater")

@bot.command()
async def add_filter(ctx, subreddit, entry_name, *keywords):
    if keywords == () or keywords == (" "):
        await ctx.send("Bruh ur giving me no keywords")
    else:
        response = reddit_monitor.add_filter(str(ctx.author.id), subreddit, entry_name, keywords)
        await reddit_monitor.save_filters('filters.csv')
        await ctx.send(response)

@bot.command()
async def remove_filter(ctx, subreddit, entry_name):
    response = reddit_monitor.remove_filter(str(ctx.author.id), subreddit, entry_name)
    await reddit_monitor.save_filters('filters.csv')
    await ctx.send(response)
    
@bot.command()
async def show_profile(ctx):
    user_id = str(ctx.author.id)
    profile_info = reddit_monitor.get_user_profile(user_id)
    await ctx.send(f"Your profile:\n{profile_info}")

bot.run(os.getenv('DISCORD_TOKEN'))