import asyncio
import asyncpraw
import asyncprawcore
import logging
import discord

from collections import defaultdict

from sqlalchemy import Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import relationship, declarative_base

from dotenv import load_dotenv
import os
load_dotenv()

NEW_POSTS = int(os.getenv('NEW_POSTS'))

Base = declarative_base()

class UserSubreddit(Base):
    __tablename__ = 'UserSubreddit'
    id = Column(Integer, primary_key=True)
    user_id = Column(String(255), nullable=False)
    discord_name = Column(String(255))
    subreddit = Column(String(255), nullable=False)
    entries = relationship("EntryName", back_populates="user_subreddit")

class EntryName(Base):
    __tablename__ = 'EntryNames'
    id = Column(Integer, primary_key=True)
    user_subreddit_id = Column(Integer, ForeignKey('UserSubreddit.id'))
    entry_name = Column(String(255), nullable=False)
    keywords = Column(Text)
    user_subreddit = relationship("UserSubreddit", back_populates="entries")

class RedditMonitor:
    def __init__(self, client_id, client_secret, user_agent, alchemy_engine, alchemy_session):
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent
        self.alchemy_engine = alchemy_engine
        self.alchemy_session = alchemy_session
        
        self.subreddit_cache = defaultdict(list)

    def add_filter(self, user_id: str, discord_name: str, subreddit: str, entry_name: str, keywords):
        session = self.alchemy_session()
        try:
            # Check if the combination of user and subreddit exists
            user_subreddit = session.query(UserSubreddit).filter_by(user_id=user_id, subreddit=subreddit).first()
            if not user_subreddit:
                # Create a new UserSubreddit entry with the Discord name
                user_subreddit = UserSubreddit(user_id=user_id, discord_name=discord_name, subreddit=subreddit)
                session.add(user_subreddit)
            else:
                # Optionally, update the discord_name if it's different
                if user_subreddit.discord_name != discord_name:
                    user_subreddit.discord_name = discord_name

            # Check if the entry name exists under this user and subreddit
            entry = session.query(EntryName).filter_by(user_subreddit_id=user_subreddit.id, entry_name=entry_name).first()
            if not entry:
                entry = EntryName(user_subreddit_id=user_subreddit.id, entry_name=entry_name, keywords=','.join(keywords))
                session.add(entry)
            else:
                # Update the keywords if the entry already exists
                entry.keywords = ','.join(keywords)

            session.commit()
            
            logging.info(f"\nSuccessfully added/updated filter with subreddit '{subreddit}' for user '{user_id}' with entry name '{entry_name}'\n")
            
            return f"Filter '{entry_name}' added/updated for subreddit '{subreddit}' for user '{user_id}' with Discord name '{discord_name}'"
        except Exception as e:
            logging.error(f"Error adding/updating filter: {e}")
            return "Error occurred while adding/updating filter."
        finally:
            session.close()

    
    def remove_filter(self, user_id:str, subreddit:str, entry_name):
        session = self.alchemy_session()
        try:
            # Find the filter
            user_subreddit = session.query(UserSubreddit).filter_by(user_id=user_id, subreddit=subreddit).first()
            if not user_subreddit:
                return f"No such filter found for subreddit '{subreddit}'"

            entry = session.query(EntryName).filter_by(user_subreddit_id=user_subreddit.id, entry_name=entry_name).first()
            if not entry:
                return f"No such filter found with entry name '{entry_name}'"

            # Remove the filter
            session.delete(entry)
            session.commit()
            
            logging.info(f"\nSuccessfully removed filter with subreddit '{subreddit}' for user '{user_id}' with entry name '{entry_name}'\n")
            
            return f"Filter '{entry_name}' removed for subreddit '{subreddit}'"
        except Exception as e:
            logging.error(f"Error removing filter: {e}")
            return "Error occurred while removing filter."
        finally:
            session.close()

    async def check_reddit(self, client, interval: int):
        await client.wait_until_ready()
        while not client.is_closed():
            try:
                async with asyncpraw.Reddit(client_id=self.client_id, 
                                            client_secret=self.client_secret, 
                                            user_agent=self.user_agent) as reddit:
                    session = self.alchemy_session()
                    user_subreddits = session.query(UserSubreddit).order_by(UserSubreddit.subreddit).all()
                    
                    #for every row in the table
                    for user_subreddit in user_subreddits:
                        subreddit_name = user_subreddit.subreddit

                        #update subreddit entry cache
                        if subreddit_name not in self.subreddit_cache:
                            print("subreddit cache switch")
                            logging.info("cache switch subreddit")
                            try:
                                async_subreddit = await reddit.subreddit(subreddit_name)
                                #since the rows are sorted by subreddit, if a new one is detected the old one will never appear again
                                self.subreddit_cache.clear()
                                self.subreddit_cache[subreddit_name] = [submission async for submission in async_subreddit.new(limit=NEW_POSTS)]
                            except asyncprawcore.exceptions.RequestException as e:
                                logging.error(f"RequestException while accessing subreddit '{subreddit_name}': {e}")
                                # Handle the exception (e.g., skip this subreddit, retry after a delay, etc.)

                        #for each entry associated with the user:subreddit pair 
                        for entry in user_subreddit.entries:
                            sent_submissions = 0
                            #for each submission in the subreddit's new posts
                            for submission in self.subreddit_cache[subreddit_name]:
                                if all(keyword.lower() in submission.title.lower() for keyword in entry.keywords.split(',')):
                                    try:
                                        user = await client.fetch_user(user_subreddit.user_id)
                                        post_url = f"https://reddit.com{submission.permalink}"
                                        await user.send(f"Deal found: {submission.title}\n{post_url}")
                                        sent_submissions += 1
                                    except discord.HTTPException as e:
                                        logging.error(f"Error sending message to user {user_subreddit.user_id}: {e}")
                            logging.info(f"For user {user_subreddit.discord_name} found {sent_submissions} entries for subreddit {subreddit_name}")

                    # Close the session after processing
                    session.close()

                    # Clear the subreddit cache
                    print("cache clear")
                    self.subreddit_cache.clear()

            except asyncprawcore.exceptions.PrawcoreException as e:
                logging.error(f"Reddit API error: {e}")
            except discord.errors.HTTPException as e:
                logging.error(f"Discord network error: {e}")
            except Exception as e:
                logging.error(f"Unexpected error in check_reddit: {e}")

            # Sleep before the next iteration
            await asyncio.sleep(interval)




            
    def get_user_profile(self, user_id):
        session = self.alchemy_session()
        try:
            user_subreddits = session.query(UserSubreddit).filter_by(user_id=user_id).all()
            if not user_subreddits:
                return "No filters set for this user."
            profile_info = []
            for user_subreddit in user_subreddits:
                for entry in user_subreddit.entries:
                    profile_info.append(f"{user_subreddit.subreddit} - {entry.entry_name}: {', '.join(entry.keywords.split(','))}")
            return "\n".join(profile_info)
        except Exception as e:
            logging.error(f"Error retrieving user profile: {e}")
            return "Error occurred while retrieving user profile."
        finally:
            session.close()