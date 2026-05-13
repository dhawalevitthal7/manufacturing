from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from server.database import engine, Base, get_db
from server.auth import decode_access_token
from server.schema_migrations import apply_sqlite_schema_migrations
from server.models import User, Organization
from server.routes_auth import router as auth_router
from server.routes_org import router as org_router
from server.routes_org_tree import router as org_tree_router
from server.routes_employees import router as emp_router
from server.routes_okrs import router as okr_router
from server.routes_okrs_hierarchy import router as okr_hierarchy_router
from server.routes_okrs_ai import router as okrs_ai_router
from server.routes_teams import router as teams_router
from server.routes_progress import router as progress_router
from server.routes_reviews import router as review_router
from server.routes_dashboard import router as dashboard_router
from server.routes_hierarchy import router as hierarchy_router
from server.routes_permissions import router as permissions_router
from server.routes_permission_matrix import router as perm_matrix_router
import os

Base.metadata.create_all(bind=engine)
apply_sqlite_schema_migrations(engine)

app = FastAPI(title="Manufacturing Performance OS", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_current_user(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    token = auth.split(" ")[1]
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(401, "Invalid token")
    return payload


# --- Middleware to inject org_id and user_id into query params for routers ---
@app.middleware("http")
async def inject_context(request: Request, call_next):
    if request.url.path.startswith("/api/") and request.url.path not in ("/api/auth/register", "/api/auth/login"):
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth.split(" ")[1]
            payload = decode_access_token(token)
            if payload:
                # Inject as query params
                from urllib.parse import urlencode, parse_qs, urlparse, urlunparse
                parsed = urlparse(str(request.url))
                params = parse_qs(parsed.query)
                params["org_id"] = [payload.get("org_id", "")]
                params["user_id"] = [payload.get("sub", "")]
                params["role"] = [payload.get("role", "")]
                new_query = urlencode({k: v[0] for k, v in params.items()})
                new_url = urlunparse(parsed._replace(query=new_query))
                request.scope["query_string"] = new_query.encode()
    response = await call_next(request)
    return response


# Auth routes (no auth needed for register/login)
app.include_router(auth_router)

# Protected routes
app.include_router(org_router)
app.include_router(org_tree_router)
app.include_router(emp_router)
app.include_router(okr_router)
app.include_router(okr_hierarchy_router)
app.include_router(okrs_ai_router)
app.include_router(teams_router)
app.include_router(progress_router)
app.include_router(review_router)
app.include_router(dashboard_router)
app.include_router(hierarchy_router)
app.include_router(permissions_router)
app.include_router(perm_matrix_router)


# --- Serve frontend ---
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Manufacturing Performance OS API", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
