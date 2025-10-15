from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger

from api.health import router as root_router


def init_app():
    application = FastAPI()
    application.include_router(root_router)
    return application


app = init_app()


@app.middleware("http")
async def log_exceptions(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        context_logger = logger.bind(
            url=request.url, method=request.method, headers=request.headers
        )
        context_logger.exception(f"Exception occurred: {str(e)}\n")
        return JSONResponse(
            status_code=500, content={"detail": "An internal server error occurred."}
        )
