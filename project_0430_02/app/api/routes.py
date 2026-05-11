"""
API Routes - 文档生成接口
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from app.services.generator import DocumentGenerator
import io
import os
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


class GenerateResponse(BaseModel):
    """文档生成响应"""
    success: bool
    message: str = ""
    file_bytes: bytes = None


@router.post("/generate")
async def generate_document(request: GenerateRequest):
    """
    生成质量体系文档

    根据文档类型和产品信息，调用AI生成文档内容并返回Word文件
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

    try:
        generator = DocumentGenerator()
        file_bytes = await generator.generate(
            doc_type=request.doc_type,
            product_name=request.product_name,
            product_type=request.product_type,
            product_params=request.product_params
        )

        # 生成文件名（URL编码避免中文编码问题）
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
        label = doc_type_labels.get(request.doc_type, request.doc_type)
        filename = f"{request.product_name}_{label}.docx"
        encoded_filename = quote(filename)

        return StreamingResponse(
            io.BytesIO(file_bytes),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
