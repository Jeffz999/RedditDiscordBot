import praw
import asyncio


USER_AGENT = "python:seraph_search:beta0.0.1 (by /u/Alek_Fucking_Rawls)"

class RedditMonitor:
    def __init__(self, client_id, client_secret, user_agent, send_message_func):
        self.reddit = praw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=user_agent)
        self.user_profiles = {}
        self.send_message = send_message_func

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
            for user_id, filters in self.user_profiles.items():
                for subreddit, keywords in filters.items():
                    for submission in self.reddit.subreddit(subreddit).new(limit=10):
                        if any(keyword.lower() in submission.title.lower() for keyword in keywords):
                            user = await client.fetch_user(user_id)
                            await self.send_message(user, f"Deal found: {submission.title}\n{submission.url}", True)
            await asyncio.sleep(interval)
