import datetime
import typing as T

from sqlalchemy.orm import Session

from quickfeed import api
import logging
logger = logging.getLogger(__name__)


def entrypoint(session_maker: T.Generator[Session, None, None], func: T.Callable[[Session], T.Iterator[str]]):
    logger.debug("Starting job: %s", func.__name__)
    with session_maker() as session:
        gen = func(session)
        for _ in gen:
            pass
    logger.debug("Done job: %s", func.__name__)


def update_feeds(session: Session):
    yield "Updating all feeds"
    for feed in api.get_feeds(session):
        yield feed.site_url
        feed_data = api.get_feed_data(feed.feed_url)
        for entry in feed_data.entries:
            if not hasattr(entry, 'id'):
                article_id = entry.link
            else:
                article_id = entry.id
            if not api.get_article(session, feed.id, article_id):
                date = entry.published_parsed[:6]
                api.add_article(
                    session,
                    feed.id,
                    article_id,
                    entry.title,
                    entry.link,
                    entry.description if hasattr(entry, 'description') else '',
                    datetime.datetime(*date),
                    datetime.datetime.now()
                )
        yield "Done"
        feed.feed_last_updated = datetime.datetime.now()
        session.commit()
