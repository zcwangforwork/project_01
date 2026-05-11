"""
VectorStore - ChromaDB 向量存储封装

提供文档摄入和语义检索功能。
"""

import os
import json
from pathlib import Path
from typing import Optional, List, Dict

import chromadb
from chromadb.config import Settings

from app.services.rag.embedder import Embedder

# 延迟导入
_chroma_client = None
_embedder = None


class VectorStore:
    """ChromaDB 向量存储封装"""

    # ChromaDB 持久化目录
    BASE_DIR = Path(__file__).parent.parent.parent.parent / "chroma_data"
    COLLECTION_NAME_PREFIX = "qms_doc_"

    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: Optional[str] = None
    ):
        """
        初始化向量存储

        Args:
            persist_directory: ChromaDB 数据持久化目录
            collection_name: collection 名称（不包含前缀），默认使用 "all"
        """
        self.persist_directory = persist_directory or str(self.BASE_DIR)
        self.collection_name = collection_name or "all"

        # 确保目录存在
        os.makedirs(self.persist_directory, exist_ok=True)

        self._client = None
        self._collection = None
        self._embedder = None

    @property
    def client(self):
        """延迟初始化 ChromaDB 客户端"""
        global _chroma_client
        if _chroma_client is None:
            _chroma_client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(anonymized_telemetry=False)
            )
        return _chroma_client

    @property
    def embedder(self):
        """延迟初始化嵌入器"""
        global _embedder
        if _embedder is None:
            _embedder = Embedder()
        return _embedder

    @property
    def collection(self):
        """获取或创建 collection"""
        if self._collection is None:
            full_name = f"{self.COLLECTION_NAME_PREFIX}{self.collection_name}"
            self._collection = self.client.get_or_create_collection(
                name=full_name,
                metadata={"description": "QMS 医疗器械文档参考库"}
            )
        return self._collection

    def add_chunk(
        self,
        chunk_id: str,
        text: str,
        doc_type: str,
        source_file: str,
        section_title: Optional[str] = None,
        chunk_index: int = 0,
        metadata: Optional[dict] = None
    ):
        """
        添加单个文档块到向量库

        Args:
            chunk_id: 块唯一 ID
            text: 文本内容
            doc_type: 文档类型（用于过滤）
            source_file: 来源文件名
            section_title: 章节标题
            chunk_index: 块在文档中的顺序索引
            metadata: 额外元数据
        """
        meta = {
            "doc_type": doc_type,
            "source_file": source_file,
            "section_title": section_title or "",
            "chunk_index": chunk_index,
            **(metadata or {})
        }

        # 使用我们的嵌入器生成向量
        embedding = self.embedder.encode_single(text)

        self.collection.add(
            ids=[chunk_id],
            documents=[text],
            metadatas=[meta],
            embeddings=[embedding]
        )

    def add_chunks(self, chunks: list[dict]):
        """
        批量添加文档块

        Args:
            chunks: 块列表，每项包含 chunk_id, text, doc_type, source_file 等
        """
        if not chunks:
            return

        ids = [c["chunk_id"] for c in chunks]
        texts = [c["text"] for c in chunks]
        metadatas = [
            {
                "doc_type": c.get("doc_type", ""),
                "source_file": c.get("source_file", ""),
                "section_title": c.get("section_title", ""),
                "chunk_index": c.get("chunk_index", 0)
            }
            for c in chunks
        ]

        # 使用我们的嵌入器批量生成向量
        embeddings = self.embedder.encode(texts)

        self.collection.add(
            ids=ids,
            documents=texts,
            metadatas=metadatas,
            embeddings=embeddings
        )

    def retrieve(
        self,
        query: str,
        doc_type: Optional[str] = None,
        top_k: int = 5,
        similarity_threshold: float = 0.0  # 默认 0.0 允许几乎所有结果通过
    ) -> list[dict]:
        """
        语义检索

        Args:
            query: 查询文本（产品信息）
            doc_type: 文档类型过滤（可选）
            top_k: 返回数量
            similarity_threshold: 最低相似度阈值（0-1），默认 0.0

        Returns:
            检索结果列表，每项包含 text, source_file, section_title, distance
        """
        # 使用我们的嵌入器生成查询向量
        query_embedding = self.embedder.encode_single(query)

        # 使用向量检索而不是文本检索
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )

        output = []
        if results["ids"]:
            for i in range(len(results["ids"][0])):
                distance = results["distances"][0][i]
                # ChromaDB 0.4.x 返回的是余弦距离，范围 [0, 2]
                # 0 = 完全相同，2 = 完全相反
                # 转换为相似度 (0-1): 1 - distance/2 使 0→1, 2→0
                similarity = max(0.0, 1.0 - distance / 2.0)

                if similarity < similarity_threshold:
                    continue

                output.append({
                    "text": results["documents"][0][i],
                    "source_file": results["metadatas"][0][i].get("source_file", ""),
                    "section_title": results["metadatas"][0][i].get("section_title", ""),
                    "doc_type": results["metadatas"][0][i].get("doc_type", ""),
                    "chunk_index": results["metadatas"][0][i].get("chunk_index", 0),
                    "similarity": similarity,
                    "distance": distance
                })

        return output

    def retrieve_hybrid(
        self,
        query: str,
        doc_type: Optional[str] = None,
        top_k: int = 5,
        similarity_threshold: float = 0.3,
        vector_weight: float = 0.6
    ) -> list[dict]:
        """
        混合检索：语义向量检索 + BM25 关键词检索

        Args:
            query: 查询文本
            doc_type: 文档类型过滤（可选），如果过滤后无结果则忽略
            top_k: 返回数量
            similarity_threshold: 最低相似度阈值（0-1）
            vector_weight: 向量检索权重 (0-1)，BM25权重 = 1 - vector_weight

        Returns:
            合并后的检索结果列表，按综合分数排序
        """
        # 使用我们的嵌入器生成查询向量
        query_embedding = self.embedder.encode_single(query)

        # 1. 向量检索（获取更多候选）
        vector_results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k * 2,
            include=["documents", "metadatas", "distances"]
        )

        # 构建向量检索结果字典
        vector_dict = {}
        doc_type_filtered_count = 0
        if vector_results["ids"]:
            for i in range(len(vector_results["ids"][0])):
                chunk_id = vector_results["ids"][0][i]
                distance = vector_results["distances"][0][i]
                similarity = max(0.0, 1.0 - distance / 2.0)

                if similarity >= similarity_threshold:
                    meta = vector_results["metadatas"][0][i]
                    chunk_doc_type = meta.get("doc_type", "")

                    # doc_type 过滤
                    if doc_type and chunk_doc_type != doc_type:
                        doc_type_filtered_count += 1
                        continue

                    vector_dict[chunk_id] = {
                        "text": vector_results["documents"][0][i],
                        "source_file": meta.get("source_file", ""),
                        "section_title": meta.get("section_title", ""),
                        "doc_type": chunk_doc_type,
                        "chunk_index": meta.get("chunk_index", 0),
                        "similarity": similarity,
                        "vector_score": similarity,
                        "bm25_score": 0.0
                    }

        # 如果 doc_type 过滤后无结果，忽略过滤重新检索
        if not vector_dict and doc_type:
            print(f"    [RAG] doc_type='{doc_type}' 过滤无结果，忽略类型过滤")
            for i in range(len(vector_results["ids"][0])):
                chunk_id = vector_results["ids"][0][i]
                distance = vector_results["distances"][0][i]
                similarity = max(0.0, 1.0 - distance / 2.0)

                if similarity >= similarity_threshold:
                    meta = vector_results["metadatas"][0][i]
                    vector_dict[chunk_id] = {
                        "text": vector_results["documents"][0][i],
                        "source_file": meta.get("source_file", ""),
                        "section_title": meta.get("section_title", ""),
                        "doc_type": meta.get("doc_type", ""),
                        "chunk_index": meta.get("chunk_index", 0),
                        "similarity": similarity,
                        "vector_score": similarity,
                        "bm25_score": 0.0
                    }

        # 2. BM25 关键词检索
        bm25_scores = self._bm25_search(query, None, top_k * 2)  # BM25 不过滤doc_type

        # 3. 合并结果
        all_ids = set(vector_dict.keys()) | set(bm25_scores.keys())

        merged = []
        for chunk_id in all_ids:
            vec_score = vector_dict.get(chunk_id, {}).get("vector_score", 0.0)
            bm_score = bm25_scores.get(chunk_id, 0.0)

            # 归一化并计算综合分数
            if vec_score > 0 and bm_score > 0:
                combined_score = vector_weight * vec_score + (1 - vector_weight) * bm_score
            elif vec_score > 0:
                combined_score = vec_score * vector_weight
            elif bm_score > 0:
                combined_score = bm_score * (1 - vector_weight)
            else:
                continue

            chunk_info = vector_dict.get(chunk_id, {})
            merged.append({
                "text": chunk_info.get("text", ""),
                "source_file": chunk_info.get("source_file", ""),
                "section_title": chunk_info.get("section_title", ""),
                "doc_type": chunk_info.get("doc_type", ""),
                "chunk_index": chunk_info.get("chunk_index", 0),
                "similarity": combined_score,
                "vector_score": vec_score,
                "bm25_score": bm_score
            })

        # 按综合分数排序
        merged.sort(key=lambda x: x["similarity"], reverse=True)

        return merged[:top_k]

    def _bm25_search(
        self,
        query: str,
        doc_type: Optional[str] = None,
        top_k: int = 10
    ) -> dict:
        """
        BM25 关键词检索

        Returns:
            {chunk_id: bm25_score, ...}
        """
        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            return {}

        try:
            # 获取所有 chunks
            result = self.collection.get(include=["documents", "metadatas"])
            if not result["ids"]:
                return {}

            ids = result["ids"]
            docs = result["documents"]
            metas = result["metadatas"]

            # doc_type 过滤
            if doc_type:
                filtered_ids = []
                filtered_docs = []
                for i, meta in enumerate(metas):
                    if meta and meta.get("doc_type") == doc_type:
                        filtered_ids.append(ids[i])
                        filtered_docs.append(docs[i])
                ids = filtered_ids
                docs = filtered_docs

            if not docs:
                return {}

            # 分词
            tokenized_corpus = [doc.lower().split() for doc in docs]
            query_tokens = query.lower().split()

            bm25 = BM25Okapi(tokenized_corpus)
            scores = bm25.get_scores(query_tokens)

            # 返回 top_k
            top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

            return {
                ids[i]: scores[i] for i in top_indices if scores[i] > 0
            }
        except Exception:
            return {}

    def count(self) -> int:
        """返回 collection 中的文档块数量"""
        return self.collection.count()

    def clear(self):
        """清空 collection（谨慎使用）"""
        try:
            self.client.delete_collection(
                name=f"{self.COLLECTION_NAME_PREFIX}{self.collection_name}"
            )
            self._collection = None
        except Exception:
            pass

    def delete_by_source(self, source_file: str):
        """
        删除指定来源文件的所有块

        Args:
            source_file: 来源文件名
        """
        try:
            self.collection.delete(
                where={"source_file": source_file}
            )
        except Exception:
            pass

    def get_sources(self) -> list[str]:
        """获取向量库中所有来源文件列表"""
        try:
            result = self.collection.get(include=["metadatas"])
            sources = set()
            for meta in result.get("metadatas", []):
                if meta and meta.get("source_file"):
                    sources.add(meta["source_file"])
            return sorted(list(sources))
        except Exception:
            return []
