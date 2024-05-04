from contextlib import contextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from quickfeed import basic_auth, jobs, routes, utils
import logging

config = utils.get_config("config.json")
utils.configure_logging(config)

app = FastAPI()


app.add_middleware(
    basic_auth.AuthMiddleware,
    username=config["user_login"]["username"],
    password=config["user_login"]["password"]
)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
def load_config() -> None:
    app.state.config = config  # Storing the config in the app state for later access

    SessionLocal = utils.setup_database(config['database_url'])

    @contextmanager
    def sesion_maker():
        session_maker = SessionLocal()
        try:
            yield session_maker
        finally:
            session_maker.close()

    app.state.sesion_maker = sesion_maker

    scheduler = BackgroundScheduler()
    scheduler.add_job(jobs.entrypoint, 'interval', minutes=5, args=[sesion_maker, jobs.update_feeds])
    scheduler.start()

    app.state.scheduler = scheduler
    app.state.templates = Jinja2Templates(directory="templates")
    app.include_router(routes.router)


@app.on_event("shutdown")
def shutdown_event() -> None:
    app.state.scheduler.shutdown(wait=False)
