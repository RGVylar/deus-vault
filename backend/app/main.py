from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import auth, contents, lookup
from app.telegram import notify_error

app = FastAPI(title="Deus Vault", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    await notify_error(exc, context=f"{request.method} {request.url.path}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


api_prefix = "/api"
app.include_router(auth.router, prefix=api_prefix)
app.include_router(contents.router, prefix=api_prefix)
app.include_router(lookup.router, prefix=api_prefix)
