"""
Document Generator - 文档生成协调服务
"""

from app.services.minimax import MiniMaxService
from app.services.template import TemplateService
from typing import Optional


class DocumentGenerator:
    """文档生成器 - 协调整个生成流程"""

    def __init__(self):
        self.minimax_service = MiniMaxService()
        self.template_service = TemplateService()

    async def generate(
        self,
        doc_type: str,
        product_name: str,
        product_type: str,
        product_params: str = ""
    ) -> bytes:
        """
        生成文档

        完整流程：
        1. 验证输入参数
        2. 调用AI生成内容
        3. 加载模板
        4. 填充内容
        5. 返回Word文件字节

        Args:
            doc_type: 文档类型
            product_name: 产品名称
            product_type: 产品类型
            product_params: 产品参数

        Returns:
            Word文件字节数据
        """
        # 1. 验证参数
        self._validate_input(doc_type, product_name, product_type)

        # 2. 加载模板
        doc = self.template_service.load_template(doc_type)

        # 3. 调用AI生成内容
        content = self.minimax_service.generate_content_with_fallback(
            doc_type=doc_type,
            product_name=product_name,
            product_type=product_type,
            product_params=product_params
        )

        # 4. 填充模板
        doc = self.template_service.fill_template(
            doc=doc,
            content=content,
            product_name=product_name,
            doc_type=doc_type
        )

        # 5. 转换为字节
        return self.template_service.document_to_bytes(doc)

    def _validate_input(
        self,
        doc_type: str,
        product_name: str,
        product_type: str
    ):
        """验证输入参数"""
        valid_doc_types = [
            "risk_management_report", "risk_management_plan", "fmea_analysis",
            "risk_acceptance_criteria", "periodic_risk_evaluation",
            "design_development_plan", "design_input", "design_output",
            "design_review", "design_verification", "design_validation",
            "design_change", "design_history_file",
            "product_spec", "instruction", "sop"
        ]

        if doc_type not in valid_doc_types:
            raise ValueError(f"无效的文档类型: {doc_type}，可选值: {', '.join(valid_doc_types)}")

        if not product_name or not product_name.strip():
            raise ValueError("产品名称不能为空")

        if not product_type or not product_type.strip():
            raise ValueError("产品类型不能为空")
