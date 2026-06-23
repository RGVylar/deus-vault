import httpx

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import auth, contents, lookup
from app.routers.steam import auth_router as steam_auth_router, contents_router as steam_contents_router
from app.telegram import send_error_alert

# Transient network errors — log but don't spam Telegram
_SILENT_EXCEPTIONS = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.RemoteProtocolError,
)

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
    if isinstance(exc, _SILENT_EXCEPTIONS):
        # Transient network error — return 503, no Telegram noise
        return JSONResponse(status_code=503, content={"detail": "Servicio externo no disponible, inténtalo de nuevo"})
    await send_error_alert(request.method, request.url.path, exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}



api_prefix = "/api"
app.include_router(auth.router, prefix=api_prefix)
app.include_router(contents.router, prefix=api_prefix)
app.include_router(lookup.router, prefix=api_prefix)
app.include_router(steam_auth_router, prefix=api_prefix)
app.include_router(steam_contents_router, prefix=api_prefix)
