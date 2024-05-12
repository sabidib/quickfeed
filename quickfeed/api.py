import datetime
import typing as T

import feedparser
from sqlalchemy import select
from sqlalchemy.orm import Session

from quickfeed import models


# Article-related functions

def get_article_by_id(db: Session, article_id: str) -> T.Optional[models.Article]:
    """Retrieve a single article by its ID."""
    stmt = select(models.Article).filter(models.Article.id == article_id)
    return db.scalars(stmt).one_or_none()

def get_articles(db: Session) -> T.List[models.Article]:
    """Get all articles."""
    stmt = select(models.Article)
    return db.scalars(stmt).all()

def get_article(db: Session, feed_id: int, unique_id: str) -> T.Optional[models.Article]:
    """Get a specific article based on feed ID and the article's unique ID."""
    stmt = select(
        models.Article).filter(
        models.Article.feed_id == feed_id).filter(
            models.Article.unique_id == unique_id)
    return db.scalars(stmt).one_or_none()

def add_article(
    db: Session,
    feed_id: int,
    unique_id: str, title: str, link: str, description: str, published_at: datetime.datetime,
    added_at: datetime.datetime
) -> models.Article:
    """Add a new article to the database."""
    article = models.Article(
        feed_id=feed_id,
        unique_id=unique_id,
        title=title,
        link=link,
        description=description,
        published_at=published_at,
        added_at=added_at
    )
    db.add(article)
    return article

def delete_article_by_id(session: Session, article_id: str):
    """Delete an article by its ID."""
    stmt = select(models.Article).filter(models.Article.id == article_id)
    article = session.scalars(stmt).one()
    session.delete(article)

def update_read(db: Session, article_id: str):
    """Mark an article as read by setting its read_at timestamp."""
    article_stmt = select(models.Article).filter(models.Article.id == article_id)
    article = db.scalars(article_stmt).one()
    article.read_at = datetime.datetime.now()

def sort_articles(articles: T.List[models.Article]) -> T.List[models.Article]:
    """Sort articles based on published date, with a decay factor for feed age."""
    now = datetime.datetime.now()

    def article_sort_key(article: models.Article) -> T.Tuple[float, float]:
        feed_age_days = (now - article.feed.added_at).total_seconds() / 86400
        decay_factor = 0.05
        weight = max(0, 1 - decay_factor * feed_age_days)
        return (-article.published_at.timestamp(), weight)

    return sorted(articles, key=article_sort_key)


# Feed-related functions

def get_feeds(session: Session) -> T.List[models.Feed]:
    """Get all feeds."""
    stmt = select(models.Feed)
    return session.scalars(stmt).all()

def get_feed_by_uri(session: Session, feed_url: str) -> T.Optional[models.Feed]:
    """Retrieve a single feed by its URL."""
    stmt = select(models.Feed).filter(models.Feed.feed_url == feed_url)
    return session.scalars(stmt).one_or_none()

def get_feed_by_id(session: Session, feed_id: str) -> T.Optional[models.Feed]:
    """Retrieve a single feed by its ID."""
    stmt = select(models.Feed).filter(models.Feed.id == feed_id)
    return session.scalars(stmt).one_or_none()

def add_feed(db: Session, feed_url: str, site_url: str, title: str, description: str, category_id: int = None) -> models.Feed:
    """Add a new feed to the database."""
    feed = models.Feed(feed_url=feed_url,
                       site_url=site_url,
                       title=title,
                       description=description,
                       added_at=datetime.datetime.now(),
                       category_id=category_id
                       )
    db.add(feed)
    return feed

def delete_feed_and_articles_by_id(session: Session, feed_id: str) -> bool:
    """Delete a feed and its related articles by the feed's ID."""
    stmt = select(models.Feed).filter(models.Feed.id == feed_id)
    feed = session.scalars(stmt).one_or_none()
    if feed is None:
        return False
    for article in feed.articles:
        delete_article_by_id(session, article.id)
    session.delete(feed)
    return True

def get_last_updated(session: Session) -> T.Optional[models.Feed]:
    """Get the last updated feed."""
    stmt = select(models.Feed).order_by(models.Feed.feed_last_updated.desc()).limit(1)
    return session.scalars(stmt).first()

def get_feeds_by_category_name(session: Session, category_name: str) -> T.List[models.Feed]:
    """Get all feeds that belong to a specific category by category name."""
    stmt = select(models.Feed).join(models.Category).filter(models.Category.name == category_name)
    return session.scalars(stmt).all()

def get_feeds_by_category_id(db: Session, category_id: int) -> T.List[models.Feed]:
    """Get all feeds that belong to a specific category by category ID."""
    stmt = select(models.Feed).filter(models.Feed.category_id == category_id)
    return db.scalars(stmt).all()

# Category-related functions

def get_default_category(session: Session) -> T.Optional[models.Category]:
    """Get the default category."""
    stmt = select(models.Category).filter(models.Category.name == 'Default')
    return session.scalars(stmt).one_or_none()

def get_categories(db: Session) -> T.List[models.Category]:
    """Get all categories."""
    stmt = select(models.Category)
    return db.scalars(stmt).all()

def get_category_by_name(db: Session, name: str) -> T.Optional[models.Category]:
    """Get a specific category by name."""
    stmt = select(models.Category).filter(models.Category.name == name)
    return db.scalars(stmt).one_or_none()

def get_category_by_id(db: Session, category_id: int) -> T.Optional[models.Category]:
    """Get a specific category by ID."""
    stmt = select(models.Category).filter(models.Category.id == category_id)
    return db.scalars(stmt).one_or_none()

def add_category(db: Session, name: str, description: str, order_number: int) -> models.Category:
    """Add a new category to the database."""
    category = models.Category(name=name, description=description, order_number=order_number)
    db.add(category)
    return category

def delete_category(session: Session, category_id: int):
    """Delete a category by its ID."""
    stmt = select(models.Category).filter(models.Category.id == category_id)
    category = session.scalars(stmt).one()
    session.delete(category)

def add_feed_to_category(db: Session, feed_id: int, category: models.Category) -> models.Feed:
    """Assign a feed to a specific category."""
    feed_stmt = select(models.Feed).filter(models.Feed.id == feed_id)
    feed = db.scalars(feed_stmt).one()
    feed.category = category
    return feed


# List and Bookmark functions

def get_bookmark_list(db: Session) -> T.Optional[models.List]:
    """Get the bookmark list."""
    stmt = select(models.List).filter(models.List.name == 'Bookmarks')
    return db.scalars(stmt).one_or_none()

def get_list(db: Session, list_id: int) -> T.Optional[models.List]:
    """Get a specific list by ID."""
    stmt = select(models.List).filter(models.List.id == list_id)
    return db.scalars(stmt).one_or_none()

def get_article_in_list(db: Session, list_id: int, article_id: str) -> T.Optional[models.ArticleList]:
    """Check if an article is in a specific list."""
    stmt = select(models.ArticleList).filter(models.ArticleList.article_id == article_id).filter(models.ArticleList.list_id == list_id)
    return db.scalars(stmt).one_or_none()

def add_article_to_list(db: Session, list_id: int, article_id: str) -> models.ArticleList:
    """Add an article to a list."""
    article_list = models.ArticleList(article_id=article_id, list_id=list_id)
    db.add(article_list)
    return article_list

def get_articles_in_list(db: Session, list_id: int) -> T.List[models.ArticleList]:
    """Get all articles in a specific list."""
    stmt = select(models.ArticleList).filter(models.ArticleList.list_id == list_id)
    return db.scalars(stmt).all()


# Feed parsing function

def get_feed_data(feed_url: str) -> feedparser.FeedParserDict:
    """Parse feed data from a URL."""
    return feedparser.parse(feed_url)

