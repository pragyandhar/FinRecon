from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.chat import router as chat_router
from app.api.jobs import router as jobs_router
from app.core.config import settings
from app.core.errors import FinReconError
from app.storage.db import init_db

_STATUS_BY_CODE = {
    "JOB_NOT_FOUND": 404,
    "UNSUPPORTED_FILE_TYPE": 422,
    "FILE_TOO_LARGE": 413,
    "EXTRACTION_FAILED": 422,
    "SCHEMA_UNCERTAIN": 422,
    "INVALID_RECONCILIATION_PLAN": 422,
    "UNSUPPORTED_OPERATION": 422,
    "PLAN_EXECUTION_FAILED": 500,
    "MODEL_EXECUTION_FAILED": 502,
    "UNRESOLVED_EXCEPTION": 200,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="FinRecon", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(FinReconError)
async def finrecon_error_handler(request: Request, exc: FinReconError) -> JSONResponse:
    status_code = _STATUS_BY_CODE.get(exc.code, 400)
    return JSONResponse(status_code=status_code, content=exc.to_dict())


app.include_router(jobs_router)
app.include_router(chat_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
