from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta  
from typing import List, Optional, Dict, Any

import asyncpraw
import asyncprawcore
import discord
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from cache import SubredditCache
from models import UserSubreddit, EntryFilter
from exceptions import RedditMonitorError

logger = logging.getLogger(__name__)
from typing import Callable, Awaitable


AsyncSessionFactory = Callable[[], Awaitable[AsyncSession]]

class RedditMonitor:
    """Monitors Reddit subreddits for matching posts based on user filters."""
    
    def __init__(
        self, 
        client_id: str,
        client_secret: str,
        user_agent: str,
        session_factory: AsyncSessionFactory,
        cache_timeout: int = 600,
        max_posts: int = 100
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent
        self.session_factory = session_factory
        self.cache_timeout = cache_timeout
        self.max_posts = max_posts
        self.cache = SubredditCache(timeout=cache_timeout)
        
    async def initialize_reddit(self) -> asyncpraw.Reddit:
        """Initialize Reddit API client."""
        return asyncpraw.Reddit(
            client_id=self.client_id,
            client_secret=self.client_secret,
            user_agent=self.user_agent
        )

    async def add_filter(
        self, 
        user_id: str, 
        discord_name: str, 
        subreddit: str, 
        entry_name: str, 
        keywords: List[str]
    ) -> str:
        """Add or update a filter for a user."""
        async with self.session_factory() as session:
            async with session.begin():  # Proper transaction management
                try:
                    user_sub = await self._get_or_create_user_subreddit(
                        session, user_id, discord_name, subreddit
                    )
                    
                    entry = await self._get_or_create_entry_filter(
                        session, user_sub.id, entry_name, keywords
                    )
                    
                    return (f"Filter '{entry_name}' added/updated for subreddit '{subreddit}' "
                           f"with keywords: {', '.join(entry.keyword_list)}")
                    
                except Exception as e:
                    logger.error(f"Error adding filter: {e}")
                    await session.rollback()
                    raise RedditMonitorError(f"Failed to add filter: {str(e)}")
                
                
    async def remove_filter(self, user_id: str, subreddit: str, entry_name: str) -> str:
        """Remove a filter for a user."""
        async with self.session_factory() as session:
            async with session.begin():
                try:
                    # Load UserSubreddit with entries eagerly
                    stmt = (
                        select(UserSubreddit)
                        .options(selectinload(UserSubreddit.entries))
                        .filter_by(user_id=user_id, subreddit=subreddit)
                    )
                    result = await session.execute(stmt)
                    user_sub = result.scalar_one_or_none()

                    if not user_sub:
                        return f"No filters found for subreddit '{subreddit}'"

                    # Find the specific entry
                    entry = next(
                        (e for e in user_sub.entries if e.entry_name == entry_name),
                        None
                    )
                    if not entry:
                        return f"Filter '{entry_name}' not found"

                    # Case 1: Delete the entire UserSubreddit if it has only this entry
                    if len(user_sub.entries) == 1:
                        await session.delete(user_sub)  # This will cascade delete the entry
                    else:
                        # Case 2: Delete only the entry
                        await session.delete(entry)

                    return f"Filter '{entry_name}' removed from subreddit '{subreddit}'"

                except Exception as e:
                    await session.rollback()
                    raise RedditMonitorError(f"Failed to remove filter: {str(e)}")

    async def get_user_profile(self, user_id: str) -> str:
        """Get user's profile showing all their filters."""
        async with self.session_factory() as session:
            try:
                # Add selectinload here too
                stmt = select(UserSubreddit).options(
                    selectinload(UserSubreddit.entries)
                ).filter_by(user_id=user_id)
                
                result = await session.execute(stmt)
                user_subs = result.scalars().all()
                
                if not user_subs:
                    return "No filters set up yet."
                
                profile = ["Your active filters:"]
                for user_sub in user_subs:
                    profile.append(f"\nSubreddit: r/{user_sub.subreddit}")
                    # Now we can safely access entries since they're eager loaded
                    for entry in user_sub.entries:
                        keywords = entry.keyword_list
                        profile.append(f"  - {entry.entry_name}: {', '.join(keywords)}")
                
                return "\n".join(profile)
                
            except Exception as e:
                logger.error(f"Error getting user profile: {e}")
                raise RedditMonitorError(f"Failed to get profile: {str(e)}")

    async def check_subreddit(self, reddit: asyncpraw.Reddit, subreddit_name: str) -> List[asyncpraw.models.Submission]:
        """Fetch new posts from a subreddit."""    
        try:
            cached_posts = self.cache.get(subreddit_name)
            if cached_posts is not None:
                return cached_posts

            subreddit = await reddit.subreddit(subreddit_name)
            posts = []
            try:
                async for post in subreddit.new(limit=self.max_posts):
                    posts.append(post)
            except asyncprawcore.exceptions.RateLimitExceeded:
                logger.warning(f"Rate limit hit for subreddit {subreddit_name}")
                await asyncio.sleep(60)  # Wait before retrying
                
            self.cache.set(subreddit_name, posts)
            return posts
        except Exception as e:
            logger.error(f"Error checking subreddit {subreddit_name}: {e}")
            raise RedditMonitorError(f"Failed to fetch posts: {str(e)}")

    async def process_matches(
        self, 
        discord_client: discord.Client,
        posts: List[asyncpraw.models.Submission],
        user_sub: UserSubreddit,
        entry: EntryFilter
    ) -> int:
        """Process matching posts and send notifications."""
        sent_count = 0
        try:
            user = await discord_client.fetch_user(user_sub.user_id)
            
            for post in posts:
                if self._post_matches_filter(post, entry.keyword_list):
                    await self._send_notification(user, post)
                    sent_count += 1
                    
            return sent_count
            
        except discord.HTTPException as e:
            logger.error(f"Discord error for user {user_sub.user_id}: {e}")
            raise RedditMonitorError(f"Failed to send notifications: {str(e)}")

    async def monitor_loop(
        self, 
        discord_client: discord.Client, 
        interval: int
    ) -> None:
        """
        Main monitoring loop that checks Reddit at specified intervals.
        
        Args:
            discord_client: Discord bot client
            interval: Time in seconds between Reddit checks
        """
        while True:
            try:
                # Properly await the coroutine first
                reddit = await self.initialize_reddit()
                # Then use the async context manager
                async with reddit:
                    await self._process_all_filters(discord_client, reddit)
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
            finally:
                # Always wait the interval before next check
                await asyncio.sleep(interval)

    # Private helper methods
    async def _get_or_create_user_subreddit(
        self,
        session: AsyncSession,
        user_id: str,
        discord_name: str,
        subreddit: str
    ) -> UserSubreddit:
        """Get or create a UserSubreddit entry."""
        stmt = select(UserSubreddit).filter_by(user_id=user_id, subreddit=subreddit)
        result = await session.execute(stmt)
        user_sub = result.scalar_one_or_none()
        
        if not user_sub:
            user_sub = UserSubreddit(
                user_id=user_id,
                discord_name=discord_name,
                subreddit=subreddit
            )
            session.add(user_sub)
            await session.flush()
            
        return user_sub

    def _post_matches_filter(
        self, 
        post: asyncpraw.models.Submission,
        keywords: List[str]
    ) -> bool:
        """Check if a post matches the filter keywords."""
        return all(
            keyword.lower() in post.title.lower() 
            for keyword in keywords
        )

    async def _send_notification(
        self,
        user: discord.User,
        post: asyncpraw.models.Submission
    ) -> None:
        """Send a notification to a user about a matching post."""
        post_url = f"https://reddit.com{post.permalink}"
        await user.send(f"Match found: {post.title}\n{post_url}")
    

    async def _get_or_create_entry_filter(
        self,
        session: AsyncSession,
        user_subreddit_id: int,
        entry_name: str,
        keywords: List[str]
    ) -> EntryFilter:
        """Get or create an EntryFilter."""
        stmt = select(EntryFilter).filter_by(
            user_subreddit_id=user_subreddit_id,
            entry_name=entry_name
        )
        result = await session.execute(stmt)
        entry = result.scalar_one_or_none()
        
        if not entry:
            entry = EntryFilter(
                user_subreddit_id=user_subreddit_id,
                entry_name=entry_name,
                keywords=','.join(keywords)
            )
            session.add(entry)
            await session.flush()
        else:
            entry.keywords = ','.join(keywords)
            entry.updated_at = datetime.now(timezone.utc)
        
        return entry

    async def _process_all_filters(
        self,
        discord_client: discord.Client,
        reddit: asyncpraw.Reddit
    ) -> None:
        """Process all filters and send notifications for matches."""
        async with self.session_factory() as session:
            # Get all unique subreddits to minimize API calls
            stmt = select(UserSubreddit.subreddit).distinct()
            result = await session.execute(stmt)
            subreddits = [row[0] for row in result]
            
            for subreddit_name in subreddits:
                try:
                    # Get posts for this subreddit
                    posts = await self.check_subreddit(reddit, subreddit_name)
                    
                    if not posts:
                        continue

                    # Get latest post time
                    latest_post_time = max(
                        datetime.fromtimestamp(post.created_utc, tz=timezone.utc)
                        for post in posts
                    )

                    
                    # Get UserSubreddits with entries
                    stmt = (
                        select(UserSubreddit)
                        .options(selectinload(UserSubreddit.entries))
                        .filter_by(subreddit=subreddit_name)
                    )
                    result = await session.execute(stmt)
                    user_subs = result.scalars().all()
                    
                    # Process each user's filters
                    for user_sub in user_subs:
                        for entry in user_sub.entries:
                            try:
                                cutoff = (
                                    entry.last_check_at.replace(tzinfo=timezone.utc)  # Add UTC tzinfo
                                    if entry.last_check_at 
                                    else datetime.min.replace(tzinfo=timezone.utc)
                                )
                                
                                relevant_posts = [
                                    post for post in posts
                                    if self._get_post_datetime(post) > cutoff
                                ]
                                
                                if relevant_posts:
                                    match_count = await self.process_matches(
                                        discord_client, relevant_posts, user_sub, entry
                                    )
                                    
                                    if match_count > 0:
                                        
                                        entry.last_check_at = latest_post_time.astimezone(timezone.utc)
                                        await session.commit()  # Explicit commit after update
                                        
                                        logger.info(
                                            f"Sent {match_count} matches to user "
                                            f"{user_sub.discord_name} for {subreddit_name}"
                                        )
                                    
                                    # Update timestamp after successful processing
                                    entry.last_check_at = latest_post_time.astimezone(timezone.utc)
                                    logger.info(
                                        f"Updated last_check_at for entry {entry.entry_name} "
                                        f"to {latest_post_time.astimezone(timezone.utc)}"
                                    )

                            except Exception as e:
                                logger.error(
                                    f"Error processing entry {entry.entry_name}: {e}"
                                )
                                raise  # Let the outer transaction handle rollback

                except RedditMonitorError as e:
                    logger.error(f"Error processing subreddit {subreddit_name}: {e}")

    def _get_post_datetime(self, post: asyncpraw.models.Submission) -> datetime:
        """Convert post created_utc to timezone-aware datetime."""
        return datetime.fromtimestamp(post.created_utc, tz=timezone.utc)
            