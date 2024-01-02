import discord
import os
from dotenv import load_dotenv
from discord.ext import commands
import asyncio
import asyncpraw
from asyncprawcore import RequestException
load_dotenv()

REDDIT_CLIENT_ID = os.getenv('REDDIT_CLIENT_ID') 
REDDIT_SECRET = os.getenv('REDDIT_SECRET')
USER_AGENT = "python:seraph_search:beta0.0.1 (by /u/Alek_Fucking_Rawls)"
CHECK_INTERVAL = 15 #TODO: change to 5 min

class RedditMonitor:
    def __init__(self, client_id, client_secret, user_agent):
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent
        self.user_profiles = {}

    def add_filter(self, user_id, subreddit, keywords):
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = {}
        self.user_profiles[user_id][subreddit] = keywords
        return f"Filter added for {subreddit} with keywords: {', '.join(keywords)}"
    
    def remove_filter(self, user_id, subreddit):
        if user_id in self.user_profiles and subreddit in self.user_profiles[user_id]:
            del self.user_profiles[user_id][subreddit]
            return f"Filter removed for {subreddit}"
        return "No such filter found"

    async def check_reddit(self, client, interval):
        await client.wait_until_ready()
        while not client.is_closed():
            async with asyncpraw.Reddit(client_id=self.client_id, 
                                        client_secret=self.client_secret, 
                                        user_agent=self.user_agent) as reddit:
                for user_id, filters in self.user_profiles.items():
                    for subreddit, keywords in filters.items():
                        try:
                            async_subreddit = await reddit.subreddit(subreddit)
                            async for submission in async_subreddit.new(limit=100):
                                if any(keyword.lower() in submission.title.lower() for keyword in keywords):
                                    user = await client.fetch_user(user_id)
                                    await user.send(f"Deal found: {submission.title}\n{submission.url}")
                        except Exception as e:
                            print(f"An error occurred: {e}")
            await asyncio.sleep(interval)
            
    def get_user_profile(self, user_id):
        user_profile = self.user_profiles.get(user_id, {})
        if not user_profile:
            return "No filters set for this user."
        profile_info = []
        for subreddit, keywords in user_profile.items():
            profile_info.append(f"{subreddit}: {', '.join(keywords)}")
        return "\n".join(profile_info)


# Bot Setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='$', intents=intents)

reddit_monitor = RedditMonitor(REDDIT_CLIENT_ID, REDDIT_SECRET, USER_AGENT)

@bot.event
async def on_ready():
    print("Initialized")
    channel = bot.get_channel(1172792075566202890)  # Replace with your channel ID
    if channel:
        await channel.send("Initialized")
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
async def addfilter(ctx, subreddit, *keywords):
    response = reddit_monitor.add_filter(ctx.author.id, subreddit, keywords)
    await ctx.send(response)

@bot.command()
async def removefilter(ctx, subreddit):
    response = reddit_monitor.remove_filter(ctx.author.id, subreddit)
    await ctx.send(response)
    
@bot.command()
async def showprofile(ctx):
    user_id = ctx.author.id
    profile_info = reddit_monitor.get_user_profile(user_id)
    await ctx.send(f"Your profile:\n{profile_info}")

bot.run(os.getenv('DISCORD_TOKEN'))