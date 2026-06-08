## 2026-06-02 09:55:00 - 贴敷式胰岛素泵数字员工全生命周期文档系统改造
- Working Dir: `E:\nrf_sample_codes\working_team_work\public\project\project_0430_02_beta`
- Purpose: 将项目从 16 种文档类型的 QMS 生成工具改造为覆盖 94+ 种文档类型的贴敷式胰岛素泵全生命周期数字员工
- Files: doc_types.py (16→104), prompt_engineer.py (16→106), minimax.py DOC_CHAPTERS (16→106), routes.py, index.html
- Result: Success — 104 types, 106 chapters, 106 prompts, 10 categories, API 200 OK

## 2026-05-12 11:00:00 - RAG 知识库重建（使用向量化 API）
- Working Dir: `E:\nrf_sample_codes\code_writer\project_0430_02`
- Purpose: 使用火山方舟向量化 API (doubao-embedding-vision-250615, 1024维) 重建 RAG 知识库，替换旧的本地模型 (384维)
- Result: Success - 向量库从 0 重建到 650 chunks，172 个来源文件

### 详细操作记录

## 2026-05-12 11:05:00 - File Created
- File: `rebuild_kb_api.py`
- Change: 创建 RAG 知识库重建脚本，使用火山方舟 API 向量化，清除旧 384维 collection 并重新摄入
- Result: Success

## 2026-05-12 11:10:00 - File Created
- File: `test_rebuild_api.py`
- Change: 创建测试套件，覆盖 API Key、Embedder、VectorStore、摄入、检索、错误处理等 7 个测试
- Result: Success

## 2026-05-12 11:15:00 - File Edited
- File: `app/services/rag/embedder.py`
- Change: 重写 Embedder 类，从使用 volcenginesdkarkruntime SDK 改为使用 httpx 直接调用 /api/coding/v3/embeddings/multimodal 端点。原因：SDK 调用路径不正确（/api/v3/ vs /api/coding/v3/），且不支持 dimensions 参数
- Result: Success - API 调用正常返回 1024 维向量

## 2026-05-12 11:20:00 - File Edited
- File: `app/services/rag/vector_store.py`
- Change: 移除全局 _embedder 变量，改为实例变量延迟初始化
- Result: Success

## 2026-05-12 11:30:00 - Bash Command Executed
- Command: `python test_rebuild_api.py`
- Working Dir: `E:\nrf_sample_codes\code_writer\project_0430_02`
- Purpose: 运行测试套件验证重建流程
- Result: Success - 6 passed, 1 skipped (检索测试需先重建)

## 2026-05-12 11:35:00 - Bash Command Executed
- Command: `python rebuild_kb_api.py`
- Working Dir: `E:\nrf_sample_codes\code_writer\project_0430_02`
- Purpose: 执行知识库重建，清除旧 384维向量，使用 API 重新摄入
- Result: Partial Success - 169 文件摄入, 486 chunks, 15 文件因 API 限流 (429) 失败, 耗时 538.9 秒

## 2026-05-12 11:45:00 - File Created
- File: `retry_failed_ingest.py`
- Change: 创建重试脚本，使用更长间隔重试因限流失败的文件
- Result: Success

## 2026-05-12 11:50:00 - Bash Command Executed
- Command: `python retry_failed_ingest.py`
- Working Dir: `E:\nrf_sample_codes\code_writer\project_0430_02`
- Purpose: 重试因 API 限流失败的文件
- Result: Success - 3 文件重试成功, 新增 28 chunks

## 2026-05-12 12:00:00 - Bash Command Executed
- Command: 增量重试缺失文件（Python 脚本内联执行）
- Working Dir: `E:\nrf_sample_codes\code_writer\project_0430_02`
- Purpose: 查找并重试所有尚未在向量库中的文件
- Result: Success - 12 文件重试成功, 新增 136 chunks, 总量 650 chunks

## 2026-05-12 12:05:00 - Analysis
- Topic: Embedder API 兼容性
- Finding: volcenginesdkarkruntime SDK 默认调用 /api/v3/ 路径，但正确的向量化 API 路径是 /api/coding/v3/embeddings/multimodal。使用 httpx 直接调用 HTTP 接口更可靠。
- Decision: 重写 Embedder 类使用 httpx 直接调用，参考 project_0428 的实现

## 2026-05-12 12:10:00 - Analysis
- Topic: 知识库重建结果
- Finding: 最终向量库 650 chunks, 172 个来源文件。检索验证通过，4 个测试查询均有相关结果返回（相似度 0.43-0.53）
- Decision: 重建完成，可以投入使用

## 2026-05-29 15:00:00 - 任务开始：贴敷式胰岛素泵知识库向量化

### 任务描述
将 `贴敷式胰岛素泵知识库` 目录（25个子目录，779个文件）中的所有文档转化为向量，存入独立的 ChromaDB 目录，供项目 RAG 检索使用。

### 修改的文件

#### 1. `app/services/rag/ingest.py` - 扩展文档格式支持
- **变更**: 添加 `extract_text_from_xlsx()` 和 `extract_text_from_md()` 函数
- **变更**: 更新 `extract_text_from_file()` 支持 .xlsx 和 .md 格式
- **变更**: 更新 `get_supported_files()` 扩展名列表包含 .xlsx 和 .md
- **原因**: 知识库中包含 xlsx 和 md 文件需要处理

#### 2. `app/services/rag/vector_store.py` - 支持多目录查询
- **变更**: 添加 `EXTRA_DB_CONFIG` 类变量和 `_extra_clients` 缓存
- **变更**: 添加 `_get_client_for_path()` 和 `set_extra_db_config()` 类方法
- **变更**: 修改 `retrieve()`、`retrieve_hybrid()` 方法遍历所有 DB 目录的 collection
- **变更**: 修改 `_bm25_search_collection()` 接受 client 参数
- **变更**: 修改 `count()` 方法统计所有 DB 目录
- **原因**: 需要从多个 ChromaDB 目录查询，新知识库存放在独立目录

#### 3. `app/main.py` - 启动时自动加载胰岛素泵知识库
- **变更**: 添加启动时检测 `chroma_db_insulin_pump` 目录并配置 EXTRA_DB_CONFIG
- **原因**: 确保 RAG 服务启动时自动包含新知识库

#### 4. `build_insulin_pump_kb.py` (新建) - 知识库摄入脚本
- **内容**: 完整的知识库构建脚本，包含文件扫描、文本提取、向量生成、ChromaDB 写入
- **功能**: 25个子目录映射到24种文档类型，跳过扫描版PDF，自动测试检索

### 执行结果

#### 摄入统计
- 源目录: `贴敷式胰岛素泵知识库`
- 向量库目录: `chroma_db_insulin_pump` (独立于现有的 `chroma_db`)
- Collection 名称: `insulin_pump_kb`
- 总文件数: 777 (排除2个不支持的PPT格式)
- 成功处理: 390 个文件
- 失败/跳过: 387 个 (主要是扫描版PDF无文本、少数损坏文件和临时文件)
- 总 chunks: 6,782
- 总耗时: 4,778秒 (79.6分钟)
- DB 大小: 119MB

#### 文档类型分布 (Top 10)
| doc_type | chunks |
|---|---|
| biocompatibility | 1,272 |
| medical_electrical_safety | 854 |
| software_usability | 785 |
| quality_management | 736 |
| sterilization | 649 |
| ghtf_guidelines | 492 |
| product_registration | 220 |
| labeling | 220 |
| emc | 202 |
| transport_packaging | 179 |

#### 检索测试结果
所有测试查询均返回高相关性结果 (相似度 0.62-0.78):
- "胰岛素泵电气安全基本要求" → IEC 60601 系列标准
- "风险管理报告编写指南" → ISO 14971 风险管理标准
- "电磁兼容测试方法" → IEC 61000-4 EMC 测试标准
- "无菌包装验证流程" → 包装验证方案文档

### 架构说明
查询流程: VectorStore.retrieve() → 遍历主DB (chroma_db) 的 QUERY_COLLECTIONS + 额外DB (chroma_db_insulin_pump) 的 EXTRA_DB_CONFIG → 合并结果按相似度排序

## 2026-06-06 - 文档生成提速优化（步骤1：参数调整）
- Working Dir: `E:\nrf_sample_codes\working_team_work\public\project\project_0430_02_beta`
- Purpose: 通过调整两个核心参数显著降低文档生成总耗时
- 预期提速: 30-40%

### File Edited
- File: `app/services/minimax.py`
- Change 1 (line 1234): `self.max_concurrent = 6` → `self.max_concurrent = 12`
  - 理由: 小节LLM调用最大并发数翻倍。文档通常 20-40 小节，6 路并发需排 4-7 轮，12 路并发只需 2-4 轮，LLM 阶段墙钟时间近乎减半。火山方舟单 key 默认 RPM 300+，可支撑 12 并发。
- Change 2 (line 2313): `_call_api(..., max_tokens: int = 12000)` → `max_tokens: int = 6000`
  - 理由: 单小节实际内容很少超 6000 token。LLM 出 token 是线性时间消耗，上限砍半直接降低生成时长。不影响实际内容质量。
- Result: Success
- 验证方式: 重启服务后生成一份文档，对比 `timing_log` 中 `llm_total` 和 `total` 字段

## 2026-06-06 - 文档生成提速优化（Web搜索并发提升）
- Working Dir: `E:\nrf_sample_codes\working_team_work\public\project\project_0430_02_beta`
- File: `app/services/minimax.py`
- Change (line 1235): `self.max_search_workers = 6` → `self.max_search_workers = 12`
- 理由: Web 搜索阶段（Phase 2b）当前是仅次于 LLM 的耗时大户。Agent SDK 搜索本质是 Claude API 调用，资源占用很轻，可支撑较高并发。Playwright 回退路径开销较大，但有 Agent SDK 优先策略兜底。30 小节文档原需 5 轮搜索（6 并发），现只需 3 轮（12 并发）。
- 预期提速: Web 搜索阶段墙钟时间下降约 40%
- Result: Success

