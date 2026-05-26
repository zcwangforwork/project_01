"""
文档类型公共常量 — DOC_TYPES 列表和 doc_type_labels 映射
所有模块从此处引用，避免重复定义
"""

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

DOC_TYPE_LABELS = {
    "risk_management_report": "风险管理报告",
    "risk_management_plan": "风险管理计划",
    "fmea_analysis": "FMEA分析报告",
    "risk_acceptance_criteria": "风险可接受准则",
    "periodic_risk_evaluation": "定期风险评价报告",
    "design_development_plan": "设计和开发计划",
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

SUPPORTED_UPLOAD_FORMATS = [".docx", ".pdf", ".txt"]
MAX_UPLOAD_SIZE_MB = 10
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024
