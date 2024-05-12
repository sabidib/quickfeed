import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class ModelMixin(Base):
    __abstract__ = True
    created_at = Column(DateTime, default=datetime.datetime.now)
    updated_at = Column(DateTime, default=datetime.datetime.now, onupdate=datetime.datetime.now)


class List(ModelMixin):
    __tablename__ = 'list'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=False)
    order_number = Column(Integer, nullable=False)


class ArticleList(ModelMixin):
    __tablename__ = 'article_list'
    article_id = Column(Integer, ForeignKey('article.id'), primary_key=True)
    list_id = Column(Integer, ForeignKey('list.id'), primary_key=True)


class Category(ModelMixin):
    __tablename__ = 'category'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=False)
    feeds = relationship('Feed', backref='category')
    order_number = Column(Integer, nullable=False)


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
    category_id = Column(Integer, ForeignKey('category.id'), nullable=False)


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
