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
