import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from app.config import settings
from app.database import engine, Base
from app.api import documents, search, health

# Create all DB tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(documents.router, prefix=settings.API_V1_STR)
app.include_router(search.router, prefix=settings.API_V1_STR)
app.include_router(health.router, prefix=settings.API_V1_STR)

# Frontend static files
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend"))
if os.path.exists(frontend_dir):
    # Mount JS and CSS subdirs
    css_dir = os.path.join(frontend_dir, "css")
    js_dir  = os.path.join(frontend_dir, "js")
    if os.path.exists(css_dir):
        app.mount("/static/css", StaticFiles(directory=css_dir), name="static-css")
    if os.path.exists(js_dir):
        app.mount("/static/js", StaticFiles(directory=js_dir), name="static-js")

    @app.get("/", include_in_schema=False)
    def serve_index():
        index_path = os.path.join(frontend_dir, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path, media_type="text/html")
        return JSONResponse({"message": "TransformoDocs API Server Ready"})

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon():
        svg = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="8" fill="#6366f1"/><text x="16" y="22" font-size="18" text-anchor="middle" fill="white" font-family="sans-serif">T</text></svg>'
        from fastapi.responses import Response
        return Response(content=svg, media_type="image/svg+xml")

else:
    @app.get("/", include_in_schema=False)
    def root():
        return {"message": "TransformoDocs API Server Ready"}
