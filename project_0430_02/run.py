"""
QMS Document Generator - 启动脚本
"""

import uvicorn
import os
import sys

# 加载 .env 文件中的环境变量
from dotenv import load_dotenv
load_dotenv()

# 确保工作目录正确
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 打印环境变量检查（调试用）
print(f"Python: {sys.version}")
print(f"API Key loaded: {bool(os.getenv('MINIMAX_API_KEY'))}")
print(f"API Key prefix: {os.getenv('MINIMAX_API_KEY', '')[:10]}...")

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True
    )
