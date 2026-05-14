"""
MiniMax API Service - AI内容生成
"""

import os
import json
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional, List, Dict

# RAG 组件 - 延迟导入避免启动时耗时
_rag_available = False
_vector_store = None
_rag_prompt_builder = None

# Web 搜索组件 - 延迟初始化
_web_search_available = None
_web_search_service = None


def _try_init_web_search():
    """延迟初始化 Web 搜索组件"""
    global _web_search_available, _web_search_service
    if _web_search_available is not None:
        return _web_search_available
    try:
        from app.services.web_search import SyncWebSearchService
        _web_search_service = SyncWebSearchService()
        _web_search_available = _web_search_service.playwright_available
        return _web_search_available
    except ImportError:
        _web_search_available = False
        return False

def _try_init_rag():
    """延迟初始化 RAG 组件"""
    global _rag_available, _vector_store, _rag_prompt_builder
    if _rag_available:
        return True
    try:
        from app.services.rag.vector_store import VectorStore
        from app.services.rag.rag_prompt import build_rag_prompt_from_base
        _vector_store = VectorStore
        _rag_prompt_builder = build_rag_prompt_from_base
        _rag_available = True
        return True
    except ImportError:
        return False

# API配置 - 从环境变量读取（延迟读取，避免导入时.env未加载）
def _get_api_key():
    return os.getenv("MINIMAX_API_KEY", "")

MINIMAX_API_URL = "https://ark.cn-beijing.volces.com/api/coding/v3/chat/completions"

# 文档章节结构定义 - 分章节生成的基础
DOC_CHAPTERS = {
    "risk_management_report": [
        {"id": "ch1", "name": "概述", "query": "产品简介 预期用途 设计原理"},
        {"id": "ch2", "name": "风险分析", "query": "风险分析 危害判定 安全性特征"},
        {"id": "ch3", "name": "风险评估", "query": "风险评估 RPN 严重度 频度数"},
        {"id": "ch4", "name": "风险控制", "query": "风险控制 风险控制措施"},
        {"id": "ch5", "name": "剩余风险评价", "query": "剩余风险 综合评价"},
        {"id": "ch6", "name": "风险管理评审结论", "query": "风险管理评审 结论 文档批准"},
    ],
    "risk_management_plan": [
        {"id": "ch1", "name": "目的和范围", "query": "风险管理目的 范围 适用性"},
        {"id": "ch2", "name": "产品描述", "query": "产品描述 结构组成 技术参数"},
        {"id": "ch3", "name": "人员资格和职责", "query": "人员资格 职责分配"},
        {"id": "ch4", "name": "风险可接受性准则", "query": "风险可接受准则 严重度 频度数"},
        {"id": "ch5", "name": "风险管理活动计划", "query": "风险管理活动 计划 评审安排"},
        {"id": "ch6", "name": "生产和生产后信息收集", "query": "生产后信息 信息收集"},
    ],
    "fmea_analysis": [
        {"id": "ch1", "name": "FMEA概述", "query": "FMEA概述 目的 范围 方法"},
        {"id": "ch2", "name": "严重度频度数探测度评价准则", "query": "严重度 频度数 探测度 评价准则"},
        {"id": "ch3", "name": "FMEA分析表", "query": "FMEA分析表 失效模式 失效效应"},
        {"id": "ch4", "name": "高风险项目改进措施", "query": "高风险 改进措施 RPN"},
        {"id": "ch5", "name": "风险可接受性判定", "query": "风险可接受性 RPN判定"},
        {"id": "ch6", "name": "FMEA分析结论", "query": "FMEA结论 建议 文档批准"},
    ],
    "design_development_plan": [
        {"id": "ch1", "name": "目的和范围", "query": "设计开发计划 目的 范围 产品描述"},
        {"id": "ch2", "name": "设计开发阶段划分", "query": "设计开发阶段 阶段划分 里程碑"},
        {"id": "ch3", "name": "职责分配", "query": "设计开发职责 人员分配 资质要求"},
        {"id": "ch4", "name": "设计开发活动安排", "query": "设计评审 设计验证 设计确认 时间安排"},
        {"id": "ch5", "name": "技术资源配置", "query": "设备 软件 标准 法规 外部资源"},
        {"id": "ch6", "name": "设计变更管理", "query": "设计变更 控制流程 审批权限"},
    ],
    "design_input": [
        {"id": "ch1", "name": "概述", "query": "设计输入 目的 范围 产品描述"},
        {"id": "ch2", "name": "性能要求", "query": "性能要求 功能要求 技术参数"},
        {"id": "ch3", "name": "法规标准要求", "query": "法规标准 强制标准 推荐标准"},
        {"id": "ch4", "name": "风险管理要求", "query": "风险管理 风险控制措施 安全性要求"},
        {"id": "ch5", "name": "用户需求", "query": "用户需求 预期用途 使用场景"},
        {"id": "ch6", "name": "设计输入评审", "query": "设计输入评审 评审记录 批准"},
    ],
    "design_output": [
        {"id": "ch1", "name": "概述", "query": "设计输出 目的 范围 概述"},
        {"id": "ch2", "name": "产品图纸和规范", "query": "图纸 规范 技术文档 物料清单"},
        {"id": "ch3", "name": "生产工艺文件", "query": "生产工艺 作业指导书 检验规程"},
        {"id": "ch4", "name": "包装和标识规范", "query": "包装规范 标识 标签 使用说明书"},
        {"id": "ch5", "name": "设计输出评审", "query": "设计输出评审 评审记录 批准"},
    ],
    "design_review": [
        {"id": "ch1", "name": "评审概述", "query": "设计评审 目的 范围 评审阶段"},
        {"id": "ch2", "name": "评审内容", "query": "评审内容 设计输入 设计输出 风险评估"},
        {"id": "ch3", "name": "评审参与人员", "query": "评审人员 资格 职责 签字"},
        {"id": "ch4", "name": "评审发现和建议", "query": "评审发现 问题 改进建议"},
        {"id": "ch5", "name": "评审结论和跟踪", "query": "评审结论 整改措施 跟踪验证"},
    ],
    "design_verification": [
        {"id": "ch1", "name": "验证概述", "query": "设计验证 目的 范围 验证计划"},
        {"id": "ch2", "name": "验证方法", "query": "验证方法 检验 测试 对比 计算"},
        {"id": "ch3", "name": "验证项目和结果", "query": "验证项目 测试数据 结果判定"},
        {"id": "ch4", "name": "不符合项处理", "query": "不符合项 原因分析 纠正措施"},
        {"id": "ch5", "name": "验证结论", "query": "验证结论 批准 记录"},
    ],
    "design_validation": [
        {"id": "ch1", "name": "确认概述", "query": "设计确认 目的 范围 确认计划"},
        {"id": "ch2", "name": "临床评价", "query": "临床评价 临床试验 临床数据"},
        {"id": "ch3", "name": "模拟使用测试", "query": "模拟使用 用户测试 可用性评价"},
        {"id": "ch4", "name": "确认结果分析", "query": "确认结果 数据分析 有效性评价"},
        {"id": "ch5", "name": "确认结论", "query": "确认结论 批准 记录"},
    ],
    "design_change": [
        {"id": "ch1", "name": "变更概述", "query": "设计变更 变更描述 变更原因"},
        {"id": "ch2", "name": "变更影响评估", "query": "变更影响 风险评估 产品影响"},
        {"id": "ch3", "name": "变更验证计划", "query": "变更验证 验证方法 验证内容"},
        {"id": "ch4", "name": "变更审批", "query": "变更审批 审批人 审批意见"},
        {"id": "ch5", "name": "变更实施记录", "query": "变更实施 实施记录 追溯性"},
    ],
    "design_history_file": [
        {"id": "ch1", "name": "DHF目录", "query": "设计历史文件 目录 文件清单"},
        {"id": "ch2", "name": "设计开发计划记录", "query": "设计计划 记录 批准"},
        {"id": "ch3", "name": "设计输入输出记录", "query": "设计输入 设计输出 记录"},
        {"id": "ch4", "name": "设计评审验证确认记录", "query": "设计评审 验证 确认 记录"},
        {"id": "ch5", "name": "设计变更记录", "query": "设计变更 变更记录 追溯"},
        {"id": "ch6", "name": "DHF管理", "query": "DHF管理 归档 保存 查阅"},
    ],
    "product_spec": [
        {"id": "ch1", "name": "型号规格", "query": "型号 规格 结构组成"},
        {"id": "ch2", "name": "性能指标", "query": "性能指标 物理性能 化学性能"},
        {"id": "ch3", "name": "检验方法", "query": "检验方法 检验规则"},
        {"id": "ch4", "name": "标志包装运输贮存", "query": "标志 包装 运输 贮存"},
    ],
    "instruction": [
        {"id": "ch1", "name": "产品信息", "query": "产品名称 型号 生产企业"},
        {"id": "ch2", "name": "适用范围", "query": "适用范围 适应症 禁忌症"},
        {"id": "ch3", "name": "使用方法", "query": "使用方法 操作步骤 使用前准备"},
        {"id": "ch4", "name": "注意事项", "query": "注意事项 警示 警告"},
        {"id": "ch5", "name": "维护保养", "query": "维护 保养 故障排除"},
    ],
    "sop": [
        {"id": "ch1", "name": "目的和范围", "query": "SOP目的 范围 引用文件"},
        {"id": "ch2", "name": "职责", "query": "职责 部门 人员资质"},
        {"id": "ch3", "name": "操作步骤", "query": "操作步骤 工艺流程 质量控制点"},
        {"id": "ch4", "name": "安全注意事项", "query": "安全注意事项 防护措施"},
    ],
}

# 默认章节（未定义的文档类型使用）
DEFAULT_CHAPTERS = [
    {"id": "ch1", "name": "概述", "query": "概述 产品简介"},
    {"id": "ch2", "name": "主要内容", "query": "主要内容 详细描述"},
    {"id": "ch3", "name": "结论", "query": "结论 总结"},
]


class MiniMaxService:
    """MiniMax API 调用服务"""

    _use_rag_default = False  # 默认禁用 RAG（避免模型问题影响启动）

    def __init__(self, api_key: Optional[str] = None, use_rag: bool = True):
        """
        初始化 MiniMax 服务

        Args:
            api_key: MiniMax API Key，默认从环境变量读取
            use_rag: 是否启用 RAG（检索增强生成），需要先运行 ingest 建立向量库
        """
        self.api_key = api_key or _get_api_key()
        self.api_url = MINIMAX_API_URL
        self.use_rag = use_rag and _try_init_rag()
        self.use_web_search = _try_init_web_search()  # Web 搜索默认可用

    def generate_content(
        self,
        doc_type: str,
        product_name: str,
        product_type: str,
        product_params: str = "",
        chapter_mode: bool = True
    ) -> str:
        """
        调用MiniMax API生成文档内容

        Args:
            doc_type: 文档类型
            product_name: 产品名称
            product_type: 产品类型
            product_params: 产品参数
            chapter_mode: 是否使用分章节生成模式（默认True）
        """
        if not self.api_key:
            raise ValueError("MINIMAX_API_KEY 未设置，请联系管理员配置")

        # 优先使用分章节生成模式
        if chapter_mode:
            return self._generate_by_chapters(
                doc_type, product_name, product_type, product_params
            )

        # 降级到单次生成
        template = self._get_prompt_template(doc_type)
        prompt = template.format(
            product_name=str(product_name),
            product_type=str(product_type),
            product_params=str(product_params) if product_params else "无特殊参数"
        )
        return self._call_api(prompt)

    def _get_prompt_template(self, doc_type: str) -> str:
        """获取详细Prompt模板 - 增强版（全中文要求）"""
        templates = {
            "risk_management_report": """
你是一位资深的医疗器械风险管理专家，持有ISO 14971内审员资质和多年医疗器械行业经验。请根据以下产品信息和参考范文，生成{chapter}章节内容。

【产品信息】
- 产品名称：{product_name}
- 产品类型：{product_type}
- 产品参数：{product_params}

【重要要求】
请参考上方的【参考范文】和【相关法规标准】部分（如果提供），严格按照参考范文的详细程度和格式生成{chapter}的完整内容。

特别注意：
0. 【强制要求】所有内容必须使用中文，不要使用任何英文单词或短语，除了标准号（如GB 42062-2022、ISO 14971:2019等）中必须包含的部分
1. 内容必须极其细致和具体，每个段落都要有实质性内容，不能只写框架标题
2. 风险分析要覆盖所有可能的危害，包括但不限于：能量危害、生物学危害、环境危害、使用危害等
3. 每个风险点都要有具体的分析、评价和控制措施
4. 技术参数要具体、可测量、有明确的数值范围
5. 表格要填写完整，不能留"（描述）"或"待填写"等占位符
6. 标准号和条款引用要准确，如GB 42062-2022、ISO 14971:2019等
7. 严重度、频度数、可探测度的评价要有理有据
8. 风险控制措施要具体可行，有明确的实施方法和验证要求
9. 剩余风险评价要有明确的结论和依据
10. 使用专业、规范的医疗器械行业术语

生成内容的详细程度要像实际可用于注册申报的正式文档一样。
""",
            "risk_management_plan": """
你是一位资深的医疗器械风险管理专家，持有ISO 14971内审员资质。请根据以下产品信息和参考范文，生成{chapter}章节内容。

【产品信息】
- 产品名称：{product_name}
- 产品类型：{product_type}
- 产品参数：{product_params}

【重要要求】
请参考上方的【参考范文】和【相关法规标准】部分（如果提供），严格按照参考范文的详细程度生成{chapter}的完整内容。

特别注意：
0. 【强制要求】所有内容必须使用中文，不要使用任何英文单词或短语，除了标准号中必须包含的部分
1. 内容必须极其细致和具体，不能只写框架
2. 人员职责要明确到具体岗位，资质要求要详细
3. 风险可接受准则要有明确的判定方法和数值标准
4. 风险管理活动计划要有具体的时间安排、责任人、输出文件
5. 生产和生产后信息收集要有具体的方法、频次、记录要求
6. 引用标准要准确，包括标准号和版本号
7. 每个条款都要有实质性内容，不能用笼统的概括
""",
            "fmea_analysis": """
你是一位资深的医疗器械FMEA分析专家，精通ISO 14971风险管理和GB 42062标准。请根据以下产品信息和参考范文，生成{chapter}章节内容。

【产品信息】
- 产品名称：{product_name}
- 产品类型：{product_type}
- 产品参数：{product_params}

【重要要求】
请参考上方的【参考范文】和【相关法规标准】部分（如果提供），严格按照参考范文的详细程度生成{chapter}的完整内容。

特别注意：
0. 【强制要求】所有内容必须使用中文，不要使用任何英文单词或短语，除了标准号和缩写（如FMEA、RPN等）中必须包含的部分
1. FMEA表格要极其详细，每个失效模式都要有完整的分析
2. 失效原因要分析到根本原因，不能只停留在表面
3. 失效后果要从多个维度分析：对患者的影响、对操作者的影响、对设备的影响等
4. 严重度、频度数、探测度的评分要有明确依据
5. 建议的改进措施要具体可行，有责任人和完成时间
6. 风险优先级数(RPN)计算要准确
7. 高风险项目要有详细的改进计划和验证方法
8. 每个条目都要有实质性内容，不能留空或用占位符
""",
            "design_development_plan": """
你是一位资深的医疗器械研发项目经理，精通ISO 13485和《医疗器械生产质量管理规范》关于设计开发的要求。请根据以下产品信息和参考范文，生成{chapter}章节内容。

【产品信息】
- 产品名称：{product_name}
- 产品类型：{product_type}
- 产品参数：{product_params}

【重要要求】
请参考上方的【参考范文】和【相关法规标准】部分（如果提供），严格按照参考范文的详细程度生成{chapter}的完整内容。

特别注意：
0. 【强制要求】所有内容必须使用中文，不要使用任何英文单词或短语，除了标准号和缩写（如DHF、DMR等）中必须包含的部分
1. 设计开发阶段划分要清晰，每个阶段都要有明确的输入、输出和验收标准
2. 职责分配要具体到岗位和人员，包括项目经理、研发工程师、测试工程师、QA等
3. 设计评审、验证、确认活动要有明确的时间点、参与人员和输出文件要求
4. 技术资源配置要详细，包括所需的设备、软件、标准、法规等
5. 设计变更管理流程要完整，包括变更申请、评估、审批、实施、验证等环节
6. 时间安排要合理，考虑各阶段的依赖关系和风险缓冲
7. 每个条款都要有实质性内容，不能笼统概括
8. 引用的标准和法规要准确，如ISO 13485、《医疗器械生产质量管理规范》等
""",
            "design_input": """
你是一位资深的医疗器械系统工程师，负责制定产品设计输入要求。请根据以下产品信息和参考范文，生成{chapter}章节内容。

【产品信息】
- 产品名称：{product_name}
- 产品类型：{product_type}
- 产品参数：{product_params}

【重要要求】
请参考上方的【参考范文】和【相关法规标准】部分（如果提供），严格按照参考范文的详细程度生成{chapter}的完整内容。

特别注意：
0. 【强制要求】所有内容必须使用中文，不要使用任何英文单词或短语，除了标准号中必须包含的部分
1. 性能要求要具体、可测量，每个指标都要有明确的数值范围和测试方法
2. 法规标准要求要列出所有适用的强制标准和推荐标准，包括标准号和版本
3. 风险管理要求要与风险管理报告中的风险控制措施相对应
4. 用户需求要从临床使用角度详细描述，包括预期用途、使用场景、用户群体等
5. 设计输入评审记录要完整，包括评审人员、评审意见、修改情况等
6. 所有要求都要明确、无歧义，能够作为设计输出的依据
7. 表格要完整填写，每个单元格都要有具体内容
""",
            "design_output": """
你是一位资深的医疗器械研发工程师，负责编制设计输出文件。请根据以下产品信息和参考范文，生成{chapter}章节内容。

【产品信息】
- 产品名称：{product_name}
- 产品类型：{product_type}
- 产品参数：{product_params}

【重要要求】
请参考上方的【参考范文】和【相关法规标准】部分（如果提供），严格按照参考范文的详细程度生成{chapter}的完整内容。

特别注意：
0. 【强制要求】所有内容必须使用中文，不要使用任何英文单词或短语，除了标准号中必须包含的部分
1. 产品图纸和规范要详细，包括零件图、装配图、技术规范、物料清单等
2. 生产工艺文件要包括工艺流程、作业指导书、检验规程等，具有可操作性
3. 包装和标识规范要符合法规要求，包括包装材料、标签内容、使用说明书等
4. 设计输出文件要与设计输入一一对应，能够证明满足设计输入要求
5. 文件编号和版本管理要规范，包括文件编号规则、版本历史、审批记录等
6. 设计输出评审记录要完整，包括评审人员、评审意见、修改情况等
7. 每个条款都要有实质性内容，不能笼统概括
""",
            "design_review": """
你是一位资深的医疗器械质量经理，负责组织和记录设计评审活动。请根据以下产品信息和参考范文，生成{chapter}章节内容。

【产品信息】
- 产品名称：{product_name}
- 产品类型：{product_type}
- 产品参数：{product_params}

【重要要求】
请参考上方的【参考范文】和【相关法规标准】部分（如果提供），严格按照参考范文的详细程度生成{chapter}的完整内容。

特别注意：
0. 【强制要求】所有内容必须使用中文，不要使用任何英文单词或短语，除了标准号中必须包含的部分
1. 评审概述要说明评审的阶段、目的、范围和依据
2. 评审内容要详细列出评审的所有项目，包括设计输入、设计输出、风险评估等
3. 评审参与人员要列出姓名、部门、资格、职责，并预留签字栏
4. 评审发现和建议要详细记录发现的问题、风险点和改进建议
5. 评审结论要明确，包括是否通过、需要整改的内容、整改期限等
6. 整改措施跟踪要记录整改情况、验证结果、验证人员等
7. 表格要完整填写，每个单元格都要有具体内容
""",
            "design_verification": """
你是一位资深的医疗器械验证工程师，负责设计验证活动的实施和记录。请根据以下产品信息和参考范文，生成{chapter}章节内容。

【产品信息】
- 产品名称：{product_name}
- 产品类型：{product_type}
- 产品参数：{product_params}

【重要要求】
请参考上方的【参考范文】和【相关法规标准】部分（如果提供），严格按照参考范文的详细程度生成{chapter}的完整内容。

特别注意：
0. 【强制要求】所有内容必须使用中文，不要使用任何英文单词或短语，除了标准号中必须包含的部分
1. 验证概述要说明验证目的、范围、依据和验证计划
2. 验证方法要详细描述每种验证方法，包括检验、测试、对比、计算等
3. 验证项目和结果要与设计输入一一对应，列出测试数据、结果判定
4. 测试记录要完整，包括测试条件、测试设备、测试人员、测试时间等
5. 不符合项处理要记录不符合项描述、原因分析、纠正措施、验证结果
6. 验证结论要明确说明设计输出是否满足设计输入要求
7. 批准记录要完整，包括批准人、批准日期、批准意见
8. 表格要完整填写，每个单元格都要有具体内容
""",
            "design_validation": """
你是一位资深的医疗器械临床评价专家，负责设计确认活动的实施和记录。请根据以下产品信息和参考范文，生成{chapter}章节内容。

【产品信息】
- 产品名称：{product_name}
- 产品类型：{product_type}
- 产品参数：{product_params}

【重要要求】
请参考上方的【参考范文】和【相关法规标准】部分（如果提供），严格按照参考范文的详细程度生成{chapter}的完整内容。

特别注意：
0. 【强制要求】所有内容必须使用中文，不要使用任何英文单词或短语，除了标准号中必须包含的部分
1. 确认概述要说明确认目的、范围、依据和确认计划
2. 临床评价要详细描述临床试验设计、受试者选择、评价指标、统计分析等
3. 模拟使用测试要描述测试环境、测试人员、测试流程、评价方法
4. 确认结果分析要详细分析测试数据，评价产品的有效性和安全性
5. 确认结论要明确说明产品是否满足预期用途和用户需求
6. 批准记录要完整，包括批准人、批准日期、批准意见
7. 每个条款都要有实质性内容，不能笼统概括
""",
            "design_change": """
你是一位资深的医疗器械变更控制专员，负责设计变更的管理和记录。请根据以下产品信息和参考范文，生成{chapter}章节内容。

【产品信息】
- 产品名称：{product_name}
- 产品类型：{product_type}
- 产品参数：{product_params}

【重要要求】
请参考上方的【参考范文】和【相关法规标准】部分（如果提供），严格按照参考范文的详细程度生成{chapter}的完整内容。

特别注意：
0. 【强制要求】所有内容必须使用中文，不要使用任何英文单词或短语，除了标准号中必须包含的部分
1. 变更概述要详细描述变更内容、变更原因、变更发起部门和人员
2. 变更影响评估要分析变更对产品安全性、有效性、风险管理、注册申报等的影响
3. 变更验证计划要明确验证方法、验证内容、验证标准、验证时间
4. 变更审批要记录各级审批人员的意见和签字
5. 变更实施记录要记录实施过程、实施人员、实施时间、相关文件更新情况
6. 变更追溯性要说明变更涉及的文件、批次、产品范围
7. 表格要完整填写，每个单元格都要有具体内容
""",
            "design_history_file": """
你是一位资深的医疗器械DHF管理人员，负责设计历史文件的整理和归档。请根据以下产品信息和参考范文，生成{chapter}章节内容。

【产品信息】
- 产品名称：{product_name}
- 产品类型：{product_type}
- 产品参数：{product_params}

【重要要求】
请参考上方的【参考范文】和【相关法规标准】部分（如果提供），严格按照参考范文的详细程度生成{chapter}的完整内容。

特别注意：
0. 【强制要求】所有内容必须使用中文，不要使用任何英文单词或短语，除了标准号和缩写（如DHF、DMR等）中必须包含的部分
1. DHF目录要完整列出所有设计历史文件，包括文件编号、版本、日期、编制人等
2. 设计开发计划记录要包括计划文件、更新记录、审批记录
3. 设计输入输出记录要包括输入文件、输出文件、评审记录
4. 设计评审验证确认记录要包括各次评审、验证、确认的完整记录
5. 设计变更记录要包括所有变更的申请、评估、审批、实施、验证记录
6. DHF管理要说明归档、保存期限、查阅权限、借阅记录等要求
7. 表格要完整填写，每个单元格都要有具体内容
""",
            "product_spec": """
你是一位资深的医疗器械注册工程师，精通《医疗器械注册与备案管理办法》和各类医疗器械标准。请根据以下产品信息和参考范文，生成{chapter}章节内容。

【产品信息】
- 产品名称：{product_name}
- 产品类型：{product_type}
- 产品参数：{product_params}

【重要要求】
请参考上方的【参考范文】和【相关法规标准】部分（如果提供），严格按照参考范文的详细程度生成{chapter}的完整内容。

特别注意：
0. 【强制要求】所有内容必须使用中文，不要使用任何英文单词或短语，除了标准号中必须包含的部分
1. 技术参数必须极其详细，有具体的数值范围、精度要求、测试方法
2. 性能指标要分条列出，每条都要有明确的要求和对应的检验方法
3. 引用的国家标准、行业标准要准确，包括标准号和年代号
4. 检验方法要具体，包括使用的仪器设备、操作步骤、判定标准
5. 标志、包装、运输、贮存要求要详细，有具体的条件和期限
6. 所有内容都要像正式注册申报资料一样专业、规范
7. 表格要完整填写，每个单元格都要有具体内容
""",
            "instruction": """
你是一位资深的医疗器械文档工程师，精通《医疗器械说明书和标签管理规定》和各类医疗器械说明书编写规范。请根据以下产品信息和参考范文，生成{chapter}章节内容。

【产品信息】
- 产品名称：{product_name}
- 产品类型：{product_type}
- 产品参数：{product_params}

【重要要求】
请参考上方的【参考范文】和【相关法规标准】部分（如果提供），严格按照参考范文的详细程度生成{chapter}的完整内容。

特别注意：
0. 【强制要求】所有内容必须使用中文，不要使用任何英文单词或短语，除了标准号中必须包含的部分
1. 内容要极其细致，像正式的产品说明书一样完整
2. 使用方法要分步骤描述，每个步骤都要有具体的操作说明
3. 注意事项要全面，包括禁忌症、警告、提示等
4. 维护保养要有具体的方法、频次、检查项目
5. 故障排除要列出常见故障、原因分析、处理方法
6. 使用的语言要通俗易懂，但又要专业规范
7. 每个章节都要有实质性内容，不能简略
""",
            "sop": """
你是一位资深的医疗器械质量体系工程师，精通ISO 13485:2016和《医疗器械生产质量管理规范》，有多年编写SOP的实际经验。请根据以下产品信息和参考范文，生成{chapter}章节内容。

【产品信息】
- 产品名称：{product_name}
- 产品类型：{product_type}
- 产品参数：{product_params}

【重要要求】
请参考上方的【参考范文】和【相关法规标准】部分（如果提供），严格按照参考范文的详细程度生成{chapter}的完整内容。

特别注意：
0. 【强制要求】所有内容必须使用中文，不要使用任何英文单词或短语，除了标准号和缩写（如SOP、QA等）中必须包含的部分
1. 内容必须极其详细和具体，像正式执行的SOP一样具有可操作性
2. 每个操作步骤都要详细描述，包括使用的设备、工具、材料、操作要点、注意事项
3. 职责分工要明确到具体岗位，如操作人员、复核人员、QA人员等
4. 质量控制点要有明确的检验方法、验收标准、记录要求
5. 安全注意事项要具体，包括个人防护、设备安全、环境安全等
6. 引用的文件和记录表单要明确，如文件名、编号、版本
7. 异常情况处理要有具体的流程和责任人
8. 使用规范的SOP语言，表述准确、清晰、无歧义
9. 每个条款都要有实质性内容，不能笼统概括

生成内容的详细程度要像车间实际使用的作业指导书一样，能够指导操作人员完成每一步工作。
""",
        }
        return templates.get(doc_type, templates["risk_management_report"])

    def _generate_by_chapters(
        self,
        doc_type: str,
        product_name: str,
        product_type: str,
        product_params: str = ""
    ) -> str:
        """
        分章节生成文档内容并汇总

        流程：获取章节结构 -> 逐章生成内容 -> 汇总成完整文档

        Args:
            doc_type: 文档类型
            product_name: 产品名称
            product_type: 产品类型
            product_params: 产品参数

        Returns:
            AI生成的完整文档内容（Markdown格式）
        """
        if not self.api_key:
            raise ValueError("MINIMAX_API_KEY 未设置，请联系管理员配置")

        # 获取文档章节结构
        chapters = DOC_CHAPTERS.get(doc_type, DEFAULT_CHAPTERS)

        # 分章节生成
        full_document = []
        doc_type_names = {
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
        doc_name = doc_type_names.get(doc_type, doc_type)

        # 添加文档标题
        full_document.append(f"# {product_name} - {doc_name}\n\n")
        full_document.append(f"**产品信息：**\n")
        full_document.append(f"- 产品名称：{product_name}\n")
        full_document.append(f"- 产品类型：{product_type}\n")
        full_document.append(f"- 产品参数：{product_params if product_params else '无'}\n")
        full_document.append("---\n\n")

        print(f"开始分章节生成文档（共 {len(chapters)} 章）...")

        for i, chapter in enumerate(chapters, 1):
            chapter_name = chapter["name"]
            chapter_query = f"{chapter['query']} {product_name} {product_type}"

            print(f"  [{i}/{len(chapters)}] 生成章节：{chapter_name}...")

            # 1. 尝试RAG增强（如可用）
            chunks = []
            if _rag_available:
                for attempt in range(2):  # 重试1次
                    try:
                        vector_store = _vector_store()
                        # 使用混合检索 - 增加检索数量以获得更多参考
                        chunks = vector_store.retrieve_hybrid(
                            doc_type=doc_type,
                            query=chapter_query,
                            top_k=8,
                            similarity_threshold=0.3,
                            vector_weight=0.7
                        )
                        break  # 成功，跳出重试循环
                    except Exception as e:
                        if attempt == 0:
                            print(f"    RAG检索首次失败，重试中: {e}")
                            continue
                        print(f"    [WARNING] RAG检索最终失败，回退到无RAG模式: {e}")

            # 2. 尝试Web搜索补充（如可用）- 增强版
            web_info = ""
            downloaded_files = []
            if self.use_web_search and _web_search_service:
                try:
                    web_info, downloaded_files = _web_search_service.search_regulations(
                        chapter_name=chapter_name,
                        product_type=product_type,
                        product_params=product_params,
                        max_results=3,
                        enable_deep_scrape=True,
                        enable_file_download=True,
                        doc_type=doc_type
                    )
                    if web_info:
                        print(f"    Web搜索: 获取到 {len(web_info)} 字符相关信息")
                    if downloaded_files:
                        print(f"    下载文件: {len(downloaded_files)} 个")
                        # 将下载的文件添加到知识库
                        self._add_files_to_knowledge_base(downloaded_files, doc_type)
                except Exception as e:
                    print(f"    [WARNING] Web搜索失败: {e}")

            # 3. 构建本章Prompt
            template = self._get_prompt_template(doc_type)
            base_prompt = template.format(
                product_name=str(product_name),
                product_type=str(product_type),
                product_params=str(product_params) if product_params else "无特殊参数",
                chapter=chapter_name
            )

            # 4. 注入RAG上下文（如检索到相关内容）
            if chunks:
                enhanced_prompt = _rag_prompt_builder(
                    base_prompt=base_prompt,
                    doc_type=doc_type,
                    product_name=product_name,
                    product_type=product_type,
                    product_params=product_params,
                    retrieved_chunks=chunks
                )
                print(f"    RAG增强: 检索到 {len(chunks)} 条相关段落")
            else:
                enhanced_prompt = base_prompt

            # 5. 注入Web搜索上下文（如获取到相关内容）
            if web_info:
                enhanced_prompt = enhanced_prompt.rstrip() + "\n\n" + "【相关法规标准 - 来自网络搜索】\n" + web_info + "\n"

            # 6. 生成章节内容
            try:
                chapter_content = self._call_api(enhanced_prompt)
                full_document.append(f"## 第{i}章 {chapter_name}\n\n")
                full_document.append(chapter_content)
                full_document.append("\n\n")
                print(f"    完成 ({len(chapter_content)} 字符)")
            except Exception as e:
                print(f"    失败: {e}")
                full_document.append(f"## 第{i}章 {chapter_name}\n\n")
                full_document.append(f"（内容生成失败: {str(e)}）\n\n")

            # 章节间休息一下，避免API限流
            if i < len(chapters):
                time.sleep(0.5)

        print(f"文档生成完成！总计 {len(''.join(full_document))} 字符")
        return "".join(full_document)

    # 保留旧方法名作为别名，兼容现有调用
    generate_content_with_rag = _generate_by_chapters

    def _call_api(self, prompt: str) -> str:
        """内部方法：调用 MiniMax API（带重试机制）"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json; charset=utf-8"
        }

        payload = {
            "model": "Doubao-Seed-2.0-pro",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,  # 稍微提高温度以获得更丰富的内容
            "max_tokens": 12000  # 增加token限制以支持更详细的内容
        }

        # 创建 session 并配置重试策略
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"],
            raise_on_status=False
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        last_error = None
        for attempt in range(3):
            try:
                response = session.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=(30, 180)
                )
                response.raise_for_status()

                result = response.json()
                # Volcengine/OpenAI 兼容格式: choices[0].message.content
                choices = result.get("choices", [])
                if choices:
                    message = choices[0].get("message", {})
                    return message.get("content", "")
                return ""

            except requests.exceptions.Timeout as e:
                last_error = TimeoutError(f"MiniMax API 请求超时 (第{attempt + 1}次尝试)")
                if attempt < 2:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                    continue
                raise last_error
            except requests.exceptions.RequestException as e:
                last_error = ConnectionError(f"MiniMax API 请求失败 (第{attempt + 1}次尝试): {str(e)}")
                if attempt < 2:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                    continue
                raise last_error
            except (KeyError, IndexError, json.JSONDecodeError) as e:
                raise ValueError(f"解析API响应失败: {str(e)}")
            finally:
                session.close()

    def generate_content_with_fallback(
        self,
        doc_type: str,
        product_name: str,
        product_type: str,
        product_params: str = ""
    ) -> str:
        """
        生成文档内容（分章节生成模式，统一入口）

        优先使用分章节生成，当API不可用时降级为占位符
        """
        try:
            # 统一使用分章节生成模式
            return self._generate_by_chapters(
                doc_type, product_name, product_type, product_params
            )
        except Exception as e:
            return self._generate_placeholder(doc_type, product_name, product_type, product_params, str(e))

    def _generate_placeholder(
        self,
        doc_type: str,
        product_name: str,
        product_type: str,
        product_params: str,
        error: str
    ) -> str:
        """生成占位符内容（当API不可用时）"""
        doc_type_names = {
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

        return f"""# {product_name} - {doc_type_names.get(doc_type, doc_type)}

**产品信息：**
- 产品名称：{product_name}
- 产品类型：{product_type}
- 产品参数：{product_params if product_params else '无'}

---

## 文档内容

> **注意：** 当前AI服务暂时不可用（{error}），请手动填写以下内容。

---
*由 QMS Document Generator 自动生成 | {doc_type}*
"""

    def _add_files_to_knowledge_base(self, file_paths: List[str], doc_type: str):
        """
        将下载的文件添加到知识库中

        Args:
            file_paths: 文件路径列表
            doc_type: 文档类型
        """
        if not file_paths:
            return

        try:
            from app.services.rag.vector_store import VectorStore
            from app.services.rag.ingest import ingest_files

            print(f"    [知识库] 正在将 {len(file_paths)} 个文件添加到知识库...")

            # 摄入文件到向量库
            result = ingest_files(
                file_paths=file_paths,
                collection_name="all",
                force_doc_type=doc_type
            )

            print(f"    [知识库] 添加完成: {result['processed_docs']} 文档, {result['total_chunks']} chunks")

            # 重新初始化RAG组件（可选）
            global _rag_available, _vector_store, _rag_prompt_builder
            _rag_available = False
            _vector_store = None
            _rag_prompt_builder = None
            # 下次使用时会重新初始化

        except Exception as e:
            print(f"    [知识库] 添加失败: {e}")

