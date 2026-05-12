"""
QMS Document Generator - FastAPI Application
医疗器械质量体系文档生成工具
"""

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api.routes import router

app = FastAPI(
    title="QMS Document Generator",
    description="医疗器械质量体系文档生成工具 - 基于AI自动生成符合法规的质量体系文档",
    version="1.0.0"
)

# Include API routes
app.include_router(router, prefix="/api")


@app.get("/")
async def root():
    """返回前端页面"""
    return FileResponse("app/static/index.html")


@app.get("/api/health")
async def health_check():
    """健康检查接口"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
