"""
Embedder - 嵌入模型封装

使用火山方舟向量化 API（doubao-embedding-vision）生成文本嵌入向量。
通过 HTTP 直接调用 /api/coding/v3/embeddings/multimodal 接口。
API 文档: https://www.volcengine.com/docs/82379/1523520
"""

import os
import time
from pathlib import Path
from typing import Optional

import httpx


class Embedder:
    """嵌入模型封装 - 火山方舟向量化 API"""

    # 默认模型
    DEFAULT_MODEL = "doubao-embedding-vision-250615"

    # 默认 API URL
    DEFAULT_API_URL = "https://ark.cn-beijing.volces.com/api/coding/v3/embeddings/multimodal"

    # 默认向量维度
    DEFAULT_DIMENSIONS = 1024

    def __init__(
        self,
        model_name: Optional[str] = None,
        dimensions: int = DEFAULT_DIMENSIONS,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
    ):
        """
        初始化嵌入模型

        Args:
            model_name: 火山方舟模型 ID，默认 doubao-embedding-vision-250615
            dimensions: 向量维度，支持 1024 或 2048，默认 1024
            api_key: API Key，默认从环境变量 MINIMAX_API_KEY 读取
            api_url: API URL，默认火山方舟向量化 API
        """
        self.model_name = model_name or self.DEFAULT_MODEL
        self.dimensions = dimensions
        self._api_key = api_key
        self._api_url = api_url or self.DEFAULT_API_URL
        self._api_key_resolved = None

    @property
    def api_key(self):
        """延迟读取 API Key，确保 .env 已加载"""
        if self._api_key_resolved is None:
            from dotenv import load_dotenv
            env_path = Path(__file__).parent.parent.parent.parent / '.env'
            if env_path.exists():
                load_dotenv(dotenv_path=env_path)
            self._api_key_resolved = self._api_key or os.getenv("MINIMAX_API_KEY", "")
            print(f"[Embedder] API Key loaded: {'Yes' if self._api_key_resolved else 'No'}")
        return self._api_key_resolved

    def encode(self, texts: list[str], batch_size: int = 20) -> list[list[float]]:
        """
        将文本列表转换为嵌入向量列表

        逐条调用 API，每条之间短暂间隔避免限流。

        Args:
            texts: 文本列表
            batch_size: 每批最大文本数（用于进度打印），默认 20

        Returns:
            嵌入向量列表，每个向量 1024 维（或 2048 维）
        """
        if not texts:
            return []

        all_embeddings = []

        for i, text in enumerate(texts):
            # 带重试的 API 调用
            last_error = None
            for attempt in range(3):
                try:
                    embedding = self._call_api(text)
                    all_embeddings.append(embedding)
                    break
                except Exception as e:
                    last_error = e
                    if attempt < 2:
                        wait = 2 ** attempt
                        print(
                            f"    [Embedder] API 请求失败，{wait}s 后重试 "
                            f"(第{attempt + 1}次): {e}"
                        )
                        time.sleep(wait)
                        continue
                    raise ConnectionError(
                        f"向量化 API 请求失败（已重试3次）: {last_error}"
                    )

            # 进度打印
            if (i + 1) % batch_size == 0:
                print(f"    [Embedder] 已完成 {i + 1}/{len(texts)} 条向量化")

            # 间隔避免限流
            if i + 1 < len(texts):
                time.sleep(0.1)

        return all_embeddings

    def encode_single(self, text: str) -> list[float]:
        """单条文本嵌入"""
        return self.encode([text])[0]

    def _call_api(self, text: str) -> list[float]:
        """
        调用火山方舟向量化 API

        Args:
            text: 待向量化的文本

        Returns:
            嵌入向量
        """
        # 截断过长文本
        text = text[:8000]

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "model": self.model_name,
            "encoding_format": "float",
            "dimensions": self.dimensions,
            "input": [{"text": text, "type": "text"}]
        }

        with httpx.Client(timeout=60, trust_env=False) as client:
            response = client.post(self._api_url, headers=headers, json=payload)

            if response.status_code == 200:
                result = response.json()
                data = result.get("data", {})
                if data:
                    embedding = data.get("embedding", [])
                    if embedding:
                        return embedding
                raise ValueError(f"API 返回数据格式异常: {str(result)[:200]}")
            else:
                raise ConnectionError(
                    f"API 请求失败 (HTTP {response.status_code}): {response.text[:300]}"
                )
