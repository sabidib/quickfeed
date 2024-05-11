import datetime

import feedparser
from sqlalchemy import select
from sqlalchemy.orm import Session

from quickfeed import models


def get_feeds(session: Session):
    stmt = select(models.Feed)
    return session.scalars(stmt).all()

def get_feed_by_uri(session: Session, feed_url: str):
    stmt = select(models.Feed).filter(models.Feed.feed_url == feed_url)
    return session.scalars(stmt).one_or_none()

def get_feed_by_id(session: Session, feed_id: str):
    stmt = select(models.Feed).filter(models.Feed.id == feed_id)
    return session.scalars(stmt).one_or_none()

def delete_article_by_id(session: Session, article_id: str):
    stmt = select(models.Article).filter(models.Article.id == article_id)
    article = session.scalars(stmt).one()
    session.delete(article)

def delete_feed_and_articles_by_id(session: Session, feed_id: str) -> bool:
    stmt = select(models.Feed).filter(models.Feed.id == feed_id)
    feed = session.scalars(stmt).one_or_none()
    if feed is None:
        return False
    for article in feed.articles:
        delete_article_by_id(session, article.id)
    session.delete(feed)
    return True

def get_last_updated(session: Session):
    stmt = select(models.Feed).order_by(models.Feed.feed_last_updated.desc()).limit(1)
    return session.scalars(stmt).first()

def get_default_category(session: Session):
    stmt = select(models.Category).filter(models.Category.name == 'Default')
    return session.scalars(stmt).one_or_none()

def get_feed_data(feed_url: str):
    feed = feedparser.parse(feed_url)
    return feed

def get_feed_articles(session: Session, feed_id: int):
    stmt = select(models.Article).filter(models.Article.feed_id == feed_id)
    return session.scalars(stmt).all()

def get_feeds_by_category_name(session: Session, category_name: str):
    stmt = select(models.Feed).join(models.Category).filter(models.Category.name == category_name)
    return session.scalars(stmt).all()

def delete_category(session: Session, category_id: int):
    stmt = select(models.Category).filter(models.Category.id == category_id)
    category = session.scalars(stmt).one()
    session.delete(category)


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

def get_article_by_id(db: Session, article_id: str):
    stmt = select(models.Article).filter(models.Article.id == article_id)
    return db.scalars(stmt).one_or_none()


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


def add_feed(db: Session, feed_url: str, site_url: str, title: str, description: str, category_id: int = None):
    feed = models.Feed(feed_url=feed_url,
                       site_url=site_url,
                       title=title,
                       description=description,
                       added_at=datetime.datetime.now(),
                       category_id=category_id
                       )
    db.add(feed)
    return feed

def get_feeds_by_category_id(db: Session, category_id: int):
    stmt = select(models.Feed).filter(models.Feed.category_id == category_id)
    return db.scalars(stmt).all()

def add_category(db: Session, name: str, description: str, order_number: int):
    category = models.Category(name=name, description=description, order_number=order_number)
    db.add(category)
    return category

def get_category_by_name(db: Session, name: str):
    stmt = select(models.Category).filter(models.Category.name == name)
    return db.scalars(stmt).one_or_none()

def get_category_by_id(db: Session, category_id: int):
    stmt = select(models.Category).filter(models.Category.id == category_id)
    return db.scalars(stmt).one_or_none()

def add_feed_to_category(db: Session, feed_id: int, category: models.Category):
    feed_stmt = select(models.Feed).filter(models.Feed.id == feed_id)
    feed = db.scalars(feed_stmt).one()
    feed.category = category
    return feed


def remove_feed(db: Session, feed_id: int):
    feed_stmt = select(models.Feed).filter(models.Feed.id == feed_id)
    feed = db.scalars(feed_stmt).one()
    db.delete(feed)
    db.commit()
    return feed

def get_categories(db: Session):
    stmt = select(models.Category)
    return db.scalars(stmt).all()

def get_bookmark_list(db: Session):
    stmt = select(models.List).filter(models.List.name == 'Bookmarks')
    return db.scalars(stmt).one_or_none()

def get_article_in_list(db: Session, list_id: int, article_id: str):
    stmt = select(models.ArticleList).filter(models.ArticleList.article_id == article_id).filter(models.ArticleList.list_id == list_id)
    return db.scalars(stmt).one_or_none()

def add_article_to_list(db: Session, list_id: int, article_id: str):
    article_list = models.ArticleList(article_id=article_id, list_id=list_id)
    db.add(article_list)
    db.commit()
    return article_list

def get_articles_in_list(db: Session, list_id: int):
    stmt = select(models.ArticleList).filter(models.ArticleList.list_id == list_id)
    return db.scalars(stmt).all()

def get_list(db: Session, list_id: int):
    stmt = select(models.List).filter(models.List.id == list_id)
    return db.scalars(stmt).one_or_none()
