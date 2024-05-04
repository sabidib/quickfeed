import typing as T

from fastapi import APIRouter, BackgroundTasks, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse

from quickfeed import api, jobs

router = APIRouter()


@router.get("/")
def root():
    return RedirectResponse(url="/feed")


@router.get("/feed", response_class=HTMLResponse)
def feed_page(request: Request, page: T.Optional[int] = 1, per_page: T.Optional[int] = 15):
    with request.app.state.sesion_maker() as session:
        articles = [
            {
                "title": article.title,
                "link": article.link,
                "published_at": article.published_at,
                "feed_name": article.feed.title,
                "read_at": article.read_at,
                "id": article.id,
            }
            for article in api.sort_articles(api.get_articles(session))
        ]
        feeds = [
            {
                "title": feed.title,
                "url": feed.site_url,
                "feed_last_updated": feed.feed_last_updated,
                "description": feed.description,
                "added_at": feed.added_at
            }
            for feed in sorted(api.get_feeds(session), key=lambda x: x.title)
        ]
        feed_max = [feed["feed_last_updated"] for feed in feeds if feed["feed_last_updated"]]
        last_updated = max(feed_max) if feed_max else None
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "page": page,
            "per_page": per_page,
            "total_pages": len(articles) // per_page,
            "articles": articles[(page - 1) * per_page: page * per_page],
            "feeds": feeds,
            "last_updated": last_updated
        }
    )


@router.get("/reload_feed")
def reload_feed(request: Request):
    def generate():
        yield "<html>"
        yield "Reloading the feed, please wait...<br>"
        with request.app.state.sesion_maker() as session:
            val = jobs.update_feeds(session)
            next(val) # pylint: disable=stop-iteration-return
            while True:
                try:
                    yield f"Updating: {next(val)}..."
                    next(val)
                    yield "Done!<br>"
                except StopIteration:
                    break
        yield "<head>"
        yield '<meta http-equiv="refresh" content="1;url=/feed">'
        yield "</head>"
        yield "<body>"
        yield "Redirecting to the feed page...<br>"
        yield "If the page does not reload, click <a href='/feed'>here</a>."
        yield "</body>"
        yield "</html>"

    return StreamingResponse(generate(), media_type="text/html")


@router.get("/redirect")
def redirect(request: Request, background_tasks: BackgroundTasks, article_id: str, url: str):
    def update_read(article_id: str):
        with request.app.state.sesion_maker() as session:
            api.update_read(session, article_id)
    background_tasks.add_task(update_read, article_id)
    return RedirectResponse(url)


@router.get("/add_feed", response_class=HTMLResponse)
def add_feed_get(request: Request,):
    return request.app.state.templates.TemplateResponse("add_feed.html", {"request": {}})

@router.post("/delete_feed_process")
def delete_feed(request: Request, feed_id: T.Annotated[str, Form()]):
    with request.app.state.sesion_maker() as session:
        if api.delete_feed_and_articles_by_id(session, feed_id):
            message = "Feed deleted successfully"
            session.commit()
            return RedirectResponse(
                url=f"/delete_feed?success={message}",
                status_code=303,
            )
        else:
            message = "Feed not found"
            session.rollback()
            return RedirectResponse(
                url=f"/delete_feed?error={message}",
                status_code=303,
            )


@router.get("/delete_feed")
def delete_feed_get(request: Request,
                    feed_id: T.Optional[int] = None,
                    success: T.Optional[str] = None,
                    error: T.Optional[str] = None):
    with request.app.state.sesion_maker() as session:
        feed = api.get_feed_by_id(session, feed_id)
        return request.app.state.templates.TemplateResponse(
            request=request,
            name="delete_feed.html",
            context={
                 "success": success,
                 "error": error,
                 "feed": feed
             }
        )


@router.post("/add_feed", response_class=HTMLResponse)
def add_feed_post(request: Request, uri: T.Annotated[str, Form()]):
    feed = api.get_feed_data(uri)
    if not feed.entries:
        return request.app.state.templates.TemplateResponse(request=request, name="add_feed.html", context={
                                                            "error": "No entries found in feed"})

    with request.app.state.sesion_maker() as session:
        if api.get_feed_by_uri(session, uri):
            return request.app.state.templates.TemplateResponse(
                request=request,
                name="add_feed.html",
                context={
                    "error": "Feed already added"
                }
            )

        api.add_feed(
            session,
            feed_url=uri,
            site_url=feed.feed.link,
            title=feed.feed.title,
            description=feed.feed.description)
    reload_time = request.app.state.config["reload_time_after_new_feed_submit"]
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="add_feed.html",
        context={
            "success": f"Feed added successfully. Refreshing feeds in {reload_time}...",
            "reload_time": reload_time
        }
    )




@router.get("/feeds", response_class=HTMLResponse)
def feeds_page(request: Request):
    with request.app.state.sesion_maker() as session:
        feeds = [
            {
                "title": feed.title,
                "site_url": feed.site_url,
                "feed_url": feed.feed_url,
                "feed_last_updated": feed.feed_last_updated,
                "description": feed.description,
                "id": feed.id
            }
            for feed in sorted(api.get_feeds(session), key=lambda x: x.title)
        ]
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="feeds.html",
        context={
            "feeds": feeds
        }
    )


@router.get("/feed_details", response_class=HTMLResponse)
def feed_details(request: Request, feed_id: int):
    with request.app.state.sesion_maker() as session:
        feed = api.get_feed_by_id(session, feed_id)
        if feed is not None:
            articles = [
                {
                    "title": article.title,
                    "link": article.link,
                    "published_at": article.published_at,
                    "read_at": article.read_at,
                    "id": article.id
                }
                for article in api.sort_articles(feed.articles)
            ]
            return request.app.state.templates.TemplateResponse(
                request=request,
                name="feed_details.html",
                context={
                    "feed": {
                        "title": feed.title,
                        "site_url": feed.site_url,
                        "feed_url": feed.feed_url,
                        "feed_last_updated": feed.feed_last_updated,
                        "description": feed.description,
                        "id": feed.id,
                        "added_at": feed.added_at
                    },
                    "articles": articles
                }
            )
        else:
            return request.app.state.templates.TemplateResponse(
                request=request,
                name="feed_details.html",
                context={
                    "feed": None,
                    "articles": []
                }
            )


