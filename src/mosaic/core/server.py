import uvicorn
from fastapi import FastAPI, APIRouter

from mosaic.utils.logger import get_logger

logger = get_logger(__name__)

class MosaicServer:
    def __init__(self, host: str, port: int):
        self._host = host
        self._port = port
        self._app = FastAPI()
        self._router = APIRouter()
        self._setup_routes()
        self._app.include_router(self._router)


    def _setup_routes(self):
        pass


    def run(self):
        uvicorn.run(self._app, host=self._host, port=self._port)