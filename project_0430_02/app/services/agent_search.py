"""
AgentSearchService - 基于 Claude Agent SDK 的智能网页搜索服务

使用 SDK 内置的 WebSearch 和 WebFetch 工具，让 Claude 自主决策搜索策略、
深度抓取页面、综合返回结果。替代原有的 Playwright 硬编码爬虫方案。

架构:
  AgentSearchService (async)  →  SyncAgentSearchService (sync wrapper)
  ── 匹配 SyncWebSearchService 接口，方便在 minimax.py 中互换 ──
"""

import os
import asyncio
from typing import Optional, Tuple

# Agent SDK 延迟导入
_sdk_available = None


def _check_sdk():
    """检查 Claude Agent SDK 是否可用"""
    global _sdk_available
    if _sdk_available is None:
        try:
            from claude_agent_sdk import query, ClaudeAgentOptions  # noqa: F401
            _sdk_available = True
        except ImportError:
            _sdk_available = False
    return _sdk_available


def _get_proxy_env() -> dict:
    """
    获取代理配置，用于传入 ClaudeAgentOptions.env

    优先级: CLAUDE_HTTP_PROXY > HTTP_PROXY
            CLAUDE_HTTPS_PROXY > HTTPS_PROXY
    """
    proxy_env = {}

    http_proxy = os.getenv("CLAUDE_HTTP_PROXY") or os.getenv("HTTP_PROXY") or ""
    https_proxy = os.getenv("CLAUDE_HTTPS_PROXY") or os.getenv("HTTPS_PROXY") or ""
    no_proxy = os.getenv("NO_PROXY") or ""

    if http_proxy:
        proxy_env["HTTP_PROXY"] = http_proxy
    if https_proxy:
        proxy_env["HTTPS_PROXY"] = https_proxy
    if no_proxy:
        proxy_env["NO_PROXY"] = no_proxy

    # Node.js 需要此变量才会代理 HTTPS 请求 (Node v22.21+ / v24.5+)
    if http_proxy or https_proxy:
        proxy_env["NODE_USE_ENV_PROXY"] = "1"

    return proxy_env


# 文档类型 → 中文名称映射（用于构建研究提示）
_DOC_TYPE_CN = {
    "sop": "作业指导书(SOP)",
    "risk_management_report": "风险管理报告",
    "risk_management_plan": "风险管理计划",
    "fmea_analysis": "FMEA分析",
    "product_spec": "产品技术要求",
    "instruction": "使用说明书",
    "design_development_plan": "设计和开发策划书",
    "design_input": "设计和开发输入记录",
    "design_output": "设计和开发输出记录",
    "design_review": "设计评审记录",
    "design_verification": "设计验证记录",
    "design_validation": "设计确认记录",
    "design_change": "设计变更控制记录",
    "design_history_file": "设计历史文件(DHF)",
}


class AgentSearchService:
    """基于 Claude Agent SDK 的智能搜索服务（异步）"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.sdk_available = _check_sdk()
        self._available = bool(self.api_key) and self.sdk_available

    @property
    def available(self) -> bool:
        return self._available

    async def research_chapter(
        self,
        chapter_name: str,
        product_type: str,
        product_params: str = "",
        doc_type: str = "",
        timeout: int = 120
    ) -> Optional[str]:
        """
        使用 Agent SDK 研究章节相关内容

        Args:
            chapter_name: 章节名称（如 "风险分析"、"操作步骤"）
            product_type: 产品类型（如 "血糖仪"）
            product_params: 产品参数（可选）
            doc_type: 文档类型 key
            timeout: 超时秒数

        Returns:
            综合研究结果文本，失败/超时/不可用时返回 None
        """
        if not self._available:
            return None

        from claude_agent_sdk import query, ClaudeAgentOptions

        prompt = self._build_research_prompt(
            chapter_name, product_type, product_params, doc_type
        )
        proxy_env = _get_proxy_env()

        options = ClaudeAgentOptions(
            allowed_tools=["WebSearch", "WebFetch"],
            permission_mode="acceptEdits",
            env=proxy_env,
        )

        try:
            result_parts = []

            async def _collect():
                async for message in query(prompt=prompt, options=options):
                    if hasattr(message, "result") and message.result:
                        result_parts.append(str(message.result))

            await asyncio.wait_for(_collect(), timeout=timeout)

            if result_parts:
                return "\n\n".join(result_parts)
            return None

        except asyncio.TimeoutError:
            print(f"    [AGENT SEARCH] 研究超时 ({timeout}s): {chapter_name}")
            return None
        except Exception as e:
            print(f"    [AGENT SEARCH] 研究失败: {e}")
            return None

    def _build_research_prompt(
        self,
        chapter_name: str,
        product_type: str,
        product_params: str = "",
        doc_type: str = ""
    ) -> str:
        """构建研究提示词 —— 引导 Claude 搜索并综合信息"""
        doc_type_cn = _DOC_TYPE_CN.get(doc_type, "质量管理文档")

        product_info = f"产品类型：{product_type}"
        if product_params:
            product_info += f"，产品参数：{product_params}"

        return f"""你是一位医疗器械法规研究专家。请搜索以下主题的相关信息，并综合成一份结构化的研究报告。

【研究主题】
- 文档类型：{doc_type_cn}
- 章节名称：{chapter_name}
- {product_info}

【搜索要求】
1. 优先搜索中国医疗器械法规标准（GB标准、YY标准、国家药监局公告）
2. 搜索国际标准（ISO 13485、ISO 14971 等）
3. 搜索相关模板、范本和行业最佳实践
4. 对该章节涉及的具体条款、要求、格式和关键内容进行详细搜索

【输出要求】
- 用中文输出综合研究报告
- 列出找到的具体标准号和关键条款
- 总结关键的法规要求和指导原则
- 如果找到模板信息，描述其结构和关键字段
- 标注信息来源（URL 或标准号）
- 控制在 1000 字以内，突出与章节直接相关的信息

请开始搜索并给出综合研究结果。"""


class SyncAgentSearchService:
    """
    同步包装器，用于非 async 上下文

    接口与 SyncWebSearchService 保持一致，方便在 minimax.py 中互换调用。
    """

    def __init__(self, api_key: Optional[str] = None):
        self.async_service = AgentSearchService(api_key)
        self.available = self.async_service.available

    def search_regulations(
        self,
        chapter_name: str,
        product_type: str,
        product_params: str = "",
        max_results: int = 3,          # 保持接口兼容，Agent SDK 忽略
        enable_deep_scrape: bool = True,  # 保持接口兼容
        enable_file_download: bool = True,  # 保持接口兼容
        doc_type: str = "sop",
        timeout: int = 120
    ) -> Tuple[str, list]:
        """
        同步搜索（内部使用 asyncio.run()）

        Returns:
            (research_text, []) — 元组格式与 SyncWebSearchService 一致
        """
        try:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    self.async_service.research_chapter(
                        chapter_name=chapter_name,
                        product_type=product_type,
                        product_params=product_params,
                        doc_type=doc_type,
                        timeout=timeout
                    )
                )
                result = future.result(timeout=timeout + 10)
                return (result or "", [])
        except Exception as e:
            print(f"    [AGENT SEARCH] 同步调用失败: {e}")
            return ("", [])
