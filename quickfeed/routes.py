import typing as T
import heapq

from fastapi import APIRouter, BackgroundTasks, Form, Request, Header
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from urllib.parse import urlparse, urljoin
from os.path import normpath

from quickfeed import api, jobs

router = APIRouter()

VALID_REDIRECT_PATHS = [
    "/feed",
    "/feeds",
    "/bookmarks"
]
def valid_redirect(path: str):
    # Normalize and clean the path to prevent directory traversal
    parsed_url = urlparse(path)  # Parse the path to handle any query or fragments
    normalized_path = normpath(parsed_url.path)  # Normalize the path to resolve '..' and '.'

    # Ensure the path is not using any URL encoding to disguise malicious paths
    try:
        normalized_path = bytes(normalized_path, "utf-8").decode("utf-8")
    except UnicodeDecodeError:
        return False

    # Check if the normalized path is exactly one of the valid paths
    if normalized_path in VALID_REDIRECT_PATHS:
        return True

    # Check if the path starts with '/feed/' to match subdirectories under '/feed/'
    if normalized_path.startswith("/feed/"):
        return True

    # Fallback to False if none of the conditions are met
    return False

@router.get("/")
def root():
    return RedirectResponse(url="/feed")



@router.get("/feed", response_class=HTMLResponse)
def feed_page(request: Request,
              page: T.Optional[int] = 1,
              per_page: T.Optional[int] = 15):
    return feed_page(request, category=None, page=page, per_page=per_page)

@router.get("/feed/{category}", response_class=HTMLResponse)
def feed_page_category(
        request: Request,
        category: T.Optional[str] = None,
        page: T.Optional[int] = 1,
        per_page: T.Optional[int] = 15
    ):
    return feed_page(request, category=category, page=page, per_page=per_page)

def get_all_categories(session):
    return [
        {
            "id": category.id,
            "name": category.name,
            "description": category.description,
            "order_number": category.order_number
        }
        for category in api.get_categories(session)
    ]


def feed_page(request: Request,
              category: T.Optional[str] = None,
              list_id: T.Optional[int] = None,
              page: T.Optional[int] = 1,
              per_page: T.Optional[int] = 15):
    with request.app.state.sesion_maker() as session:
        if category is None:
            article_feeds = api.get_feeds(session)
        else:
            article_feeds = api.get_feeds_by_category_name(session, category)

        article_models = []
        for feed in article_feeds:
            article_models.extend(feed.articles)

        list_model = None
        if list_id is not None:
            list_model = api.get_list(session, list_id)
            if list_model is None:
                error = "List not found"
                return RedirectResponse(url=f"/feed&error={error}", status_code=303)
            articles_in_list = api.get_articles_in_list(session, list_id)
            articles_ids_in_list = {article.article_id for article in articles_in_list}
            article_models = [article for article in article_models if article.id in articles_ids_in_list]

        bookmarked_ids = set()
        bookmark_list = api.get_bookmark_list(session)
        if bookmark_list:
            bookmarked_articles = api.get_articles_in_list(session, bookmark_list.id)
            bookmarked_ids = {article.article_id for article in bookmarked_articles}

        articles = [
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
        # Get favorites in bookmarks list

        last_updated_feed = api.get_last_updated(session)
        return request.app.state.templates.TemplateResponse(
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
                "sidebar": get_sidebar_data(session)
            }
        )

def get_sidebar_data(session):
    feeds = [
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
    feed_max = [feed["feed_last_updated"] for feed in feeds if feed["feed_last_updated"]]
    last_updated = max(feed_max) if feed_max else None
    categories = {}
    for feed in feeds:
        if feed["category"] not in categories:
            categories[feed["category"]] = []
        categories[feed["category"]].append(feed)

    categories = sorted(
        categories.items(),
        key=lambda x: (x[1][0]["category_order_number"], x[1][0]["category"])
    )
    return {
        "categories": categories
    }



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
    with request.app.state.sesion_maker() as session:
        categories = [
            {
                "id": category.id,
                "name": category.name,
                "description": category.description
            }
            for category in api.get_categories(session)
        ]

        return request.app.state.templates.TemplateResponse(
            request=request,
            name="add_feed.html",
            context={
                "categories": categories,
                "sidebar": get_sidebar_data(session)
            })


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
                 "sidebar": get_sidebar_data(session),
                 "success": success,
                 "error": error,
                 "feed": feed
             }
        )


@router.post("/add_feed", response_class=HTMLResponse)
def add_feed_post(request: Request, uri: T.Annotated[str, Form()], category: T.Annotated[str, Form()]):
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
                    "error": "Feed already added",
                    "sidebar": get_sidebar_data(session)
                }
            )

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
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="add_feed.html",
        context={
            "success": f"Feed added successfully. Refreshing feeds in {reload_time}...",
            "reload_time": reload_time,
            "sidebar": get_sidebar_data(session)
        }
    )




@router.get("/feeds", response_class=HTMLResponse)
def feeds_page(request: Request, error: T.Optional[str] = None, success: T.Optional[str] = None):
    with request.app.state.sesion_maker() as session:
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
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="feeds.html",
        context={
            "categories": get_all_categories(session),
            "error": error,
            "success": success,
            "sidebar": get_sidebar_data(session),
            "feeds": feeds
        }
    )


@router.get("/feed_details", response_class=HTMLResponse)
def feed_details(request: Request, feed_id: str, error: T.Optional[str] = None, success: T.Optional[str] = None):
    with request.app.state.sesion_maker() as session:
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
            return request.app.state.templates.TemplateResponse(
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
                    "sidebar": get_sidebar_data(session)
                }
            )
        else:
            return request.app.state.templates.TemplateResponse(
                request=request,
                name="feed_details.html",
                context={
                    "sidebar": get_sidebar_data(session),
                    "error": error,
                    "success": success,
                    "feed": None,
                    "feeds": feeds,
                    "articles": []
                }
            )

# Add category page
@router.get("/add_category", response_class=HTMLResponse)
def add_category_get(request: Request, success: T.Optional[str] = None, error: T.Optional[str] = None):
    with request.app.state.sesion_maker() as session:
        return request.app.state.templates.TemplateResponse(
            request=request,
            name="add_category.html",
            context={
                "sidebar": get_sidebar_data(session),
                "success": success,
                "error": error
            }
        )

@router.post("/add_category", response_class=HTMLResponse)
async def add_category_post(request: Request):
    form_data = await request.form()
    category_name = form_data.get("category_name")
    category_description = form_data.get("category_description")
    category_order_number = form_data.get("category_order_number")
    with request.app.state.sesion_maker() as session:
        if api.get_category_by_name(session, category_name):
            # redirect to the same page with error message
            message = f"Category with name {category_name} already exists"
            return RedirectResponse(
                url=f"/add_category?error={message}",
                status_code=303,
            )
        api.add_category(session, category_name, category_description, category_order_number)
        session.commit()
        message = f"Category {category_name} added successfully"
        return RedirectResponse(
            url=f"/add_category?success={message}",
            status_code=303,
        )


@router.get("/categories", response_class=HTMLResponse)
def categories_page(request: Request):
    with request.app.state.sesion_maker() as session:
        categories = get_all_categories(session)
        return request.app.state.templates.TemplateResponse(
            request=request,
            name="categories.html",
            context={
                "sidebar": get_sidebar_data(session),
                "categories": categories
            }
        )

@router.get("/category_details", response_class=HTMLResponse)
def category_details(request: Request, category_id: str, error: T.Optional[str] = None, success: T.Optional[str] = None):
    with request.app.state.sesion_maker() as session:
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
        return request.app.state.templates.TemplateResponse(
            request=request,
            name="category_details.html",
            context={
                "category": category,
                "feeds": feeds,
                "error": error,
                "success": success,
                "sidebar": get_sidebar_data(session)
            }
        )

@router.get("/delete_category")
def delete_category_get(request: Request, category_id: T.Optional[int] = None, success: T.Optional[str] = None, error: T.Optional[str] = None):
    with request.app.state.sesion_maker() as session:
        category = api.get_category_by_id(session, category_id)
        return request.app.state.templates.TemplateResponse(
            request=request,
            name="delete_category.html",
            context={
                "sidebar": get_sidebar_data(session),
                "success": success,
                "error": error,
                "category": category
            }
        )

@router.post("/delete_category_process")
def delete_category(request: Request, category_id: T.Annotated[str, Form()]):
    with request.app.state.sesion_maker() as session:
        category = api.get_category_by_id(session, category_id)
        if not category:
            message = "Category not found"
            return RedirectResponse(
                url=f"/categories?error={message}",
                status_code=303,
            )

        feeds = api.get_feeds_by_category_id(session, category_id)
        default_category = api.get_default_category(session)
        for feed in feeds:
            feed.category = default_category

        session.delete(category)
        message = "Category deleted successfully"
        session.commit()
        return RedirectResponse(
            url=f"/categories?success={message}",
            status_code=303,
        )



@router.post("/update_feeds")
async def update_feeds(request: Request):
    with request.app.state.sesion_maker() as session:
        form_data = await request.form()
        for category_feed_key in form_data.keys():
            if category_feed_key.startswith("category_"):
                feed_id = category_feed_key.split("_")
                if len(feed_id) != 3:
                    error = "Invalid form data"
                    return RedirectResponse(url=f"/feeds?error={error}", status_code=303)
                feed_id = feed_id[2]
                if not feed_id.isdigit():
                    error = "Invalid form data"
                    return RedirectResponse(url=f"/feeds?error={error}", status_code=303)
                feed_id = int(feed_id)
                category_id = form_data.get(category_feed_key)
                feed = api.get_feed_by_id(session, feed_id)
                if feed is not None and feed.category_id != category_id:
                    category = api.get_category_by_id(session, category_id)
                    if category is None:
                        error = "Category not found: {category_id}"
                        return RedirectResponse(url=f"/feeds?error={error}", status_code=303)
                    feed.category = category
                    session.add(feed)
        session.commit()
        success = "Feeds updated successfully"
        return RedirectResponse(url=f"/feeds?success={success}", status_code=303)




@router.post("/update_feed")
async def update_feed(request: Request):
    with request.app.state.sesion_maker() as session:
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
async def update_category(request: Request):
    form_data = await request.form()

    category_id = form_data.get("category_id")
    category_name = form_data.get("name")
    if not category_name:
        error = "Category name cannot be empty"
        return RedirectResponse(url=f"/category_details?category_id={category_id}&error={error}", status_code=303)
    category_description = form_data.get("description")
    category_order_number = form_data.get("order_number")

    with request.app.state.sesion_maker() as session:
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
async def bookmark(request: Request, referer: str = Header(None)):
    with request.app.state.sesion_maker() as session:
        form_data = await request.form()
        article_id = form_data.get("article_id")
        article = api.get_article_by_id(session, article_id)
        if article is None:
            error = "Article not found"
            return RedirectResponse(url="/feed?error={error}", status_code=303)
        bookmark_list = api.get_bookmark_list(session)
        if bookmark_list is None:
            error = "Bookmark list not found. Internal error."
            return RedirectResponse(url="/feed?error={error}", status_code=303)
        article_list = api.get_article_in_list(session, bookmark_list.id, article.id)
        if article_list is None:
            # Add to favorites list
            article_list = api.add_article_to_list(session, bookmark_list.id, article.id)
        else:
            # Remove from favorites list
            session.delete(article_list)

        session.commit()
        if referer:
            referer_parsed = urlparse(referer)
            if not valid_redirect(referer_parsed.path):
                redirect_path = "/feed"
            else:
                redirect_path = referer_parsed.path
        else:
            redirect_path = "/feed"

        return RedirectResponse(url=redirect_path, status_code=303)

@router.get("/bookmarks", response_class=HTMLResponse)
def bookmarks_page(request: Request,
                   page: T.Optional[int] = 1,
                   per_page: T.Optional[int] = 15
    ):
    with request.app.state.sesion_maker() as session:
        bookmark_list = api.get_bookmark_list(session)
        return feed_page(request,
                         page=page,
                         per_page=per_page,
                         list_id=bookmark_list.id)

