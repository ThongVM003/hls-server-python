import uvicorn
import json
from fastapi import FastAPI, Response, HTTPException, status, Request
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse

from pydantic import BaseModel
from starlette.responses import RedirectResponse

import argparse
import os
from core import HLSManager

from contextlib import asynccontextmanager
from fastapi.templating import Jinja2Templates


@asynccontextmanager
async def lifespan(app: FastAPI):

    global manager
    manager = HLSManager(os.path.join("metadata", "stream.json"))
    yield

    # Wait for all streams to stop

    manager.stop()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
async def index():
    """
    This endpoint redirects the root URL to the API documentation page.

    Returns:

        RedirectResponse: A redirection to the API documentation page.
    """
    return RedirectResponse(url="/docs")


@app.get("/stream/{id}/{fileName}", include_in_schema=False)
async def video(response: Response, id: str, fileName: str):
    response.headers["Content-Type"] = "application/x-mpegURL"
    return FileResponse("stream/" + id + "/" + fileName, filename=fileName)


@app.get("/streams")
async def get_streams():
    """
    This endpoint returns a list of active streams.

    Returns:

        JSONResponse: A response containing the list of active streams.
    """
    return JSONResponse(content=manager.config)


templates = Jinja2Templates(directory="templates")


@app.get("/live/{id}")
async def get_live_stream(request: Request, id: str):
    """
    This endpoint returns the live stream URL of a given stream.

    Args:

        id (str): The ID of the stream.

    """
    # return html page with video player and pass parameters to the html page
    return templates.TemplateResponse(
        request=request,
        name="live.html",
        context={
            "server": f"{os.getenv('API_HOST', '127.0.0.1')}:{os.getenv('API_PORT', 3597)}",
            "id": id,
        },
    )


@app.post("/stream/add/")
async def add_stream(stream: dict):
    """
    This endpoint adds a new stream to the list of active streams.

    Args:

        stream (dict): A dictionary containing the stream ID and RTSP URL.


    Returns:

        JSONResponse: A response containing the status of the operation.

    Example:

            {
                "id": "stream1",
                "rtsp_url": "rtsp://0.0.0.0:554/stream1"
            }
    """
    id, rtsp_url = stream["id"], stream["rtsp_url"]
    res = manager.add_stream(id, rtsp_url)
    if res is not None:
        return JSONResponse(content={"status": "success"})
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to add stream",
        )


@app.post("/stream/remove/{id}")
async def remove_stream(id: str):
    """
    This endpoint removes a stream from the list of active streams.

    Args:

        id (str): The ID of the stream to remove.

    Returns:

        JSONResponse: A response containing the status of the operation.
    """
    manager.remove_stream(id)
    return JSONResponse(content={"status": "success"})


# Shutdown the HLS manager when the server is stopped


def args_parser():
    parser = argparse.ArgumentParser(description="Stream HLS API")
    parser.add_argument("--watch", action="store_true", help="Enable live mode")
    return parser.parse_args()


if __name__ == "__main__":
    opt = args_parser()
    # manager = HLSManager(os.path.join("metadata", "stream.json"))
    manager = None

    uvicorn.run(
        "api:app",
        host=os.getenv("API_HOST", "127.0.0.1"),
        port=int(os.getenv("API_PORT", 3597)),
        reload=opt.watch if opt.watch else False,
    )
