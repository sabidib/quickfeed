# QuickFeed

## What is this?

QuickFeed is a super fast HTML only RSS/ATOM reader. Uses FastAPI and Sqlite server side.

### Features
- Feed subscription
- Periodic background and on-demand feed fetching.
- Articles marked as read when followed.

## Why?


1. I wanted an RSS feed reader that could double as a homepage and load quickly when a new tab was open. I didn't find anything that could respond within realtime (less than 100ms), so I built one.

2. I also haven't found an dead-simple RSS reader that I've been happy with since Google Reader's retirment.


## Running it


Start by installing the dependencies with:
```
poetry install
```

You can then launch the server with:
```
poetry run scripts/run_server.py
```

You can adjust configurations in `config.json`.



