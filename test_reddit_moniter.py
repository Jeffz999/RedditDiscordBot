import unittest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest import mock
from unittest.mock import AsyncMock, MagicMock, patch
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
    async def test_remove_filter_single_entry(self):
        """Test removing a filter when it's the only entry for a UserSubreddit."""
        await self.asyncSetUp()
        try:
            reddit_monitor = RedditMonitor(
                client_id='dummy_id',
                client_secret='dummy_secret',
                user_agent='dummy_agent',
                session_factory=self.Session,
                max_posts=100
            )

            # Setup: Add a single filter
            user_id = "test_user"
            subreddit = "test_subreddit"
            entry_name = "test_entry"
            
            await reddit_monitor.add_filter(
                user_id=user_id,
                discord_name="test_discord",
                subreddit=subreddit,
                entry_name=entry_name,
                keywords=["keyword1"]
            )
            
            # Remove the filter
            remove_result = await reddit_monitor.remove_filter(user_id, subreddit, entry_name)
            
            # Verify database state
            async with self.Session() as session:
                # Check UserSubreddit was deleted
                user_sub_result = await session.execute(
                    select(UserSubreddit).filter_by(
                        user_id=user_id,
                        subreddit=subreddit
                    )
                )
                user_sub = user_sub_result.scalar_one_or_none()
                self.assertIsNone(user_sub, "UserSubreddit should be deleted")
                
                # Check EntryFilter was deleted
                entry_result = await session.execute(
                    select(EntryFilter).filter_by(entry_name=entry_name)
                )
                entry = entry_result.scalar_one_or_none()
                self.assertIsNone(entry, "EntryFilter should be deleted")
                
        finally:
            await self.asyncTearDown()

    @async_test
    async def test_remove_filter_multiple_entries(self):
        """Test removing one filter when multiple exist for a UserSubreddit."""
        await self.asyncSetUp()
        try:
            reddit_monitor = RedditMonitor(
                client_id='dummy_id',
                client_secret='dummy_secret',
                user_agent='dummy_agent',
                session_factory=self.Session,
                max_posts=100
            )

            # Setup: Add two filters
            user_id = "test_user"
            subreddit = "test_subreddit"
            discord_name = "test_discord"
            
            # Add first filter
            await reddit_monitor.add_filter(
                user_id=user_id,
                discord_name=discord_name,
                subreddit=subreddit,
                entry_name="entry1",
                keywords=["keyword1"]
            )
            
            # Add second filter
            await reddit_monitor.add_filter(
                user_id=user_id,
                discord_name=discord_name,
                subreddit=subreddit,
                entry_name="entry2",
                keywords=["keyword2"]
            )
            
            # Remove one filter
            remove_result = await reddit_monitor.remove_filter(
                user_id,
                subreddit,
                "entry1"
            )
            
            # Verify database state
            async with self.Session() as session:
                # Check UserSubreddit still exists
                user_sub_result = await session.execute(
                    select(UserSubreddit).filter_by(
                        user_id=user_id,
                        subreddit=subreddit
                    )
                )
                user_sub = user_sub_result.scalar_one_or_none()
                self.assertIsNotNone(user_sub, "UserSubreddit should still exist")
                
                # Check deleted EntryFilter is gone
                entry1_result = await session.execute(
                    select(EntryFilter).filter_by(entry_name="entry1")
                )
                entry1 = entry1_result.scalar_one_or_none()
                self.assertIsNone(entry1, "EntryFilter 'entry1' should be deleted")
                
                # Check other EntryFilter still exists
                entry2_result = await session.execute(
                    select(EntryFilter).filter_by(entry_name="entry2")
                )
                entry2 = entry2_result.scalar_one_or_none()
                self.assertIsNotNone(entry2, "EntryFilter 'entry2' should still exist")
                
        finally:
            await self.asyncTearDown()
            
    
    @async_test
    async def test_remove_last_entry_deletes_user_subreddit(self):
        await self.asyncSetUp()
        try:
            reddit_monitor = RedditMonitor(
                client_id='dummy_id',
                client_secret='dummy_secret',
                user_agent='dummy_agent',
                session_factory=self.Session,
                max_posts=100
            )
            await reddit_monitor.add_filter("user1", "test", "test_sub", "entry1", ["test"])

            # Remove the only entry
            await reddit_monitor.remove_filter("user1", "test_sub", "entry1")

            # Verify UserSubreddit deleted
            async with self.Session() as session:
                user_sub = await session.get(UserSubreddit, 1)
                self.assertIsNone(user_sub)
        finally:
            await self.asyncTearDown()        
            
    
    @async_test
    async def test_add_multiple_entries_and_remove_one(self):
        await self.asyncSetUp()
        try:
            reddit_monitor = RedditMonitor(
                client_id='dummy_id',
                client_secret='dummy_secret',
                user_agent='dummy_agent',
                session_factory=self.Session,
                max_posts=100
            )
            await reddit_monitor.add_filter("user1", "test", "test_sub", "entry1", ["test1"])
            await reddit_monitor.add_filter("user1", "test", "test_sub", "entry2", ["test2"])

            # Remove one entry
            await reddit_monitor.remove_filter("user1", "test_sub", "entry1")

            # Verify remaining entry
            async with self.Session() as session:
                user_sub = await session.get(UserSubreddit, 1)
                self.assertEqual(len(user_sub.entries), 1)
                self.assertEqual(user_sub.entries[0].entry_name, "entry2")
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
            
    @async_test
    async def test_initial_run_processes_all_posts(self):
        await self.asyncSetUp()
        try:
            # Setup RedditMonitor and add a filter
            reddit_monitor = RedditMonitor(
                client_id='dummy_id',
                client_secret='dummy_secret',
                user_agent='dummy_agent',
                session_factory=self.Session,
                max_posts=100
            )
            await reddit_monitor.add_filter("user1", "test", "test_sub", "entry1", ["test"])

            # Create test posts with varying timestamps
            now = datetime.now(timezone.utc)
            post1 = self._create_mock_post(now - timedelta(minutes=20))
            post2 = self._create_mock_post(now - timedelta(minutes=5))
            test_posts = [post1, post2]

            # Mock check_subreddit and process_matches
            with mock.patch.object(RedditMonitor, 'check_subreddit', AsyncMock(return_value=test_posts)):
                sent_count = 0
                async def mock_process_matches(*args):
                    nonlocal sent_count
                    sent_count = len(args[1])  # All posts are considered matches
                    return sent_count
                reddit_monitor.process_matches = mock_process_matches

                await reddit_monitor._process_all_filters(None, None)

                # Verify all posts processed and last_check_at updated
                self.assertEqual(sent_count, 2)
                async with self.Session() as session:
                    entry = await session.get(EntryFilter, 1)
        
                    # Convert naive datetime from DB to UTC-aware
                    db_time = entry.last_check_at.replace(tzinfo=timezone.utc)
                    expected_time = datetime.fromtimestamp(post2.created_utc, tz=timezone.utc)
                
                    self.assertEqual(db_time, expected_time)
        finally:
            await self.asyncTearDown()
                
                
    @async_test
    async def test_subsequent_run_processes_new_posts_only(self):
        await self.asyncSetUp()
        try:
            reddit_monitor = RedditMonitor(
                client_id='dummy_id',
                client_secret='dummy_secret',
                user_agent='dummy_agent',
                session_factory=self.Session,
                max_posts=100
            )
            await reddit_monitor.add_filter("user1", "test", "test_sub", "entry1", ["test"])

            # Set initial last_check_at
            initial_check_time = datetime.now(timezone.utc) - timedelta(minutes=10)
            async with self.Session() as session:
                entry = await session.get(EntryFilter, 1)
                entry.last_check_at = initial_check_time
                await session.commit()

            # Mock posts: one old, one new
            post_old = self._create_mock_post(initial_check_time - timedelta(minutes=5))
            post_new = self._create_mock_post(initial_check_time + timedelta(minutes=5))
            with mock.patch.object(RedditMonitor, 'check_subreddit', AsyncMock(return_value=[post_old, post_new])):
                sent_count = 0
                async def mock_process_matches(*args):
                    nonlocal sent_count
                    sent_count = len(args[1])
                    return sent_count
                reddit_monitor.process_matches = mock_process_matches

                await reddit_monitor._process_all_filters(None, None)

                # Only new post processed
                self.assertEqual(sent_count, 1)
                async with self.Session() as session:
                    entry = await session.get(EntryFilter, 1)
                    db_time = entry.last_check_at.replace(tzinfo=timezone.utc)
                    self.assertEqual(db_time, datetime.fromtimestamp(post_new.created_utc, tz=timezone.utc))
        finally:
            await self.asyncTearDown()
            
            
    def _create_mock_post(self, post_time: datetime) -> MagicMock:
        post = MagicMock()
        post.created_utc = post_time.timestamp()
        post.title = "Test Post"
        post.permalink = "/r/test/post"
        return post

if __name__ == '__main__':
    unittest.main()