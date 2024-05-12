
import typing as T
from os.path import normpath
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, Form, Header, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session

from quickfeed import api, jobs

router = APIRouter()

VALID_REDIRECT_PATHS: T.List[str] = [
    "/feed",
    "/feeds",
    "/bookmarks"
]
DEFAULT_REDIRECT_PATH: str = "/feeds"


def construct_redirect_url(path: str, query: str) -> str:
    """Constructs the redirect URL from path and query string."""
    if query:
        return f"{path}?{query}"
    return path


def valid_redirect(url: str) -> str:
    parsed_url = urlparse(url)
    normalized_path: str = normpath(parsed_url.path)

    try:
        normalized_path = bytes(normalized_path, "utf-8").decode("utf-8")
    except UnicodeDecodeError:
        return '/'

    if normalized_path in VALID_REDIRECT_PATHS:
        return construct_redirect_url(normalized_path, parsed_url.query)

    if normalized_path.startswith("/feed/"):
        return construct_redirect_url(normalized_path, parsed_url.query)

    if normalized_path.startswith("/feed"):
        return construct_redirect_url(normalized_path, parsed_url.query)

    return DEFAULT_REDIRECT_PATH


def templated_response(request: Request, name: str, context: T.Dict[str, T.Any]) -> HTMLResponse:
    if "sidebar" in context:
        raise ValueError("Key 'sidebar' is reserved in context")
    with request.app.state.session_maker() as session:  # type: Session
        context["sidebar"] = get_sidebar_data(session)
    return request.app.state.templates.TemplateResponse(
        request=request,
        name=name,
        context=context
    )


def get_sidebar_data(session: Session) -> T.Dict[str, T.Any]:
    feeds: T.List[T.Dict[str, T.Any]] = [
        {
            "id": feed.id,
            "title": feed.title,
            "url": feed.site_url,
            "feed_last_updated": feed.feed_last_updated,
            "description": feed.description,
            "added_at": feed.added_at,
            "category": feed.category.name,
            "category_order_number": feed.category.order_number if feed.category else -1
        }
        for feed in sorted(api.get_feeds(session), key=lambda x: x.title)
    ]
    categories: T.Dict[str, T.List[T.Dict[str, T.Any]]] = {}
    for feed in feeds:
        if feed["category"] not in categories:
            categories[feed["category"]] = []
        categories[feed["category"]].append(feed)

    sorted_categories: T.List[T.Tuple[str, T.List[T.Dict[str, T.Any]]]] = sorted(
        categories.items(),
        key=lambda x: (x[1][0]["category_order_number"], x[1][0]["category"])
    )
    return {
        "feeds_by_category": sorted_categories
    }


def get_all_categories(session: Session) -> T.List[T.Dict[str, T.Any]]:
    return [
        {
            "id": category.id,
            "name": category.name,
            "description": category.description,
            "order_number": category.order_number
        }
        for category in api.get_categories(session)
    ]


@router.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/feed")


@router.get("/feed", response_class=HTMLResponse)
def feed_page_index(request: Request, page: T.Optional[int] = 1, per_page: T.Optional[int] = 15) -> HTMLResponse:
    return feed_page(request, category=None, page=page, per_page=per_page)


@router.get("/feed/{category}", response_class=HTMLResponse)
def feed_page_category(
    request: Request,
    category: T.Optional[str] = None,
    page: T.Optional[int] = 1,
    per_page: T.Optional[int] = 15
) -> HTMLResponse:
    return feed_page(request, category=category, page=page, per_page=per_page)


def feed_page(
    request: Request,
    category: T.Optional[str] = None,
    list_id: T.Optional[int] = None,
    page: int = 1,
    per_page: int = 15
) -> HTMLResponse:
    # pylint: disable=too-many-locals
    with request.app.state.session_maker() as session:  # type: Session
        if category is None:
            article_feeds = api.get_feeds(session)
        else:
            article_feeds = api.get_feeds_by_category_name(session, category)

        article_models: T.List[T.Any] = [article for feed in article_feeds for article in feed.articles]

        list_model: T.Optional[T.Any] = None
        if list_id is not None:
            list_model = api.get_list(session, list_id)
            if list_model is None:
                error = "List not found"
                return RedirectResponse(url=f"/feed&error={error}", status_code=303)
            articles_ids_in_list = {
                article.article_id for article in api.get_articles_in_list(session, list_id)
            }
            article_models = [article for article in article_models if article.id in articles_ids_in_list]

        bookmarked_ids: T.Set[int] = set()
        bookmark_list = api.get_bookmark_list(session)
        if bookmark_list:
            bookmarked_articles = api.get_articles_in_list(session, bookmark_list.id)
            bookmarked_ids = {article.article_id for article in bookmarked_articles}

        articles: T.List[T.Dict[str, T.Any]] = [
            {
                "title": article.title,
                "link": article.link,
                "published_at": article.published_at,
                "feed_name": article.feed.title,
                "read_at": article.read_at,
                "id": article.id,
                "bookmarked": article.id in bookmarked_ids
            }
            for article in api.sort_articles(article_models)
        ]

        last_updated_feed = api.get_last_updated(session)
        return templated_response(
            request=request,
            name="index.html",
            context={
                "category": category if category else "All",
                "list_name": list_model.name if list_model else None,
                "page": page,
                "per_page": per_page,
                "total_pages": len(articles) // per_page,
                "articles": articles[(page - 1) * per_page: page * per_page],
                "last_updated": last_updated_feed.feed_last_updated if last_updated_feed else None,
            }
        )


@router.get("/reload_feed")
def reload_feed(request: Request) -> StreamingResponse:
    def generate() -> T.Generator[str, None, None]:
        yield "<html>"
        yield "Reloading the feed, please wait...<br>"
        with request.app.state.session_maker() as session:  # type: Session
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
def redirect(
    request: Request,
    background_tasks: BackgroundTasks,
    article_id: str,
    url: str
) -> RedirectResponse:
    def update_read(article_id: str) -> None:
        with request.app.state.session_maker() as session:  # type: Session
            api.update_read(session, article_id)
            session.commit()
    background_tasks.add_task(update_read, article_id)
    return RedirectResponse(url)


@router.get("/add_feed", response_class=HTMLResponse)
def add_feed_page(request: Request) -> HTMLResponse:
    with request.app.state.session_maker() as session:  # type: Session
        categories = get_all_categories(session)

        return templated_response(
            request=request,
            name="add_feed.html",
            context={
                "categories": categories
            }
        )


@router.post("/delete_feed_process")
def delete_feed(request: Request, feed_id: T.Annotated[str, Form()]) -> RedirectResponse:
    with request.app.state.session_maker() as session:  # type: Session
        if api.delete_feed_and_articles_by_id(session, feed_id):
            message = "Feed deleted successfully"
            session.commit()
            return RedirectResponse(
                url=f"/delete_feed?success={message}",
                status_code=303,
            )
        message = "Feed not found"
        session.rollback()
        return RedirectResponse(
            url=f"/delete_feed?error={message}",
            status_code=303,
        )


@router.get("/delete_feed", response_class=HTMLResponse)
def delete_feed_page(
    request: Request,
    feed_id: T.Optional[int] = None,
    success: T.Optional[str] = None,
    error: T.Optional[str] = None
) -> HTMLResponse:
    with request.app.state.session_maker() as session:  # type: Session
        feed = api.get_feed_by_id(session, feed_id)
        return templated_response(
            request=request,
            name="delete_feed.html",
            context={
                 "success": success,
                 "error": error,
                 "feed": feed
            }
        )


@router.post("/add_feed", response_class=HTMLResponse)
def add_feed_post(
    request: Request,
    uri: T.Annotated[str, Form()],
    category: T.Annotated[str, Form()]
) -> HTMLResponse:
    feed = api.get_feed_data(uri)
    if not feed.entries:
        return templated_response(request=request, name="add_feed.html", context={"error": "No entries found in feed"})

    with request.app.state.session_maker() as session:  # type: Session
        if api.get_feed_by_uri(session, uri):
            return templated_response(request=request, name="add_feed.html", context={"error": "Feed already added"})

        category_obj = None
        if category:
            category_obj = api.get_category_by_name(session, category)
            if category_obj is None:
                category_obj = api.add_category(session, category, "", 0)
        session.flush()
        api.add_feed(
            session,
            feed_url=uri,
            site_url=feed.feed.link,
            title=feed.feed.title,
            description=feed.feed.description if hasattr(feed.feed, "description") else "",
            category_id=category_obj.id if category_obj else None
        )
        session.commit()

    reload_time = request.app.state.config["reload_time_after_new_feed_submit"]
    return templated_response(
        request=request,
        name="add_feed.html",
        context={
            "success": f"Feed added successfully. Refreshing feeds in {reload_time}...",
            "reload_time": reload_time
        }
    )


@router.get("/feeds", response_class=HTMLResponse)
def feeds_page(
    request: Request,
    error: T.Optional[str] = None,
    success: T.Optional[str] = None
) -> HTMLResponse:
    with request.app.state.session_maker() as session:  # type: Session
        feeds = [
            {
                "title": feed.title,
                "site_url": feed.site_url,
                "feed_url": feed.feed_url,
                "feed_last_updated": feed.feed_last_updated,
                "description": feed.description,
                "category": feed.category.name if feed.category else None,
                "id": feed.id
            }
            for feed in sorted(api.get_feeds(session), key=lambda x: x.title)
        ]
        return templated_response(
            request=request,
            name="feeds.html",
            context={
                "categories": get_all_categories(session),
                "error": error,
                "success": success,
                "feeds": feeds
            }
        )


@router.get("/feed_details", response_class=HTMLResponse)
def feed_details(
    request: Request,
    feed_id: str,
    error: T.Optional[str] = None,
    success: T.Optional[str] = None
) -> HTMLResponse:
    with request.app.state.session_maker() as session:  # type: Session
        feed = api.get_feed_by_id(session, feed_id)
        feeds = [
            {
                "title": feed.title,
                "site_url": feed.site_url,
                "feed_url": feed.feed_url,
                "feed_last_updated": feed.feed_last_updated,
                "description": feed.description,
                "category": feed.category.name if feed.category else None,
                "id": feed.id
            }
            for feed in sorted(api.get_feeds(session), key=lambda x: x.title)
        ]
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
            return templated_response(
                request=request,
                name="feed_details.html",
                context={
                    "categories": get_all_categories(session),
                    "feed": {
                        "title": feed.title,
                        "site_url": feed.site_url,
                        "feed_url": feed.feed_url,
                        "feed_last_updated": feed.feed_last_updated,
                        "description": feed.description,
                        "category": feed.category.name if feed.category else None,
                        "id": feed.id,
                        "added_at": feed.added_at
                    },
                    "feeds": feeds,
                    "articles": articles,
                    "error": error,
                    "success": success,
                }
            )

        return templated_response(
            request=request,
            name="feed_details.html",
            context={
                "error": error,
                "success": success,
                "feed": None,
                "feeds": feeds,
                "articles": []
            }
        )


@router.get("/add_category", response_class=HTMLResponse)
def add_category_page(
    request: Request,
    success: T.Optional[str] = None,
    error: T.Optional[str] = None
) -> HTMLResponse:
    return templated_response(
        request=request,
        name="add_category.html",
        context={
            "success": success,
            "error": error
        }
    )


@router.post("/add_category", response_class=HTMLResponse)
async def add_category_post(request: Request) -> RedirectResponse:
    form_data = await request.form()
    category_name: str = form_data.get("category_name")
    category_description: str = form_data.get("category_description")
    category_order_number: int = int(form_data.get("category_order_number"))
    with request.app.state.session_maker() as session:  # type: Session
        if api.get_category_by_name(session, category_name):
            message = f"Category with name {category_name} already exists"
            return RedirectResponse(url=f"/add_category?error={message}", status_code=303)
        api.add_category(session, category_name, category_description, category_order_number)
        session.commit()
        message = f"Category {category_name} added successfully"
        return RedirectResponse(url=f"/add_category?success={message}", status_code=303)


@router.get("/categories", response_class=HTMLResponse)
def categories_page(request: Request) -> HTMLResponse:
    with request.app.state.session_maker() as session:  # type: Session
        categories = get_all_categories(session)
        return templated_response(
            request=request,
            name="categories.html",
            context={
                "categories": categories
            }
        )


@router.get("/category_details", response_class=HTMLResponse)
def category_details(
    request: Request,
    category_id: str,
    error: T.Optional[str] = None,
    success: T.Optional[str] = None
) -> HTMLResponse:
    with request.app.state.session_maker() as session:  # type: Session
        category = api.get_category_by_id(session, category_id)
        feeds = [
            {
                "title": feed.title,
                "site_url": feed.site_url,
                "feed_url": feed.feed_url,
                "feed_last_updated": feed.feed_last_updated,
                "description": feed.description,
                "category": feed.category.name if feed.category else None,
                "id": feed.id
            }
            for feed in sorted(api.get_feeds_by_category_id(session, category_id), key=lambda x: x.title)
        ]
        return templated_response(
            request=request,
            name="category_details.html",
            context={
                "category": category,
                "feeds": feeds,
                "error": error,
                "success": success
            }
        )


@router.get("/delete_category", response_class=HTMLResponse)
def delete_category_get(
    request: Request,
    category_id: int,
    success: T.Optional[str] = None,
    error: T.Optional[str] = None
) -> HTMLResponse:
    with request.app.state.session_maker() as session:  # type: Session
        category = api.get_category_by_id(session, category_id)
        return templated_response(
            request=request,
            name="delete_category.html",
            context={
                "success": success,
                "error": error,
                "category": category
            }
        )


@router.post("/delete_category_process")
def delete_category(
    request: Request,
    category_id: T.Annotated[str, Form()]
) -> RedirectResponse:
    with request.app.state.session_maker() as session:  # type: Session
        category = api.get_category_by_id(session, category_id)
        if not category:
            message = "Category not found"
            return RedirectResponse(url=f"/categories?error={message}", status_code=303)

        feeds = api.get_feeds_by_category_id(session, category_id)
        default_category = api.get_default_category(session)
        for feed in feeds:
            feed.category = default_category

        session.delete(category)
        message = "Category deleted successfully"
        session.commit()
        return RedirectResponse(url=f"/categories?success={message}", status_code=303)


@router.post("/update_feeds")
async def update_feeds(request: Request) -> RedirectResponse:
    with request.app.state.session_maker() as session:  # type: Session
        form_data = await request.form()
        for category_feed_key in form_data.keys():
            if category_feed_key.startswith("category_"):
                feed_id_parts = category_feed_key.split("_")
                if len(feed_id_parts) != 3:
                    error = "Invalid form data"
                    return RedirectResponse(url=f"/feeds?error={error}", status_code=303)
                feed_id = feed_id_parts[2]
                if not feed_id.isdigit():
                    error = "Invalid form data"
                    return RedirectResponse(url=f"/feeds?error={error}", status_code=303)
                feed_id = int(feed_id)
                category_id = form_data.get(category_feed_key)
                feed = api.get_feed_by_id(session, feed_id)
                if feed is not None and feed.category_id != category_id:
                    category = api.get_category_by_id(session, category_id)
                    if category is None:
                        error = f"Category not found: {category_id}"
                        return RedirectResponse(url=f"/feeds?error={error}", status_code=303)
                    feed.category = category
                    session.add(feed)
        session.commit()
        success = "Feeds updated successfully"
        return RedirectResponse(url=f"/feeds?success={success}", status_code=303)


@router.post("/update_feed")
async def update_feed(request: Request) -> RedirectResponse:
    with request.app.state.session_maker() as session:  # type: Session
        form_data = await request.form()
        feed_id = form_data.get("feed_id")
        category_id = form_data.get("category_id")
        feed = api.get_feed_by_id(session, feed_id)
        if feed is None:
            error = "Feed not found"
            return RedirectResponse(url=f"/feed_details?error={error}", status_code=303)
        if category_id:
            category = api.get_category_by_id(session, category_id)
            if category is None:
                error = "Category not found"
                return RedirectResponse(url=f"/feed_details?feed_id={feed_id}&error={error}", status_code=303)
            feed.category = category
            session.add(feed)
            session.commit()
        success = "Feed updated successfully"
        return RedirectResponse(url=f"/feed_details?feed_id={feed_id}&success={success}", status_code=303)


@router.post("/update_category")
async def update_category(request: Request) -> RedirectResponse:
    form_data = await request.form()

    category_id = form_data.get("category_id")
    category_name = form_data.get("name")
    if not category_name:
        error = "Category name cannot be empty"
        return RedirectResponse(url=f"/category_details?category_id={category_id}&error={error}", status_code=303)
    category_description = form_data.get("description")
    category_order_number = int(form_data.get("order_number"))

    with request.app.state.session_maker() as session:  # type: Session
        category = api.get_category_by_id(session, category_id)
        if category is None:
            error = "Category not found"
            return RedirectResponse(url=f"/category_details?category_id={category_id}&error={error}", status_code=303)
        category.name = category_name
        category.description = category_description
        category.order_number = category_order_number
        session.add(category)
        session.commit()
        success = "Category updated successfully"
        return RedirectResponse(url=f"/category_details?category_id={category_id}&success={success}", status_code=303)


@router.post("/bookmark")
async def bookmark(request: Request, referer: str = Header(None)) -> RedirectResponse:
    with request.app.state.session_maker() as session:  # type: Session
        form_data = await request.form()
        article_id = form_data.get("article_id")
        article = api.get_article_by_id(session, article_id)
        if article is None:
            error = "Article not found"
            return RedirectResponse(url=f"/feed?error={error}", status_code=303)
        bookmark_list = api.get_bookmark_list(session)
        if bookmark_list is None:
            error = "Bookmark list not found. Internal error."
            return RedirectResponse(url=f"/feed?error={error}", status_code=303)
        article_list = api.get_article_in_list(session, bookmark_list.id, article.id)
        if article_list is None:
            article_list = api.add_article_to_list(session, bookmark_list.id, article.id)
        else:
            session.delete(article_list)

        session.commit()
        return RedirectResponse(url=valid_redirect(referer), status_code=303)


@router.get("/bookmarks", response_class=HTMLResponse)
def bookmarks_page(
    request: Request,
    page: T.Optional[int] = 1,
    per_page: T.Optional[int] = 15
) -> HTMLResponse:
    with request.app.state.session_maker() as session:  # type: Session
        bookmark_list = api.get_bookmark_list(session)
        return feed_page(request, page=page, per_page=per_page, list_id=bookmark_list.id)
