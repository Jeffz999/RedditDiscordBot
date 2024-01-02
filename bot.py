import discord
import os
from dotenv import load_dotenv
from discord.ext import commands
import asyncio
import asyncpraw
from asyncprawcore import RequestException
import csv
load_dotenv()

REDDIT_CLIENT_ID = os.getenv('REDDIT_CLIENT_ID') 
REDDIT_SECRET = os.getenv('REDDIT_SECRET')
USER_AGENT = os.getenv('USER_AGENT')
CHECK_INTERVAL = 60 #TODO: change to 5 min

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
        if user_id in self.user_profiles and subreddit in self.user_profiles[user_id]:
            del self.user_profiles[user_id][subreddit][entry_name]
            return f"Filter removed for {subreddit}, {entry_name}"
        return "No such filter found"
    
    
    def load_filters(self, filename):
        self.user_profiles = {}
        try:
            with open(filename, mode='r', newline='', encoding='utf-8') as file:
                reader = csv.reader(file)
                for row in reader:
                    user_id, subreddit, entry_name, keywords_joined = row
                    keywords = set(keywords_joined.split(','))
                    self.user_profiles.setdefault(user_id, {}).setdefault(subreddit, {})[entry_name] = keywords
        except FileNotFoundError:
            print(f"No existing file found: {filename}. Starting with empty filters.")

    def save_filters(self, filename):
        with open(filename, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            for user_id, filters in self.user_profiles.items():
                for subreddit, entries in filters.items():
                    for entry_name, keywords in entries.items():
                        keywords_joined = ','.join(keywords)
                        writer.writerow([user_id, subreddit, entry_name, keywords_joined])

    async def check_reddit(self, client, interval):
        await client.wait_until_ready()
        while not client.is_closed():
            async with asyncpraw.Reddit(client_id=self.client_id, 
                                        client_secret=self.client_secret, 
                                        user_agent=self.user_agent) as reddit:
                user_profiles_snapshot = list(self.user_profiles.items())
                for user_id, filters in user_profiles_snapshot:
                    for subreddit, entries in filters.items():
                        for entry_name, keywords in entries.items():
                            try:
                                async_subreddit = await reddit.subreddit(subreddit)
                                async for submission in async_subreddit.new(limit=100):
                                    # Check if all keywords are in the submission's title
                                    if all(keyword.lower() in submission.title.lower() for keyword in keywords):
                                        user = await client.fetch_user(user_id)
                                        await user.send(f"Deal found: {submission.title}\n{submission.url}")
                            except Exception as e:
                                print(f"An error occurred: {e}")
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
    reddit_monitor.load_filters('filters.csv')
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
    if message.lower() == 'who are you':  # Check if the argument is 'hello'
        await ctx.send("Do you 2 piss ants not have a clue who I am?\nSeriously\nI am Alek Fucking Rawls. I am the founder of Republic of Texas Airsoft\n\nI am not some speedsofter to shit on")
    else:
        await ctx.send("and you too")
        
@bot.command()
async def help_commands(ctx):
    await ctx.send("Ok so while I am also a satrical representation of TLA's Chairman/Dictator, my main purpose is to save money by checking reddit for deals (subreddits like gundeals or gafs). \n\nFunction: \"$addfilter subreddit entry_name keywords\" with keywords being a list of keywords you want checked is how u tell me what things you want searched. To remove a filter use \"removefilter subreddit entryname\"\n\nFor any other questions just ask the creater")

@bot.command()
async def add_filter(ctx, subreddit, entry_name, *keywords):
    response = reddit_monitor.add_filter(str(ctx.author.id), subreddit, entry_name, keywords)
    reddit_monitor.save_filters('filters.csv')
    await ctx.send(response)

@bot.command()
async def remove_filter(ctx, subreddit, entry_name):
    response = reddit_monitor.remove_filter(str(ctx.author.id), subreddit, entry_name)
    reddit_monitor.save_filters('filters.csv')
    await ctx.send(response)
    
@bot.command()
async def show_profile(ctx):
    user_id = str(ctx.author.id)
    profile_info = reddit_monitor.get_user_profile(user_id)
    await ctx.send(f"Your profile:\n{profile_info}")

bot.run(os.getenv('DISCORD_TOKEN'))