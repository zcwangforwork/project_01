"""
Embedder - 嵌入模型封装

使用火山方舟向量化 API（doubao-embedding-vision）生成文本嵌入向量。
SDK 文档: https://www.volcengine.com/docs/82379/1541595
API 文档: https://www.volcengine.com/docs/82379/1523520
"""

import os
import time
from typing import Optional

# 延迟导入避免启动时耗时
_client = None


class Embedder:
    """嵌入模型封装 - 火山方舟向量化 SDK"""

    # 默认模型
    DEFAULT_MODEL = "doubao-embedding-vision-250615"

    # 默认向量维度
    DEFAULT_DIMENSIONS = 2048

    def __init__(
        self,
        model_name: Optional[str] = None,
        dimensions: int = DEFAULT_DIMENSIONS,
        api_key: Optional[str] = None,
    ):
        """
        初始化嵌入模型

        Args:
            model_name: 火山方舟模型 ID，默认 doubao-embedding-vision-250615
            dimensions: 向量维度，支持 1024 或 2048，默认 2048
            api_key: API Key，默认从环境变量 MINIMAX_API_KEY 读取
        """
        self.model_name = model_name or self.DEFAULT_MODEL
        self.dimensions = dimensions
        self.api_key = api_key or os.getenv("MINIMAX_API_KEY", "")
        self._client = None

    @property
    def client(self):
        """延迟初始化 Ark SDK 客户端"""
        global _client
        if _client is None:
            from volcenginesdkarkruntime import Ark
            # 修复 SSL_CERT_FILE 指向不存在文件导致的问题
            ssl_cert = os.environ.pop("SSL_CERT_FILE", None)
            try:
                _client = Ark(api_key=self.api_key)
            finally:
                if ssl_cert is not None:
                    os.environ["SSL_CERT_FILE"] = ssl_cert
        return _client

    def encode(self, texts: list[str], batch_size: int = 20) -> list[list[float]]:
        """
        将文本列表转换为嵌入向量列表

        当文本数量较多时，分批调用 API 以避免超限。

        Args:
            texts: 文本列表
            batch_size: 每批最大文本数，默认 20

        Returns:
            嵌入向量列表，每个向量 2048 维（或 1024 维）
        """
        if not texts:
            return []

        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]

            # 带重试的 API 调用
            last_error = None
            for attempt in range(3):
                try:
                    # 构建输入列表
                    input_data = [{"type": "text", "text": t} for t in batch]

                    resp = self.client.multimodal_embeddings.create(
                        model=self.model_name,
                        input=input_data,
                        encoding_format="float",
                        dimensions=self.dimensions,
                    )

                    # 从响应中提取 embedding
                    # resp.data 是列表，每个元素有 embedding 属性
                    batch_embeddings = []
                    for item in resp.data:
                        batch_embeddings.append(item.embedding)

                    all_embeddings.extend(batch_embeddings)
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

            # 批次间短暂间隔，避免限流
            if i + batch_size < len(texts):
                time.sleep(0.2)

        return all_embeddings

    def encode_single(self, text: str) -> list[float]:
        """单条文本嵌入"""
        return self.encode([text])[0]
