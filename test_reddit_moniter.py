import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from reddit_monitor import RedditMonitor, Base, UserSubreddit, EntryName

"""cls.discord_token = os.getenv('DISCORD_TOKEN')
    cls.reddit_secret = os.getenv('REDDIT_SECRET')
    cls.reddit_client_id = os.getenv('REDDIT_CLIENT_ID')
    cls.tester_channel_id = os.getenv('TESTER_CHANNEL_ID')
    cls.user_agent = os.getenv('USER_AGENT')
    cls.db_schema = os.getenv('DB_SCHEMA')
    cls.db_host = os.getenv('DB_HOST')
    cls.db_user = os.getenv('DB_USER')
    cls.db_password = os.getenv('DB_PASSWORD')
    cls.ping_timer = os.getenv('PING_TIMER')
    cls.new_posts = os.getenv('NEW_POSTS')
"""

class TestRedditMonitorSQLite(unittest.TestCase):

    def setUp(self):
        # Connect to an in-memory SQLite database
        self.engine = create_engine('sqlite:///:memory:')
        
        # Create all tables in the database
        Base.metadata.create_all(self.engine)

        # Create a new sessionmaker that binds to the in-memory engine
        self.Session = sessionmaker(bind=self.engine)
        
        

    def tearDown(self):
        # Drop all tables in the database
        Base.metadata.drop_all(self.engine)

    def test_add_filter_1(self):
        # Create a new session
        session = self.Session()

        reddit_monitor = RedditMonitor(client_id='dummy_id', client_secret='dummy_secret', user_agent='dummy_agent',
                                       alchemy_engine=self.engine, alchemy_session=lambda: session)
        

        user_id = "test_user"
        discord_name = "test_discord"
        subreddit = "test_subreddit"
        entry_name = "test_entry"
        keywords = ["keyword1", "keyword2"]

        # Call your method
        reddit_monitor.add_filter(user_id=user_id, discord_name=discord_name, subreddit=subreddit,
                                           entry_name=entry_name, keywords=keywords)

        # Assertions to verify the behavior of add_filter
        user_subreddit = session.query(UserSubreddit).filter_by(user_id=user_id, subreddit=subreddit).first()
        assert user_subreddit is not None, "UserSubreddit should be created"
        assert user_subreddit.discord_name == discord_name, "Discord name should match"
        
        
        entry = session.query(EntryName).filter_by(user_subreddit_id=user_subreddit.id, entry_name=entry_name).first()
        assert entry is not None, "EntryName should be created"
        assert entry.keywords == ','.join(keywords), "Keywords should match"

        # Close the session
        session.close()

    def test_remove_filter_1(self):
        session = self.Session()

        reddit_monitor = RedditMonitor(client_id='dummy_id', client_secret='dummy_secret', user_agent='dummy_agent',
                                       alchemy_engine=self.engine, alchemy_session=lambda: session)
        
        # Assuming add_filter has been tested and works correctly
        # Set up test data by calling add_filter first
        user_id = "test_user"
        discord_name = "test_discord"
        subreddit = "test_subreddit"
        entry_name = "test_entry"
        keywords = ["keyword1", "keyword2"]
        reddit_monitor.add_filter(user_id, discord_name, subreddit, entry_name, keywords)

        # Call the function to remove the filter
        reddit_monitor.remove_filter(user_id, subreddit, entry_name)

        # Assertions
        entry = session.query(EntryName).filter_by(user_subreddit_id=user_id, entry_name=entry_name).first()
        assert entry is None, "EntryName should be removed"
    
    def test_add_remove_1(self):
        session = self.Session()

        reddit_monitor = RedditMonitor(client_id='dummy_id', client_secret='dummy_secret', user_agent='dummy_agent',
                                    alchemy_engine=self.engine, alchemy_session=lambda: session)

        # Setup: Add a filter for an existing subreddit
        user_id = "user1"
        discord_name = "User One"
        subreddit = "subreddit1"
        entry_name1 = "entry1"
        keywords1 = ["keyword1"]
        reddit_monitor.add_filter(user_id=user_id, discord_name=discord_name, subreddit=subreddit,
                                entry_name=entry_name1, keywords=keywords1)

        # Action: Add another filter for the same subreddit but with a different entry
        entry_name2 = "entry2"
        keywords2 = ["keyword2"]
        reddit_monitor.add_filter(user_id=user_id, discord_name=discord_name, subreddit=subreddit,
                                entry_name=entry_name2, keywords=keywords2)

        # Assertions: Check if both entries exist under the same subreddit
        entries = session.query(EntryName).join(UserSubreddit).filter(UserSubreddit.subreddit == subreddit).all()
        assert len(entries) == 2, "There should be two entries for the subreddit"
        assert any(entry.entry_name == entry_name1 for entry in entries), "First entry should exist"
        assert any(entry.entry_name == entry_name2 for entry in entries), "Second entry should exist"

        session.close()
        
    def test_two_users_add_same_entry(self):
        session = self.Session()

        reddit_monitor = RedditMonitor(client_id='dummy_id', client_secret='dummy_secret', user_agent='dummy_agent',
                                    alchemy_engine=self.engine, alchemy_session=lambda: session)

        subreddit = "test_subreddit"
        entry_name = "test_entry"
        keywords = ["keyword1", "keyword2"]

        # User 1 adds an entry
        reddit_monitor.add_filter(user_id="user1", discord_name="UserOne", subreddit=subreddit,
                                entry_name=entry_name, keywords=keywords)

        # User 2 adds the same entry
        reddit_monitor.add_filter(user_id="user2", discord_name="UserTwo", subreddit=subreddit,
                                entry_name=entry_name, keywords=keywords)

        # Assertions
        entries_count = session.query(EntryName).join(UserSubreddit).filter(UserSubreddit.subreddit == subreddit, EntryName.entry_name == entry_name).count()
        self.assertEqual(entries_count, 2, "Both users should have the same entry for the subreddit")

        session.close()


    def test_two_users_add_different_entries(self):
        session = self.Session()

        reddit_monitor = RedditMonitor(client_id='dummy_id', client_secret='dummy_secret', user_agent='dummy_agent',
                                    alchemy_engine=self.engine, alchemy_session=lambda: session)

        subreddit = "test_subreddit"

        # User 1 adds an entry
        reddit_monitor.add_filter(user_id="user1", discord_name="UserOne", subreddit=subreddit,
                                entry_name="entry1", keywords=["keyword1"])

        # User 2 adds a different entry
        reddit_monitor.add_filter(user_id="user2", discord_name="UserTwo", subreddit=subreddit,
                                entry_name="entry2", keywords=["keyword2"])

        # Assertions
        entries = session.query(EntryName).join(UserSubreddit).filter(UserSubreddit.subreddit == subreddit).all()
        self.assertEqual(len(entries), 2, "There should be two different entries for the subreddit")

        session.close()

    def test_user_adds_and_deletes_entry_twice(self):
        session = self.Session()

        reddit_monitor = RedditMonitor(client_id='dummy_id', client_secret='dummy_secret', user_agent='dummy_agent',
                                    alchemy_engine=self.engine, alchemy_session=lambda: session)

        user_id = "user1"
        discord_name = "UserOne"
        subreddit = "test_subreddit"
        entry_name = "test_entry"
        keywords = ["keyword1", "keyword2"]

        # User adds an entry and deletes it twice
        reddit_monitor.add_filter(user_id=user_id, discord_name=discord_name, subreddit=subreddit,
                                entry_name=entry_name, keywords=keywords)
        reddit_monitor.remove_filter(user_id, subreddit, entry_name)
        reddit_monitor.remove_filter(user_id, subreddit, entry_name)  # Attempt to delete the same entry again

        # Assertions
        entry = session.query(EntryName).join(UserSubreddit).filter(UserSubreddit.subreddit == subreddit, EntryName.entry_name == entry_name).first()
        self.assertIsNone(entry, "The entry should be deleted and not found")

        session.close()

    def test_two_users_different_entries_one_deletes(self):
        session = self.Session()

        reddit_monitor = RedditMonitor(client_id='dummy_id', client_secret='dummy_secret', user_agent='dummy_agent',
                                    alchemy_engine=self.engine, alchemy_session=lambda: session)

        subreddit = "test_subreddit"

        # User 1 adds an entry
        reddit_monitor.add_filter(user_id="user1", discord_name="UserOne", subreddit=subreddit,
                                entry_name="entry1", keywords=["keyword1"])

        # User 2 adds a different entry
        reddit_monitor.add_filter(user_id="user2", discord_name="UserTwo", subreddit=subreddit,
                                entry_name="entry2", keywords=["keyword2"])

        # User 1 deletes their entry
        reddit_monitor.remove_filter("user1", subreddit, "entry1")

        # Assertions
        entry1 = session.query(EntryName).join(UserSubreddit).filter(UserSubreddit.subreddit == subreddit, EntryName.entry_name == "entry1").first()
        entry2 = session.query(EntryName).join(UserSubreddit).filter(UserSubreddit.subreddit == subreddit, EntryName.entry_name == "entry2").first()

        self.assertIsNone(entry1, "User 1's entry should be deleted")
        self.assertIsNotNone(entry2, "User 2's entry should still exist")

        session.close()


        
    def test_get_user_profile_1(self):
        session = self.Session()

        reddit_monitor = RedditMonitor(client_id='dummy_id', client_secret='dummy_secret', user_agent='dummy_agent',
                                       alchemy_engine=self.engine, alchemy_session=lambda: session)
        
        user_id = "test_user"
        discord_name = "test_discord"
        subreddit = "test_subreddit"
        entry_name = "test_entry"
        keywords = ["keyword1", "keyword2"]
        
        # Assuming add_filter has been tested and works correctly
        # Set up test data by calling add_filter first
        reddit_monitor.add_filter(user_id, discord_name, subreddit, entry_name, keywords)

        # Call the function
        profile_info = reddit_monitor.get_user_profile(user_id)

        # Assertions
        expected_profile_info = f"{subreddit} - {entry_name}: {', '.join(keywords)}"
        assert expected_profile_info in profile_info, "Profile info should include the added filter"

if __name__ == '__main__':
    unittest.main()
