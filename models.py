from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import Column, Integer, String, ForeignKey, Text, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship, declarative_base, Mapped, mapped_column

Base = declarative_base()

class UserSubreddit(Base):
    """Represents a user's subscription to a subreddit with associated filters."""
    __tablename__ = 'user_subreddits'
    __table_args__ = (
        UniqueConstraint('user_id', 'subreddit', name='uix_user_subreddit'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    discord_name: Mapped[str] = mapped_column(String(255), nullable=False)
    subreddit: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),  # Note the timezone=True parameter
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    
    # Relationships
    entries = relationship(
        "EntryFilter",
        back_populates="user_subreddit",
        lazy="selectin",  # Changed from default lazy loading
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"UserSubreddit(id={self.id}, user_id={self.user_id}, subreddit={self.subreddit})"

class EntryFilter(Base):
    """Represents a filter entry with keywords for a user's subreddit subscription."""
    __tablename__ = 'entry_filters'
    __table_args__ = (
        UniqueConstraint('user_subreddit_id', 'entry_name', name='uix_entry_filter'),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_subreddit_id: Mapped[int] = mapped_column(
        ForeignKey('user_subreddits.id'),  # No ondelete clause
        index=True
    )
    entry_name: Mapped[str] = mapped_column(String(255), nullable=False)
    keywords: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    last_check_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),  # Explicitly store with timezone
        nullable=True,
        default=None
    )
    
    # Relationships
    user_subreddit = relationship(
        "UserSubreddit",
        back_populates="entries",
        lazy="selectin"  # Changed from default lazy loading
    )

    def __repr__(self) -> str:
        return f"EntryFilter(id={self.id}, entry_name={self.entry_name})"

    @property
    def keyword_list(self) -> List[str]:
        """Returns the keywords as a list of strings."""
        return [k.strip() for k in self.keywords.split(',') if k.strip()]
