"""
API Routes - 文档生成接口（异步任务模式）
"""

import uuid
import threading
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field
from app.services.generator import DocumentGenerator
import io
import os
import time
from urllib.parse import quote

router = APIRouter()

# 文档类型枚举
DOC_TYPES = [
    # 风险管理类
    "risk_management_report",      # 风险管理报告
    "risk_management_plan",       # 风险管理计划
    "fmea_analysis",              # FMEA分析
    "risk_acceptance_criteria",    # 风险可接受准则
    "periodic_risk_evaluation",     # 定期风险评价报告
    # 设计开发类
    "design_development_plan",    # 设计和开发计划
    "design_input",               # 设计输入
    "design_output",              # 设计输出
    "design_review",              # 设计评审
    "design_verification",        # 设计验证
    "design_validation",          # 设计确认
    "design_change",              # 设计变更
    "design_history_file",        # 设计历史文件
    # 注册申报类
    "product_spec",               # 产品技术要求
    # 通用类
    "instruction",                # 使用说明书
    "sop"                         # 作业指导书
]


class GenerateRequest(BaseModel):
    """文档生成请求"""
    doc_type: str = Field(..., description="文档类型")
    product_name: str = Field(..., description="产品名称")
    product_type: str = Field(..., description="产品类型，如：有源医疗器械")
    product_params: str = Field("", description="产品参数详情")


# 内存中的任务存储
tasks = {}  # task_id -> {status, progress, message, file_bytes, filename, created_at}


def _run_generation(task_id: str, doc_type: str, product_name: str, product_type: str, product_params: str):
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
                    product_params=product_params
                )
            )
        finally:
            loop.close()

        # 生成文件名
        doc_type_labels = {
            "risk_management_report": "风险管理报告",
            "risk_management_plan": "风险管理计划",
            "fmea_analysis": "FMEA分析",
            "risk_acceptance_criteria": "风险可接受准则",
            "periodic_risk_evaluation": "定期风险评价",
            "design_development_plan": "设计开发计划",
            "design_input": "设计输入",
            "design_output": "设计输出",
            "design_review": "设计评审",
            "design_verification": "设计验证",
            "design_validation": "设计确认",
            "design_change": "设计变更",
            "design_history_file": "设计历史文件",
            "product_spec": "产品技术要求",
            "instruction": "使用说明书",
            "sop": "作业指导书"
        }
        label = doc_type_labels.get(doc_type, doc_type)
        filename = f"{product_name}_{label}.docx"

        tasks[task_id]["status"] = "completed"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["message"] = "文档生成完成！"
        tasks[task_id]["file_bytes"] = file_bytes
        tasks[task_id]["filename"] = filename

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
    # 验证 doc_type
    if request.doc_type not in DOC_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"无效的文档类型。可选值: {', '.join(DOC_TYPES)}"
        )

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
        args=(task_id, request.doc_type, request.product_name, request.product_type, request.product_params),
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
    return {
        "task_id": task_id,
        "status": task["status"],
        "progress": task["progress"],
        "message": task["message"],
        "filename": task.get("filename", "")
    }


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


@router.get("/doc-types")
async def get_doc_types():
    """获取支持的文档类型列表"""
    return {
        "types": [
            # 风险管理类
            {"value": "risk_management_report", "label": "风险管理报告", "category": "风险管理", "description": "符合ISO 14971/GB 42062的综合风险管理报告"},
            {"value": "risk_management_plan", "label": "风险管理计划", "category": "风险管理", "description": "定义风险管理活动计划和职责分配"},
            {"value": "fmea_analysis", "label": "FMEA分析报告", "category": "风险管理", "description": "失效模式与效应分析"},
            {"value": "risk_acceptance_criteria", "label": "风险可接受准则", "category": "风险管理", "description": "风险判定标准和RPN准则"},
            {"value": "periodic_risk_evaluation", "label": "定期风险评价报告", "category": "风险管理", "description": "上市后定期风险评价"},
            # 设计开发类
            {"value": "design_development_plan", "label": "设计和开发计划", "category": "设计开发", "description": "定义设计开发阶段、活动、职责和时间安排"},
            {"value": "design_input", "label": "设计输入", "category": "设计开发", "description": "产品设计输入要求，包括性能、法规、标准要求"},
            {"value": "design_output", "label": "设计输出", "category": "设计开发", "description": "设计输出文件，包括图纸、规范、检验规程等"},
            {"value": "design_review", "label": "设计评审", "category": "设计开发", "description": "设计评审记录，包括评审内容、参与人员、评审结论"},
            {"value": "design_verification", "label": "设计验证", "category": "设计开发", "description": "设计验证报告，证明设计输出满足设计输入要求"},
            {"value": "design_validation", "label": "设计确认", "category": "设计开发", "description": "设计确认报告，证明产品满足使用要求"},
            {"value": "design_change", "label": "设计变更", "category": "设计开发", "description": "设计变更控制记录，包括变更评估、审批和验证"},
            {"value": "design_history_file", "label": "设计历史文件", "category": "设计开发", "description": "DHF设计历史文件，汇总所有设计开发活动记录"},
            # 注册申报类
            {"value": "product_spec", "label": "产品技术要求", "category": "注册申报", "description": "医疗器械注册产品技术要求"},
            # 通用类
            {"value": "instruction", "label": "使用说明书", "category": "通用", "description": "医疗器械使用说明书IFU"},
            {"value": "sop", "label": "作业指导书", "category": "通用", "description": "标准操作规程SOP"}
        ]
    }


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
