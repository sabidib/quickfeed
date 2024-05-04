import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class ModelMixin(Base):
    __abstract__ = True
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.datetime.now)
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)


class Category(ModelMixin):
    __tablename__ = 'category'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=False)


# Models for an RSS feed reader
class Feed(ModelMixin):
    __tablename__ = 'feed'
    id = Column(Integer, primary_key=True, autoincrement=True)
    feed_url = Column(String, nullable=False)
    site_url = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    added_at = Column(DateTime, nullable=False)
    feed_last_updated = Column(DateTime, nullable=True)
    category_id = Column(Integer, ForeignKey('category.id'))


class Article(ModelMixin):
    __tablename__ = 'article'
    id = Column(Integer, primary_key=True, autoincrement=True)
    feed_id = Column(Integer, ForeignKey('feed.id'))
    unique_id = Column(String, nullable=False)
    title = Column(String, nullable=False)
    link = Column(String, nullable=False)
    read_at = Column(DateTime, nullable=True)
    description = Column(String, nullable=False)
    published_at = Column(DateTime, nullable=False)
    added_at = Column(DateTime, nullable=False)
    feed = relationship('Feed', backref='articles')
