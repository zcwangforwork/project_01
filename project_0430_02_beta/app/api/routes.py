"""
API Routes - 文档生成接口（异步任务模式）+ 附件上传接口
"""

import uuid
import threading
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field
from app.services.generator import DocumentGenerator
from app.services.doc_types import DOC_TYPE_LABELS, DOC_CATEGORIES, SUPPORTED_UPLOAD_FORMATS, MAX_UPLOAD_SIZE_BYTES
from app.services.attachment_service import (
    validate_upload, submit_extract_task, get_extract_status
)
from app.services.conversation import conversation_manager
import io
import os
import time
from typing import Optional, List
from urllib.parse import quote

router = APIRouter()


class GenerateRequest(BaseModel):
    """文档生成请求"""
    doc_type: str = Field(..., description="文档类型")
    product_name: str = Field(..., description="产品名称")
    product_type: str = Field(default="", description="产品类型，如：有源医疗器械")
    product_params: str = Field("", description="产品参数详情")
    file_ids: Optional[List[str]] = Field(None, description="已入库附件的file_id列表")
    attachment_content: Optional[str] = Field(None, description="临时附件的提取文本内容")


# 内存中的任务存储
tasks = {}  # task_id -> {status, progress, message, file_bytes, filename, created_at}


def _run_generation(task_id: str, doc_type: str, product_name: str, product_type: str, product_params: str, file_ids: Optional[List[str]] = None, attachment_content: Optional[str] = None):
    """在后台线程中执行文档生成"""
    try:
        tasks[task_id]["status"] = "generating"
        tasks[task_id]["progress"] = 10
        tasks[task_id]["message"] = "正在生成文档内容..."

        generator = DocumentGenerator()

        # 同步生成文档（在线程中运行，不阻塞事件循环）
        import asyncio
        loop = asyncio.new_event_loop()
        try:
            file_bytes = loop.run_until_complete(
                generator.generate(
                    doc_type=doc_type,
                    product_name=product_name,
                    product_type=product_type,
                    product_params=product_params,
                    file_ids=file_ids,
                    attachment_content=attachment_content
                )
            )
        finally:
            loop.close()

        # 生成文件名
        label = DOC_TYPE_LABELS.get(doc_type, doc_type)
        filename = f"{product_name}_{label}.docx"

        # 创建会话，保存生成的内容供后续修订
        session_id = conversation_manager.create_session(
            doc_type=doc_type,
            product_name=product_name,
            product_type=product_type,
            product_params=product_params,
            doc_content=generator.last_generated_content
        )

        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["message"] = "文档生成完成！"
        tasks[task_id]["file_bytes"] = file_bytes
        tasks[task_id]["filename"] = filename
        tasks[task_id]["search_log"] = generator.search_log
        tasks[task_id]["session_id"] = session_id
        tasks[task_id]["doc_content"] = generator.last_generated_content

    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["progress"] = 0
        tasks[task_id]["message"] = f"生成失败: {str(e)}"


@router.post("/generate")
async def generate_document(request: GenerateRequest):
    """
    提交文档生成任务（异步）

    立即返回任务ID，文档在后台生成，前端通过 /api/status/{task_id} 轮询进度
    """
    # 验证必填字段
    if not request.product_name.strip():
        raise HTTPException(status_code=400, detail="产品名称不能为空")

    # 创建任务
    task_id = str(uuid.uuid4())[:8]
    tasks[task_id] = {
        "status": "pending",
        "progress": 0,
        "message": "任务已创建，等待生成...",
        "file_bytes": None,
        "filename": "",
        "created_at": time.time()
    }

    # 启动后台线程
    thread = threading.Thread(
        target=_run_generation,
        args=(task_id, request.doc_type, request.product_name, request.product_type, request.product_params, request.file_ids, request.attachment_content),
        daemon=True
    )
    thread.start()

    return {"task_id": task_id, "status": "pending", "message": "任务已提交"}


@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """查询任务状态"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]
    result = {
        "task_id": task_id,
        "status": task["status"],
        "progress": task["progress"],
        "message": task["message"],
        "filename": task.get("filename", ""),
        "search_log": task.get("search_log", [])
    }
    # 生成完成时返回 session_id 供前端进入修订模式
    if task["status"] == "completed" and task.get("session_id"):
        result["session_id"] = task["session_id"]
    return result


@router.get("/download/{task_id}")
async def download_document(task_id: str):
    """下载生成的文档"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = tasks[task_id]

    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="文档尚未生成完成")

    if not task["file_bytes"]:
        raise HTTPException(status_code=500, detail="文档数据为空")

    encoded_filename = quote(task["filename"])

    return StreamingResponse(
        io.BytesIO(task["file_bytes"]),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        }
    )


# ==================== 数字员工交互式修订接口 ====================

class ReviseRequest(BaseModel):
    """文档修订请求"""
    session_id: str = Field(..., description="会话ID（从首次生成返回）")
    feedback: str = Field(..., description="用户修改意见")


@router.post("/revise")
async def revise_document(request: ReviseRequest):
    """
    基于用户反馈修订文档（数字员工交互模式）

    提交修改意见，返回修订后的文档
    """
    session = conversation_manager.get_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")

    if not request.feedback.strip():
        raise HTTPException(status_code=400, detail="反馈意见不能为空")

    # 记录反馈并创建版本快照
    version_label = conversation_manager.add_feedback(request.session_id, request.feedback)

    # 在后台执行修订
    task_id = str(uuid.uuid4())[:8]
    tasks[task_id] = {
        "status": "revising",
        "progress": 0,
        "message": "正在根据反馈修订文档...",
        "file_bytes": None,
        "filename": "",
        "session_id": request.session_id,
        "created_at": time.time()
    }

    thread = threading.Thread(
        target=_run_revision,
        args=(task_id, request.session_id, request.feedback),
        daemon=True
    )
    thread.start()

    return {"task_id": task_id, "status": "revising", "message": "修订任务已提交", "version": version_label}


def _run_revision(task_id: str, session_id: str, feedback: str):
    """在后台线程中执行文档修订"""
    try:
        tasks[task_id]["status"] = "revising"
        tasks[task_id]["progress"] = 20
        tasks[task_id]["message"] = "正在根据反馈修订文档..."

        session = conversation_manager.get_session(session_id)
        if not session:
            tasks[task_id]["status"] = "failed"
            tasks[task_id]["message"] = "会话不存在"
            return

        generator = DocumentGenerator()

        import asyncio
        loop = asyncio.new_event_loop()
        try:
            file_bytes = loop.run_until_complete(
                generator.revise(
                    current_content=session.current_content,
                    feedback=feedback,
                    doc_type=session.doc_type,
                    product_name=session.product_name,
                    product_type=session.product_type,
                    product_params=session.product_params
                )
            )
        finally:
            loop.close()

        # 更新会话中的文档内容
        conversation_manager.update_content(session_id, generator.last_generated_content)

        # 将差异数据写入版本快照，供前端展示修订对比
        if generator.last_diff_data:
            conversation_manager.set_version_diff(session_id, generator.last_diff_data)

        label = DOC_TYPE_LABELS.get(session.doc_type, session.doc_type)
        filename = f"{session.product_name}_{label}_修订版.docx"

        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["message"] = "文档修订完成！"
        tasks[task_id]["file_bytes"] = file_bytes
        tasks[task_id]["filename"] = filename

    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["progress"] = 0
        tasks[task_id]["message"] = f"修订失败: {str(e)}"


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """获取数字员工会话状态"""
    session = conversation_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")
    return session.to_dict()


@router.get("/session/{session_id}/download")
async def download_session_document(session_id: str):
    """
    下载会话当前的文档版本

    根据会话中的最新内容重新生成 Word 文件并返回
    """
    session = conversation_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")

    from app.services.template import TemplateService
    template_service = TemplateService()

    doc = template_service.load_template(session.doc_type)
    doc = template_service.fill_template(
        doc=doc,
        content=session.current_content,
        product_name=session.product_name,
        doc_type=session.doc_type
    )
    file_bytes = template_service.document_to_bytes(doc)

    label = DOC_TYPE_LABELS.get(session.doc_type, session.doc_type)
    v = session.version_count
    filename = f"{session.product_name}_{label}_v{v}.docx"
    encoded_filename = quote(filename)

    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        }
    )


@router.get("/doc-types")
async def get_doc_types():
    """获取支持的文档类型列表 — 贴敷式胰岛素泵全生命周期94+种文档"""
    types = []
    for cat_key, cat_info in DOC_CATEGORIES.items():
        for doc_type in cat_info["types"]:
            label = DOC_TYPE_LABELS.get(doc_type, doc_type)
            types.append({
                "value": doc_type,
                "label": label,
                "category": cat_info["name"],
                "category_key": cat_key,
                "description": cat_info["description"]
            })
    return {
        "types": types,
        "categories": [
            {
                "key": cat_key,
                "name": cat_info["name"],
                "description": cat_info["description"],
                "icon": cat_info["icon"],
                "count": len(cat_info["types"])
            }
            for cat_key, cat_info in DOC_CATEGORIES.items()
        ]
    }


# ==================== 附件上传接口 ====================

@router.post("/upload")
async def upload_attachment(
    file: UploadFile = File(..., description="附件文件 (.docx/.pdf/.txt)"),
    persist: bool = Form(False, description="是否存入知识库供后续复用")
):
    """
    上传附件文档，提交后台提取任务

    返回 file_id，前端通过 GET /api/extract-status/{file_id} 轮询提取进度
    """
    # 验证格式和大小
    file_content = await file.read()
    is_valid, error_msg = validate_upload(file.filename, len(file_content))
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    # 提交后台提取任务
    task_id = submit_extract_task(
        file_content=file_content,
        filename=file.filename,
        persist=persist,
        doc_type="unknown"
    )

    return {
        "file_id": task_id,
        "filename": file.filename,
        "status": "pending",
        "message": "文件已接收，正在后台提取文本..."
    }


@router.get("/extract-status/{file_id}")
async def get_extract_task_status(file_id: str):
    """查询附件提取任务状态"""
    status = get_extract_status(file_id)
    if status is None:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return status


@router.get("/debug/env")
async def debug_env():
    """调试端点 - 检查环境变量"""
    api_key = os.getenv("MINIMAX_API_KEY", "")
    return {
        "api_key_set": bool(api_key),
        "api_key_prefix": api_key[:10] + "..." if api_key else None,
        "env_file_loaded": os.path.exists(".env"),
        "cwd": os.getcwd()
    }


@router.get("/debug/test-api")
async def test_api():
    """测试 MiniMax API 调用"""
    from app.services.minimax import MiniMaxService
    service = MiniMaxService()
    try:
        result = service.generate_content(
            doc_type="risk_management_report",
            product_name="测试产品",
            product_type="有源医疗器械",
            product_params="测试参数"
        )
        return {"success": True, "result": result[:500] if result else "empty"}
    except Exception as e:
        return {"success": False, "error": str(e)}
