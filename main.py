from contextlib import asynccontextmanager
import json
import os
import random
import string
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit

import asyncpg
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    PlainTextResponse,
    RedirectResponse
)
from pydantic import BaseModel
import uvicorn

db_conn_pools: list[asyncpg.Pool] = []

with open("index.html") as f:
    home_page_content: str = f.read()


class URL(BaseModel):
    url: str


@asynccontextmanager
async def lifespan(app: FastAPI) -> None:
    db_url = os.environ["DATABASE_URL"]
    pool = await asyncpg.create_pool(db_url)
    async with pool.acquire() as conn:
        await conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS urls (
                id SERIAL PRIMARY KEY,
                scheme TEXT NOT NULL DEFAULT 'http',
                netloc TEXT NOT NULL,
                path TEXT DEFAULT NULL,
                query JSONB DEFAULT NULL,
                fragment TEXT DEFAULT NULL,
                short_url_id TEXT NOT NULL UNIQUE
            )
            '''
        )
    db_conn_pools.append(pool)
    yield
    for p in db_conn_pools:
        await p.close()


async def not_found(request: Request, exc: HTTPException) -> PlainTextResponse:
    return PlainTextResponse("404 Not Found", status_code=exc.status_code)


app = FastAPI(
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    exception_handlers={404: not_found}
)


@app.get("/", response_class=HTMLResponse)
async def home_page() -> str:
    return home_page_content

@app.get("/healthcheck")
async def health_check() -> dict[str, str]:
    return {"status": "ready"}

@app.post("/create", response_class=PlainTextResponse)
async def create_short_url(url: URL, request: Request) -> str | None:
    url = url.dict()["url"]
    url_components = list(urlsplit(url))
    url_components[3] = parse_qs(url_components[3])
    url_components[3] = json.dumps(url_components[3])
    sql_stmt = '''
        SELECT
            short_url_id
        FROM urls
        WHERE
            scheme = $1 AND
            netloc = $2 AND
            path = $3 AND
            query = $4 AND
            fragment = $5
    '''
    async with db_conn_pools[0].acquire() as conn:
        row = await conn.fetchrow(sql_stmt, *url_components)
    if row is not None:
        short_url_id = list(row)[0]
        return urljoin(str(request.base_url), "l/" + short_url_id)
    short_url_id = ""
    while True:
        short_url_id = ''.join(
            random.choices(string.ascii_letters + string.digits + '-_', k=7)
        )
        sql_stmt = '''
            SELECT
                short_url_id
            FROM urls
            WHERE short_url_id = $1
        '''
        if db_conn_pools:
            async with db_conn_pools[0].acquire() as conn:
                row = await conn.fetchrow(sql_stmt, short_url_id)
            if row is None:
                sql_stmt = '''
                    INSERT INTO
                    urls (scheme, netloc, path, query, fragment, short_url_id)
                    VALUES ($1, $2, $3, $4, $5, $6);
                '''
                async with db_conn_pools[0].acquire() as conn:
                    await conn.execute(
                        sql_stmt,
                        *url_components,
                        short_url_id
                    )
                return urljoin(str(request.base_url), "l/" + short_url_id)

@app.get("/l/{short_url_id}", status_code=301, response_class=RedirectResponse)
async def redirect(short_url_id: str) -> str:
    sql_stmt = '''
        SELECT
            scheme,
            netloc,
            path,
            query,
            fragment
        FROM urls
        WHERE short_url_id = $1
    '''
    if db_conn_pools:
        async with db_conn_pools[0].acquire() as conn:
            row = await conn.fetchrow(sql_stmt, short_url_id)
        if row is None:
            raise HTTPException(status_code=404)
        else:
            url_components = list(row)
            url_components[3] = json.loads(url_components[3])
            url_components[3] = urlencode(url_components[3], doseq=True)
            return urlunsplit(url_components)

@app.get("/favicon.ico", response_class=FileResponse)
async def favicon():
    return FileResponse("favicons/favicon.ico")

@app.get("/android-chrome-192x192.png", response_class=FileResponse)
async def favicon2():
    return FileResponse("favicons/android-chrome-192x192.png")

@app.get("/android-chrome-512x512.png", response_class=FileResponse)
async def favicon3():
    return FileResponse("favicons/android-chrome-512x512.png")

@app.get("/apple-touch-icon.png", response_class=FileResponse)
async def favicon4():
    return FileResponse("favicons/apple-touch-icon.png")

@app.get("/favicon-16x16.png", response_class=FileResponse)
async def favicon5():
    return FileResponse("favicons/favicon-16x16.png")

@app.get("/favicon-32x32.png", response_class=FileResponse)
async def favicon6():
    return FileResponse("favicons/favicon-32x32.png")

@app.get("/site.webmanifest", response_class=FileResponse)
async def favicon7():
    return FileResponse("favicons/site.webmanifest")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=os.environ.get("PORT", 8000)
    )
