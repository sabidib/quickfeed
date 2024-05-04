import datetime

import feedparser
from sqlalchemy import select
from sqlalchemy.orm import Session

from quickfeed import models


def get_feeds(session: Session):
    stmt = select(models.Feed)
    yield from session.scalars(stmt)


def get_feed_data(feed_url: str):
    feed = feedparser.parse(feed_url)
    return feed


def add_article(
    db: Session,
    feed_id: int,
    unique_id: str, title: str, link: str, description: str, published_at: datetime.datetime,
    added_at: datetime.datetime
):
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
    db.commit()
    return article


def get_article(db: Session, feed_id: int, unique_id: str):
    stmt = select(
        models.Article).filter(
        models.Article.feed_id == feed_id).filter(
            models.Article.unique_id == unique_id)
    return db.scalars(stmt).one_or_none()


def sort_articles(articles):
    # Current time for calculating the age of the feed
    now = datetime.datetime.now()

    # Custom sort key function
    def article_sort_key(article):
        # Calculate feed age in days
        feed_age_days = (now - article.feed.added_at).total_seconds() / 86400

        # Weight factor decreases as the feed gets older
        # You can adjust the decay factor to tune how quickly the boost diminishes
        decay_factor = 0.05  # This is an example value; adjust as needed
        weight = max(0, 1 - decay_factor * feed_age_days)

        # Return a tuple that Python's sort can use:
        # Primary sort by published date, boosted by weight if the feed is new
        # Multiply by -1 to ensure that more recent articles come first
        return (-article.published_at.timestamp(), weight)

    # Return the sorted list of articles
    return sorted(articles, key=article_sort_key)


def get_articles(db: Session):
    stmt = select(models.Article)
    return db.scalars(stmt).all()


def update_read(db: Session, article_id: str):
    article_stmt = select(models.Article).filter(models.Article.id == article_id)
    article = db.scalars(article_stmt).one()
    article.read_at = datetime.datetime.now()
    db.commit()


def add_feed(db: Session, feed_url: str, site_url: str, title: str, description: str):
    feed = models.Feed(feed_url=feed_url,
                       site_url=site_url,
                       title=title,
                       description=description,
                       added_at=datetime.datetime.now())
    db.add(feed)
    db.commit()
    return feed


def remove_feed(db: Session, feed_id: int):
    feed_stmt = select(models.Feed).filter(models.Feed.id == feed_id)
    feed = db.scalars(feed_stmt).one()
    db.delete(feed)
    db.commit()
    return feed