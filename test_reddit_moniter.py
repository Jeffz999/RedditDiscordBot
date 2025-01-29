import unittest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, func
from reddit_monitor import RedditMonitor, UserSubreddit, EntryFilter
from models import Base

# Decorator to run async test methods
def async_test(func):
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))
    return wrapper

class TestRedditMonitorSQLite(unittest.TestCase):
    async def asyncSetUp(self):
        """Async setup: Create async engine and tables, initialize session factory."""
        # Using async SQLite engine with aiosqlite driver for in-memory database
        self.engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        # Create tables using async connection
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        # Async session factory (replaces synchronous sessionmaker)
        self.Session = async_sessionmaker(bind=self.engine, expire_on_commit=False)

    async def asyncTearDown(self):
        """Async teardown: Drop tables and dispose engine."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()

    @async_test
    async def test_add_filter_1(self):
        """Test adding a filter - now uses async setup and async ORM methods."""
        await self.asyncSetUp()
        try:
            # Initialize RedditMonitor with async session factory
            reddit_monitor = RedditMonitor(
                client_id='dummy_id',
                client_secret='dummy_secret',
                user_agent='dummy_agent',
                session_factory=self.Session,
                cache_timeout=600,
                max_posts=100
            )

            user_id = "test_user"
            discord_name = "test_discord"
            subreddit = "test_subreddit"
            entry_name = "test_entry"
            keywords = ["keyword1", "keyword2"]

            # Await the async add_filter method
            add_result = await reddit_monitor.add_filter(
                user_id=user_id,
                discord_name=discord_name,
                subreddit=subreddit,
                entry_name=entry_name,
                keywords=keywords
            )
            
            print(add_result)

            # Verify using async session
            async with self.Session() as session:
                # Query UserSubreddit
                user_sub_result = await session.execute(
                    select(UserSubreddit).filter_by(user_id=user_id, subreddit=subreddit)
                )
                user_sub = user_sub_result.scalar_one_or_none()
                self.assertIsNotNone(user_sub, "UserSubreddit should be created")
                self.assertEqual(user_sub.discord_name, discord_name, "Discord name should match")

                # Query EntryFilter (renamed from EntryName in Codefile2)
                entry_result = await session.execute(
                    select(EntryFilter).filter_by(user_subreddit_id=user_sub.id, entry_name=entry_name)
                )
                entry = entry_result.scalar_one_or_none()
                self.assertIsNotNone(entry, "EntryFilter should be created")
                self.assertEqual(entry.keywords, ','.join(keywords), "Keywords should match")
        finally:
            await self.asyncTearDown()

    @async_test
    async def test_remove_filter_1(self):
        """Test removing a filter - demonstrates async ORM deletion."""
        await self.asyncSetUp()
        try:
            reddit_monitor = RedditMonitor(
                client_id='dummy_id',
                client_secret='dummy_secret',
                user_agent='dummy_agent',
                session_factory=self.Session,
                cache_timeout=600,
                max_posts=100
            )

            user_id = "test_user"
            subreddit = "test_subreddit"
            entry_name = "test_entry"

            # Setup: Add a filter first
            await reddit_monitor.add_filter(
                user_id=user_id,
                discord_name="test_discord",
                subreddit=subreddit,
                entry_name=entry_name,
                keywords=["keyword1"]
            )

            # Debug: Print initial state
            async with self.Session() as session:
                result = await session.execute(select(EntryFilter))
                entries = result.scalars().all()
                print(f"Initial EntryFilters count: {len(entries)}")
                for e in entries:
                    print(f"Entry: id={e.id}, name={e.entry_name}, user_sub_id={e.user_subreddit_id}")

                result = await session.execute(select(UserSubreddit))
                subs = result.scalars().all()
                print(f"Initial UserSubreddits count: {len(subs)}")
                for s in subs:
                    print(f"UserSub: id={s.id}, user_id={s.user_id}, subreddit={s.subreddit}")

            # Execute remove
            print("Executing remove_filter...")
            remove_result = await reddit_monitor.remove_filter(user_id, subreddit, entry_name)
            print(remove_result)

            # Debug: Print final state
            async with self.Session() as session:
                result = await session.execute(select(EntryFilter))
                entries = result.scalars().all()
                print(f"Final EntryFilters count: {len(entries)}")

                result = await session.execute(select(UserSubreddit))
                subs = result.scalars().all()
                print(f"Final UserSubreddits count: {len(subs)}")

        finally:
            await self.asyncTearDown()

    @async_test
    async def test_get_user_profile_1(self):
        """Test retrieving user profile with async query."""
        await self.asyncSetUp()
        try:
            reddit_monitor = RedditMonitor(
                client_id='dummy_id',
                client_secret='dummy_secret',
                user_agent='dummy_agent',
                session_factory=self.Session,
                cache_timeout=600,
                max_posts=100
            )

            user_id = "test_user"
            await reddit_monitor.add_filter(
                user_id=user_id,
                discord_name="test_discord",
                subreddit="test_sub",
                entry_name="entry1",
                keywords=["kw1"]
            )

            profile = await reddit_monitor.get_user_profile(user_id)
            
            print(profile)
            # Update assertion to match actual format
            self.assertIn("Subreddit: r/test_sub", profile)
            self.assertIn("  - entry1: kw1", profile)
        finally:
            await self.asyncTearDown()

if __name__ == '__main__':
    unittest.main()