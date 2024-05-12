# QuickFeed

## What is this?

QuickFeed is a super fast HTML only RSS/ATOM reader. Uses FastAPI and sqlalchemy server side.

### Features
- Feed subscription.
- Manual categories for feeds.
- Starring articles.
- Periodic background and on-demand feed fetching.
- Articles marked as read when opened.
- Configurable basic auth.
- Uses SQLAlchemy so most databases can be used as a backend.

## Why?

I wanted a dead simple RSS feed reader akin to early Google Reader that could be fast enough to be a homepage without caching.

I couldn't find one that met those requirements, so I built it.


## Running it


Start by installing the dependencies with:
```
poetry install
```

Set up the database:
```
poetry run alembic upgrade head
```

You can then launch the server with:
```
poetry run python quickfeed/run_server.py
```

You can adjust configurations in `config.json`.


The site will be available at `http://localhost:8000`.


You can add feeds by pressing the `+` button on the sidebar next to `Feeds`.



