import logging

import uvicorn

from shopping_agent.config import get_settings

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    s = get_settings()
    uvicorn.run("shopping_agent.api:app", host=s.host, port=s.port)
