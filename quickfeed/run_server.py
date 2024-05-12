import os
import uvicorn
from quickfeed import utils

if __name__ == "__main__":
    config = utils.get_config("config.json")
    uvicorn.run("quickfeed.server:app",
                host=config["host"],
                port=config["port"],
                ssl_keyfile=config["ssl_keyfile"],
                ssl_certfile=config["ssl_certfile"]
                )

