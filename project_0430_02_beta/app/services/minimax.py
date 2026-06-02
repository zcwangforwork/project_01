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

from app.services.doc_types import DOC_TYPE_LABELS

# RAG 组件 - 延迟导入避免启动时耗时
_rag_available = False
_vector_store = None
_rag_prompt_builder = None

# Web 搜索组件 - 延迟初始化
_web_search_available = None
_web_search_service = None

# Agent 搜索组件 — Claude Agent SDK（延迟初始化）
_agent_search_available = None
_agent_search_service = None

# 跨 collection 检索 — uploads collection 是否可用
_uploads_collection_available = None


def _try_init_agent_search():
    """延迟初始化 Agent SDK 搜索组件"""
    global _agent_search_available, _agent_search_service
    if _agent_search_available is not None:
        return _agent_search_available
    try:
        from app.services.agent_search import SyncAgentSearchService
        _agent_search_service = SyncAgentSearchService()
        _agent_search_available = _agent_search_service.available
        if _agent_search_available:
            print("    [INIT] Agent SDK 搜索已就绪")
        else:
            print("    [INIT] Agent SDK 搜索不可用 (缺少 ANTHROPIC_API_KEY 或 SDK)")
        return _agent_search_available
    except ImportError:
        _agent_search_available = False
        return False


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
# 按贴敷式胰岛素泵9大生命周期阶段组织
DOC_CHAPTERS = {
    # ================= 一、设计策划阶段 =================
    "design_development_plan": [
        {"id": "ch1", "name": "目的和范围", "query": "设计开发计划 目的 范围 产品描述 贴敷式胰岛素泵"},
        {"id": "ch2", "name": "设计开发阶段划分", "query": "设计开发阶段 阶段划分 里程碑 软件C级 无菌器械"},
        {"id": "ch3", "name": "职责分配", "query": "设计开发职责 人员分配 资质要求 项目组织"},
        {"id": "ch4", "name": "设计开发活动安排", "query": "设计评审 设计验证 设计确认 时间安排 资源配置"},
        {"id": "ch5", "name": "技术资源配置", "query": "设备 软件工具 标准 法规 外部资源 测试设备"},
        {"id": "ch6", "name": "设计变更管理", "query": "设计变更 控制流程 审批权限 追溯性"},
    ],
    "product_requirements_spec": [
        {"id": "ch1", "name": "产品概述", "query": "贴敷式胰岛素泵 产品概述 预期用途 适用范围"},
        {"id": "ch2", "name": "功能需求", "query": "功能需求 输注模式 闭环控制 CGM联动 报警功能"},
        {"id": "ch3", "name": "性能需求", "query": "性能需求 输注精度 流量稳定性 阻塞检测 电池续航"},
        {"id": "ch4", "name": "安全需求", "query": "安全需求 故障检测 冗余设计 安全状态 电气安全"},
        {"id": "ch5", "name": "使用环境需求", "query": "使用环境 家庭护理 温度 湿度 防水 电磁环境"},
        {"id": "ch6", "name": "法规和标准需求", "query": "法规标准 GB9706 ISO13485 IEC62304 注册要求"},
    ],
    "risk_management_plan": [
        {"id": "ch1", "name": "目的和范围", "query": "风险管理目的 范围 适用性 ISO14971"},
        {"id": "ch2", "name": "产品描述", "query": "贴敷式胰岛素泵 结构组成 技术参数 工作原理"},
        {"id": "ch3", "name": "人员资格和职责", "query": "人员资格 职责分配 风险管理团队"},
        {"id": "ch4", "name": "风险可接受性准则", "query": "风险可接受准则 严重度 频度数 探测度 评分标准"},
        {"id": "ch5", "name": "风险管理活动计划", "query": "风险管理活动 FMEA FTA 计划时间表 评审安排"},
        {"id": "ch6", "name": "生产和生产后信息收集", "query": "生产后信息 投诉 不良事件 文献 信息收集方案"},
    ],
    "software_development_plan": [
        {"id": "ch1", "name": "目的和范围", "query": "软件计划 目的范围 IEC62304 安全等级C"},
        {"id": "ch2", "name": "软件开发生命周期模型", "query": "生命周期模型 V模型 敏捷 阶段划分"},
        {"id": "ch3", "name": "软件配置管理", "query": "配置管理 版本控制 基线管理 工具"},
        {"id": "ch4", "name": "软件验证计划", "query": "单元测试 集成测试 系统测试 验证策略"},
        {"id": "ch5", "name": "交付物清单", "query": "软件交付物 文档清单 IEC62304要求"},
    ],
    "usability_engineering_plan": [
        {"id": "ch1", "name": "目的和范围", "query": "可用性工程 目的范围 IEC62366 贴敷式胰岛素泵"},
        {"id": "ch2", "name": "用户画像和使用场景", "query": "用户画像 糖尿病患者 使用场景 家庭 外出 运动"},
        {"id": "ch3", "name": "关键任务识别", "query": "关键任务 贴敷 更换 剂量设定 报警响应"},
        {"id": "ch4", "name": "形成性评价计划", "query": "形成性评价 原型测试 认知走查 启发式评估"},
        {"id": "ch5", "name": "总结性评价计划", "query": "总结性评价 真实用户 模拟环境 任务完成率 错误率"},
    ],
    "biological_evaluation_plan": [
        {"id": "ch1", "name": "目的和范围", "query": "生物学评价 目的范围 ISO10993 接触性质"},
        {"id": "ch2", "name": "产品接触性质分析", "query": "皮肤接触 长期接触 输注管路 材料清单"},
        {"id": "ch3", "name": "试验项目确定", "query": "细胞毒性 刺激 致敏 血液相容性 试验项目"},
        {"id": "ch4", "name": "化学表征计划", "query": "化学表征 材料成分 溶出物 可沥滤物"},
        {"id": "ch5", "name": "评价时间表", "query": "时间安排 试验顺序 依赖关系"},
    ],
    "sterilization_validation_plan": [
        {"id": "ch1", "name": "目的和范围", "query": "灭菌验证 目的范围 EO灭菌 辐照灭菌 选择依据"},
        {"id": "ch2", "name": "灭菌方法选择", "query": "EO灭菌 辐照灭菌 材料兼容性 灭菌效果"},
        {"id": "ch3", "name": "验证策略", "query": "IQ OQ PQ 生物负载 灭菌周期开发"},
        {"id": "ch4", "name": "接受标准", "query": "SAL 10-6 生物指示剂 过程参数 残留限值"},
        {"id": "ch5", "name": "验证时间表", "query": "时间安排 资源 样品制备"},
    ],
    "packaging_validation_plan": [
        {"id": "ch1", "name": "目的和范围", "query": "包装验证 目的范围 ISO11607 无菌屏障"},
        {"id": "ch2", "name": "包装系统描述", "query": "初级包装 次级包装 运输包装 材料"},
        {"id": "ch3", "name": "验证测试项目", "query": "密封强度 完整性 运输模拟 老化测试"},
        {"id": "ch4", "name": "接受标准", "query": "密封强度限值 完整性标准 运输后完好率"},
        {"id": "ch5", "name": "验证时间表", "query": "时间安排 样品量 测试顺序"},
    ],
    "supplier_management_plan": [
        {"id": "ch1", "name": "目的和范围", "query": "供应商管理 目的范围 ISO13485 7.4"},
        {"id": "ch2", "name": "关键外购件识别", "query": "微电机 储药器 贴片胶带 电池 传感器 关键物料"},
        {"id": "ch3", "name": "供应商评价准则", "query": "评价准则 质量体系 生产能力 交付 价格"},
        {"id": "ch4", "name": "供应商审核计划", "query": "审核计划 审核频率 审核内容 审核报告"},
        {"id": "ch5", "name": "进货检验和绩效监控", "query": "进货检验 供应商绩效 不合格处理"},
    ],
    "regulatory_strategy_document": [
        {"id": "ch1", "name": "注册策略概述", "query": "注册策略 目标市场 NMPA FDA CE 注册路径选择"},
        {"id": "ch2", "name": "适用标准清单", "query": "适用标准 GB9706 ISO13485 IEC62304 标准清单"},
        {"id": "ch3", "name": "注册时间表", "query": "注册时间表 里程碑 关键节点 资料准备"},
        {"id": "ch4", "name": "UDI实施策略", "query": "UDI 器械标识 生产标识 赋码方案"},
        {"id": "ch5", "name": "风险和应对", "query": "注册风险 法规变更 测试失败 应对措施"},
    ],

    # ================= 二、设计输入阶段 =================
    "design_input": [
        {"id": "ch1", "name": "概述", "query": "设计输入 目的 范围 产品描述 贴敷式胰岛素泵"},
        {"id": "ch2", "name": "功能性能要求", "query": "功能要求 性能要求 输注精度 报警 通信 技术参数"},
        {"id": "ch3", "name": "法规标准要求", "query": "法规标准 强制标准 推荐标准 GB9706 ISO13485 IEC62304"},
        {"id": "ch4", "name": "风险管理要求", "query": "风险管理 风险控制措施 安全性要求 危害分析"},
        {"id": "ch5", "name": "使用环境要求", "query": "使用环境 家庭护理 温度 湿度 电磁 防水 跌落"},
        {"id": "ch6", "name": "设计输入评审", "query": "设计输入评审 评审记录 批准 可追溯性"},
    ],
    "software_requirements_spec": [
        {"id": "ch1", "name": "概述", "query": "软件需求 概述 IEC62304 安全等级C 贴敷式胰岛素泵"},
        {"id": "ch2", "name": "功能需求", "query": "输注控制 CGM联动 报警管理 数据记录 功能需求"},
        {"id": "ch3", "name": "性能需求", "query": "响应时间 数据精度 存储容量 处理速度"},
        {"id": "ch4", "name": "接口需求", "query": "BLE通信协议 App API 固件OTA 传感器接口"},
        {"id": "ch5", "name": "安全需求", "query": "故障检测 冗余校验 安全状态机 软件安全"},
        {"id": "ch6", "name": "软件需求评审", "query": "需求评审 可追溯性 验证方法"},
    ],
    "hardware_requirements_spec": [
        {"id": "ch1", "name": "概述", "query": "硬件需求 概述 系统架构 贴敷式胰岛素泵"},
        {"id": "ch2", "name": "电路设计需求", "query": "电机驱动 传感器接口 电源管理 MCU选型"},
        {"id": "ch3", "name": "机械结构需求", "query": "泵体尺寸 储药器接口 贴敷面设计 外壳材料"},
        {"id": "ch4", "name": "电池需求", "query": "电池容量 充放电管理 安全保护 续航时间"},
        {"id": "ch5", "name": "传感器需求", "query": "压力传感器 温度传感器 位置传感器 精度"},
    ],
    "ui_requirements_spec": [
        {"id": "ch1", "name": "概述", "query": "UI需求 概述 IEC62366 贴敷式胰岛素泵用户界面"},
        {"id": "ch2", "name": "设备端UI需求", "query": "LED指示 按钮操作 声音报警 振动反馈"},
        {"id": "ch3", "name": "App端UI需求", "query": "输注状态 剂量设定 报警信息 历史数据 图表"},
        {"id": "ch4", "name": "可访问性需求", "query": "视力障碍 老年人 大字体 高对比度 语音辅助"},
        {"id": "ch5", "name": "UI需求评审", "query": "UI评审 可用性 用户反馈"},
    ],
    "cybersecurity_requirements": [
        {"id": "ch1", "name": "概述", "query": "网络安全 概述 IEC81001 贴敷式胰岛素泵 无线通信"},
        {"id": "ch2", "name": "通信安全需求", "query": "BLE加密 数据完整性 中间人攻击防护 配对认证"},
        {"id": "ch3", "name": "数据安全需求", "query": "患者数据保护 存储加密 传输加密 访问控制"},
        {"id": "ch4", "name": "固件安全需求", "query": "固件签名校验 OTA安全更新 回滚保护 防篡改"},
        {"id": "ch5", "name": "安全事件响应需求", "query": "安全监控 漏洞管理 安全更新机制"},
    ],
    "labeling_ifu_requirements": [
        {"id": "ch1", "name": "概述", "query": "标签说明书需求 ISO20417 ISO15223 法规要求"},
        {"id": "ch2", "name": "标签符号需求", "query": "标签符号 灭菌标识 UDI 制造商信息 警告标识"},
        {"id": "ch3", "name": "说明书内容需求", "query": "适应症 禁忌症 使用步骤 警示 维护 技术参数"},
        {"id": "ch4", "name": "多语言需求", "query": "多语言 中文 英文 出口市场 翻译验证"},
    ],

    # ================= 三、设计输出阶段 =================
    "product_drawings": [
        {"id": "ch1", "name": "3D模型", "query": "3D模型 泵体 储药器 贴敷底座 装配关系"},
        {"id": "ch2", "name": "2D工程图", "query": "工程图 尺寸公差 GD&T 关键尺寸 装配图"},
        {"id": "ch3", "name": "材料标注", "query": "材料 表面处理 颜色 供应商 规格"},
        {"id": "ch4", "name": "图纸审批记录", "query": "审批 版本 变更记录"},
    ],
    "bill_of_materials": [
        {"id": "ch1", "name": "BOM结构", "query": "BOM 层次结构 成品 组件 零件 原材料"},
        {"id": "ch2", "name": "物料明细", "query": "物料编码 名称 规格 数量 供应商 关键物料"},
        {"id": "ch3", "name": "关键物料标识", "query": "安全件 法规件 关键特性 可追溯性"},
        {"id": "ch4", "name": "BOM审批和变更", "query": "BOM审批 版本管理 变更历史"},
    ],
    "product_specification": [
        {"id": "ch1", "name": "产品概述", "query": "贴敷式胰岛素泵 产品规格 概述"},
        {"id": "ch2", "name": "物理规格", "query": "尺寸 重量 材料 外观 颜色"},
        {"id": "ch3", "name": "性能规格", "query": "输注精度 流量范围 基础率 大剂量 精度"},
        {"id": "ch4", "name": "电气规格", "query": "电池容量 工作电压 功耗 充电参数"},
        {"id": "ch5", "name": "环境规格", "query": "工作温度 存储温度 湿度 防水等级 防护等级"},
    ],
    "software_architecture_doc": [
        {"id": "ch1", "name": "架构概述", "query": "软件架构 IEC62304 安全等级C 系统架构"},
        {"id": "ch2", "name": "模块划分", "query": "模块 组件 输注控制 CGM通信 报警管理 UI"},
        {"id": "ch3", "name": "接口定义", "query": "API 数据流 控制流 模块间通信"},
        {"id": "ch4", "name": "安全架构", "query": "故障隔离 冗余设计 安全监控 安全状态"},
        {"id": "ch5", "name": "部署架构", "query": "嵌入式固件 移动App 云服务 部署方案"},
    ],
    "software_detailed_design": [
        {"id": "ch1", "name": "设计概述", "query": "详细设计 IEC62304 模块设计 概述"},
        {"id": "ch2", "name": "核心算法设计", "query": "输注控制算法 CGM联动算法 报警决策 状态机"},
        {"id": "ch3", "name": "数据结构定义", "query": "数据结构 数据库 日志存储 配置数据"},
        {"id": "ch4", "name": "接口详细设计", "query": "API规范 通信协议 数据格式 时序"},
        {"id": "ch5", "name": "异常处理设计", "query": "异常处理 故障检测 恢复机制 降级模式"},
    ],
    "hardware_design_doc": [
        {"id": "ch1", "name": "设计概述", "query": "硬件设计 概述 系统框图 贴敷式胰岛素泵"},
        {"id": "ch2", "name": "电路原理图", "query": "原理图 电机驱动 电源管理 MCU 传感器接口"},
        {"id": "ch3", "name": "PCB设计", "query": "PCB布局 布线 叠层 电磁兼容设计"},
        {"id": "ch4", "name": "元器件选型", "query": "元器件选型 计算 关键参数 供应商"},
        {"id": "ch5", "name": "热设计", "query": "热设计 功耗预算 温升分析 散热方案"},
    ],
    "firmware_design_doc": [
        {"id": "ch1", "name": "固件架构", "query": "固件架构 RTOS 任务划分 中断处理"},
        {"id": "ch2", "name": "电机控制设计", "query": "步进电机 微步控制 PWM 位置反馈"},
        {"id": "ch3", "name": "传感器数据采集", "query": "压力传感器 温度传感器 信号调理 ADC"},
        {"id": "ch4", "name": "低功耗设计", "query": "低功耗 睡眠模式 唤醒机制 功耗优化"},
        {"id": "ch5", "name": "故障检测和安全", "query": "故障检测 看门狗 安全状态 错误处理"},
    ],
    "industrial_design_doc": [
        {"id": "ch1", "name": "外观设计", "query": "外观设计 壳体造型 轮廓 曲面 贴敷式胰岛素泵"},
        {"id": "ch2", "name": "CMF设计", "query": "颜色 材质 表面处理 医疗级材料"},
        {"id": "ch3", "name": "人因工程", "query": "贴敷舒适度 更换便利性 按键布局 指示灯"},
        {"id": "ch4", "name": "佩戴体验设计", "query": "人体工学 皮肤贴合 运动自由度 隐蔽性"},
    ],
    "label_nameplate_artwork": [
        {"id": "ch1", "name": "产品标签设计", "query": "标签 型号 批号 有效期 灭菌标识 UDI 符号"},
        {"id": "ch2", "name": "包装标签设计", "query": "包装标签 运输条件 存储条件 条码"},
        {"id": "ch3", "name": "法规符合性", "query": "ISO15223 NMPA FDA 标签法规 符号 格式"},
    ],
    "packaging_design_artwork": [
        {"id": "ch1", "name": "初级包装设计", "query": "无菌屏障 吸塑盒 涂胶盖材 密封设计"},
        {"id": "ch2", "name": "次级包装设计", "query": "彩盒 印刷内容 产品信息 品牌元素"},
        {"id": "ch3", "name": "运输包装设计", "query": "外箱 缓冲材料 堆码标识 运输标识"},
    ],
    "instruction_for_use": [
        {"id": "ch1", "name": "产品信息", "query": "贴敷式胰岛素泵 产品名称 型号 生产企业 结构组成"},
        {"id": "ch2", "name": "适用范围", "query": "适用范围 适应症 禁忌症 适用人群"},
        {"id": "ch3", "name": "使用步骤", "query": "贴敷步骤 储药器填充 启动 输注设定 更换 废弃"},
        {"id": "ch4", "name": "警示和注意事项", "query": "警示 警告 注意事项 并发症 不良事件"},
        {"id": "ch5", "name": "维护和故障排除", "query": "清洁 存储 故障现象 处理方法 客服联系"},
        {"id": "ch6", "name": "技术参数和符号", "query": "技术参数 符号说明 EMC 无线 电磁兼容说明"},
    ],
    "manufacturing_process_draft": [
        {"id": "ch1", "name": "组装工艺流程", "query": "组装流程 泵体组装 储药器组装 贴敷底座 工艺流程"},
        {"id": "ch2", "name": "调试和校准", "query": "输注精度校准 通信测试 功能检查 整机调试"},
        {"id": "ch3", "name": "包装工艺流程", "query": "内包 外包 灭菌前准备 包装工序"},
        {"id": "ch4", "name": "关键工艺参数", "query": "关键参数 控制范围 监控方法 工艺能力"},
    ],

    # ================= 四、设计验证阶段 =================
    "design_verification_master_plan": [
        {"id": "ch1", "name": "目的和范围", "query": "设计验证 总计划 ISO13485 贴敷式胰岛素泵"},
        {"id": "ch2", "name": "验证矩阵", "query": "验证项目 验证方法 接收标准 可追溯性矩阵"},
        {"id": "ch3", "name": "验证时间表", "query": "时间安排 资源 样品量 优先顺序"},
        {"id": "ch4", "name": "验证管理", "query": "职责分配 不符合项处理 报告模板 审批流程"},
    ],
    "electrical_safety_test_report": [
        {"id": "ch1", "name": "测试概述", "query": "电气安全 GB9706.1 测试目的 测试样品"},
        {"id": "ch2", "name": "测试项目和方法", "query": "耐压 漏电流 接地阻抗 温升 绝缘电阻"},
        {"id": "ch3", "name": "测试数据和结果", "query": "测试数据 限值 判定 充电模式 电池模式"},
        {"id": "ch4", "name": "结论", "query": "测试结论 符合性声明 不符合项"},
    ],
    "emc_test_report": [
        {"id": "ch1", "name": "测试概述", "query": "EMC测试 YY9706.102 测试目的 测试配置"},
        {"id": "ch2", "name": "发射测试", "query": "辐射发射 传导发射 限值 测试数据"},
        {"id": "ch3", "name": "抗扰度测试", "query": "ESD 辐射抗扰度 传导抗扰度 EFT 浪涌 测试数据"},
        {"id": "ch4", "name": "特殊考量", "query": "BLE通信 EMC考量 无线共存"},
        {"id": "ch5", "name": "结论", "query": "测试结论 符合性 不符合项"},
    ],
    "alarm_system_test_report": [
        {"id": "ch1", "name": "测试概述", "query": "报警测试 YY9706.108 报警系统 贴敷式胰岛素泵"},
        {"id": "ch2", "name": "报警优先级测试", "query": "高优先级 阻塞 低电量 中优先级 低优先级"},
        {"id": "ch3", "name": "声光特性测试", "query": "声压级 频率 脉冲模式 指示灯特性"},
        {"id": "ch4", "name": "智能报警测试", "query": "报警延迟 报警确认 报警升级 报警日志"},
        {"id": "ch5", "name": "结论", "query": "测试结论 符合性"},
    ],
    "infusion_accuracy_test_report": [
        {"id": "ch1", "name": "测试概述", "query": "输注精度 GB9706.224 测试目的 测试装置"},
        {"id": "ch2", "name": "基础率精度测试", "query": "基础率 不同速率 误差 流量 称重法"},
        {"id": "ch3", "name": "大剂量精度测试", "query": "Bolus 不同剂量 误差 重复性"},
        {"id": "ch4", "name": "阻塞检测测试", "query": "阻塞检测 响应时间 不同背压 报警触发"},
        {"id": "ch5", "name": "长期稳定性测试", "query": "长时间运行 输注一致性 温度影响"},
        {"id": "ch6", "name": "结论", "query": "精度结论 符合性 不确定度分析"},
    ],
    "software_unit_test_report": [
        {"id": "ch1", "name": "测试概述", "query": "单元测试 IEC62304 测试策略 测试环境"},
        {"id": "ch2", "name": "测试用例和结果", "query": "测试用例 测试数据 期望输出 实际结果"},
        {"id": "ch3", "name": "代码覆盖率", "query": "语句覆盖 分支覆盖 MC/DC 覆盖率统计"},
        {"id": "ch4", "name": "安全单元测试", "query": "安全相关单元 边界条件 异常输入 深度测试"},
        {"id": "ch5", "name": "结论", "query": "测试结论 未覆盖项 残留风险"},
    ],
    "software_integration_test_report": [
        {"id": "ch1", "name": "测试概述", "query": "集成测试 IEC62304 集成策略 测试环境"},
        {"id": "ch2", "name": "模块接口测试", "query": "接口测试 数据传输 时序 协议 正确性"},
        {"id": "ch3", "name": "软硬件集成测试", "query": "传感器读取 电机控制 通信协议栈 集成"},
        {"id": "ch4", "name": "回归测试", "query": "回归测试 变更影响 自动化测试"},
        {"id": "ch5", "name": "结论", "query": "集成测试结论 接口问题 解决方案"},
    ],
    "software_system_test_report": [
        {"id": "ch1", "name": "测试概述", "query": "系统测试 IEC62304 黑盒测试 测试环境"},
        {"id": "ch2", "name": "功能测试", "query": "功能测试 需求覆盖 可追溯性矩阵 测试结果"},
        {"id": "ch3", "name": "性能测试", "query": "响应时间 并发处理 长时间运行 性能数据"},
        {"id": "ch4", "name": "异常测试", "query": "异常条件 边界条件 压力测试 容错性"},
        {"id": "ch5", "name": "结论", "query": "系统测试结论 发布建议"},
    ],
    "battery_performance_test_report": [
        {"id": "ch1", "name": "测试概述", "query": "电池测试 IEC62133 UL1642 测试目的"},
        {"id": "ch2", "name": "续航测试", "query": "续航时间 不同模式 基础率 大剂量 蓝牙"},
        {"id": "ch3", "name": "充放电测试", "query": "充电循环 容量衰减 充电效率 放电特性"},
        {"id": "ch4", "name": "安全测试", "query": "过充 过放 短路 高温 安全保护"},
        {"id": "ch5", "name": "低电量测试", "query": "低电量报警 自动关机 数据保存"},
        {"id": "ch6", "name": "结论", "query": "电池测试结论 寿命预估"},
    ],
    "ip_rating_test_report": [
        {"id": "ch1", "name": "测试概述", "query": "IP防护 IEC60529 防水防尘 测试条件"},
        {"id": "ch2", "name": "测试执行", "query": "测试方法 测试装置 持续时间 试验过程"},
        {"id": "ch3", "name": "测试结果", "query": "进水检查 功能检查 外观检查 测试数据"},
        {"id": "ch4", "name": "结论", "query": "IP等级结论 符合性"},
    ],
    "environmental_reliability_test": [
        {"id": "ch1", "name": "测试概述", "query": "环境试验 GB/T14710 测试目的 测试项目"},
        {"id": "ch2", "name": "气候环境测试", "query": "低温 高温 湿热 温度循环 温度冲击"},
        {"id": "ch3", "name": "机械环境测试", "query": "振动 跌落 冲击 碰撞"},
        {"id": "ch4", "name": "测试结果汇总", "query": "测试前后对比 功能检查 外观检查"},
        {"id": "ch5", "name": "结论", "query": "环境可靠性结论"},
    ],
    "package_transport_test_report": [
        {"id": "ch1", "name": "测试概述", "query": "运输包装 GB/T4857 ASTM D4169 测试方案"},
        {"id": "ch2", "name": "跌落测试", "query": "自由跌落 不同高度 不同方向 角 棱 面"},
        {"id": "ch3", "name": "堆码和振动测试", "query": "堆码 压缩 随机振动 正弦振动"},
        {"id": "ch4", "name": "测试后检查", "query": "包装完整性 产品功能 外观 密封"},
        {"id": "ch5", "name": "结论", "query": "运输包装结论"},
    ],
    "seal_integrity_test_report": [
        {"id": "ch1", "name": "测试概述", "query": "密封完整性 ISO11607 YY/T0681 测试目的"},
        {"id": "ch2", "name": "物理测试", "query": "染色渗透 爆破强度 拉伸测试"},
        {"id": "ch3", "name": "无损测试", "query": "真空衰减 压力衰减 目视检查"},
        {"id": "ch4", "name": "灭菌前后对比", "query": "灭菌前 灭菌后 老化后 密封对比"},
        {"id": "ch5", "name": "结论", "query": "密封完整性结论 接受标准"},
    ],
    "material_characterization_report": [
        {"id": "ch1", "name": "测试概述", "query": "材料表征 ISO10993-18 测试目的 材料清单"},
        {"id": "ch2", "name": "物理特性", "query": "拉伸强度 硬度 密度 熔融指数"},
        {"id": "ch3", "name": "化学特性", "query": "成分分析 溶出物 可沥滤物 残留单体"},
        {"id": "ch4", "name": "特殊材料测试", "query": "贴片胶带 粘性 透气性 皮肤相容性"},
        {"id": "ch5", "name": "结论", "query": "材料表征结论 毒理学评估"},
    ],
    "accelerated_aging_test_report": [
        {"id": "ch1", "name": "测试概述", "query": "加速老化 ASTM F1980 YY/T0681.1 老化方案"},
        {"id": "ch2", "name": "老化条件", "query": "温度 湿度 时间 加速因子 Q10"},
        {"id": "ch3", "name": "老化后性能测试", "query": "输注精度 密封完整性 电池 外观 功能"},
        {"id": "ch4", "name": "有效期确定", "query": "有效期结论 安全系数 实时老化关联"},
        {"id": "ch5", "name": "结论", "query": "加速老化结论"},
    ],
    "sensor_calibration_validation": [
        {"id": "ch1", "name": "验证概述", "query": "传感器校准 压力传感器 位置传感器 温度传感器"},
        {"id": "ch2", "name": "校准方法", "query": "校准方法 标准器 校准环境 校准频率"},
        {"id": "ch3", "name": "校准数据", "query": "校准曲线 线性度 重复性 迟滞 漂移"},
        {"id": "ch4", "name": "结论", "query": "校准验证结论 不确定度"},
    ],
    "cybersecurity_test_report": [
        {"id": "ch1", "name": "测试概述", "query": "网络安全测试 IEC81001 测试范围 测试方法"},
        {"id": "ch2", "name": "渗透测试", "query": "BLE渗透 App渗透 固件渗透 渗透结果"},
        {"id": "ch3", "name": "加密验证", "query": "通信加密 存储加密 密钥管理 证书"},
        {"id": "ch4", "name": "固件安全测试", "query": "固件签名 防篡改 安全启动 OTA安全"},
        {"id": "ch5", "name": "漏洞评估", "query": "漏洞扫描 风险评估 缓解措施 残留风险"},
        {"id": "ch6", "name": "结论", "query": "网络安全测试结论"},
    ],

    # ================= 五、设计确认阶段 =================
    "design_validation_master_plan": [
        {"id": "ch1", "name": "目的和范围", "query": "设计确认 总计划 ISO13485 确认活动总览"},
        {"id": "ch2", "name": "可用性确认计划", "query": "可用性 总结性评价 真实用户 模拟场景"},
        {"id": "ch3", "name": "临床确认计划", "query": "临床评价 临床试验 CER 临床数据"},
        {"id": "ch4", "name": "生物学和灭菌确认", "query": "生物学评价 灭菌确认 SAL 残留"},
        {"id": "ch5", "name": "确认时间表", "query": "时间安排 资源 依赖关系"},
    ],
    "summative_usability_report": [
        {"id": "ch1", "name": "报告概述", "query": "总结性可用性 IEC62366 测试目的 测试场景"},
        {"id": "ch2", "name": "测试方法", "query": "参与者 测试场景 任务列表 数据收集"},
        {"id": "ch3", "name": "测试结果", "query": "任务完成率 错误率 时间 满意度 根本原因"},
        {"id": "ch4", "name": "分析和改进", "query": "使用错误分析 设计改进 人因工程"},
        {"id": "ch5", "name": "结论", "query": "可用性结论 安全性 有效性"},
    ],
    "clinical_evaluation_report": [
        {"id": "ch1", "name": "评价概述", "query": "临床评价 MEDDEV ISO14155 评价范围"},
        {"id": "ch2", "name": "文献检索和评价", "query": "文献检索策略 文献筛选 质量评价 数据提取"},
        {"id": "ch3", "name": "临床数据分析", "query": "安全性 有效性 性能 等效器械对比"},
        {"id": "ch4", "name": "受益-风险评价", "query": "受益评估 风险评估 综合结论"},
        {"id": "ch5", "name": "上市后要求", "query": "PMCF计划 数据缺口 后续研究"},
        {"id": "ch6", "name": "结论", "query": "临床评价结论 符合性声明"},
    ],
    "biological_evaluation_report": [
        {"id": "ch1", "name": "评价概述", "query": "生物学评价 ISO10993-1 接触性质 材料清单"},
        {"id": "ch2", "name": "化学表征总结", "query": "材料成分 溶出物 可沥滤物 化学表征"},
        {"id": "ch3", "name": "生物学试验总结", "query": "细胞毒性 刺激 致敏 血液相容性 试验结果"},
        {"id": "ch4", "name": "毒理学评估", "query": "毒理学 安全限值 暴露量 风险评估"},
        {"id": "ch5", "name": "结论", "query": "生物学评价结论 生物学安全性"},
    ],
    "cytotoxicity_test_report": [
        {"id": "ch1", "name": "测试概述", "query": "细胞毒性 ISO10993-5 试验目的 材料"},
        {"id": "ch2", "name": "试验方法", "query": "浸提液制备 细胞系 培养条件 评价方法"},
        {"id": "ch3", "name": "试验结果", "query": "定性结果 定量结果 细胞活力 形态"},
        {"id": "ch4", "name": "结论", "query": "细胞毒性结论 符合性"},
    ],
    "skin_irritation_sensitization": [
        {"id": "ch1", "name": "测试概述", "query": "皮肤刺激 致敏 ISO10993-10 测试目的"},
        {"id": "ch2", "name": "皮肤刺激试验", "query": "刺激试验 方法 动物模型 评分系统 结果"},
        {"id": "ch3", "name": "致敏试验", "query": "致敏试验 GPMT LLNA 方法 结果"},
        {"id": "ch4", "name": "结论", "query": "皮肤刺激和致敏结论"},
    ],
    "blood_compatibility_test_report": [
        {"id": "ch1", "name": "测试概述", "query": "血液相容性 ISO10993-4 测试目的 适用性"},
        {"id": "ch2", "name": "溶血试验", "query": "溶血率 直接接触 间接接触 试验结果"},
        {"id": "ch3", "name": "凝血试验", "query": "PTT PT 凝血激活 血小板激活"},
        {"id": "ch4", "name": "结论", "query": "血液相容性结论"},
    ],
    "sal_validation_report": [
        {"id": "ch1", "name": "验证概述", "query": "SAL验证 ISO11135 ISO11137 灭菌方法"},
        {"id": "ch2", "name": "IQ/OQ", "query": "安装确认 运行确认 设备验证"},
        {"id": "ch3", "name": "PQ", "query": "性能确认 生物负载 半周期法 SAL 10-6"},
        {"id": "ch4", "name": "结论", "query": "SAL验证结论 灭菌保证水平"},
    ],
    "sterilization_residue_test_report": [
        {"id": "ch1", "name": "测试概述", "query": "灭菌残留 ISO10993-7 EO残留 残留测试"},
        {"id": "ch2", "name": "EO残留测试", "query": "EO残留 ECH残留 测试方法 气相色谱"},
        {"id": "ch3", "name": "残留限值评估", "query": "安全限值 ISO10993-7 暴露评估"},
        {"id": "ch4", "name": "结论", "query": "残留测试结论"},
    ],
    "process_validation_iq_oq_pq": [
        {"id": "ch1", "name": "验证概述", "query": "过程确认 IQ OQ PQ 关键工艺"},
        {"id": "ch2", "name": "安装确认(IQ)", "query": "设备安装 校准 文件 公用设施"},
        {"id": "ch3", "name": "运行确认(OQ)", "query": "工艺参数 操作范围 挑战测试 最差条件"},
        {"id": "ch4", "name": "性能确认(PQ)", "query": "连续批次 一致性 能力指数 稳定性"},
        {"id": "ch5", "name": "结论", "query": "过程确认结论"},
    ],
    "cleaning_validation_report": [
        {"id": "ch1", "name": "验证概述", "query": "清洗验证 ISO15883 清洗目的"},
        {"id": "ch2", "name": "清洗工艺", "query": "清洗剂 温度 时间 方式 参数"},
        {"id": "ch3", "name": "验证结果", "query": "残留限值 粒子计数 微生物 内毒素"},
        {"id": "ch4", "name": "结论", "query": "清洗验证结论"},
    ],

    # ================= 六、设计转化阶段 =================
    "design_transfer_plan": [
        {"id": "ch1", "name": "目的和范围", "query": "设计转化 ISO13485 7.3.8 转化计划"},
        {"id": "ch2", "name": "交接条件", "query": "交接条件 检查清单 研发输出 生产接收"},
        {"id": "ch3", "name": "人员培训", "query": "培训计划 培训内容 考核 人员资质"},
        {"id": "ch4", "name": "设备和工装", "query": "生产设备 工装 模具 检验设备 采购"},
        {"id": "ch5", "name": "供应商准备", "query": "供应商确认 物料准备 首批供应"},
    ],
    "design_transfer_report": [
        {"id": "ch1", "name": "转化概述", "query": "设计转化 报告 转化过程 时间节点"},
        {"id": "ch2", "name": "输出转化确认", "query": "图纸 BOM 工艺文件 检验规范 转化确认"},
        {"id": "ch3", "name": "过程验证状态", "query": "IQ OQ PQ 验证状态 工艺能力"},
        {"id": "ch4", "name": "首批生产评估", "query": "首批生产 良率 问题 改进"},
        {"id": "ch5", "name": "结论", "query": "设计转化结论 审批"},
    ],
    "device_master_record": [
        {"id": "ch1", "name": "DMR概述", "query": "DMR ISO13485 4.2.3 产品主记录"},
        {"id": "ch2", "name": "产品规范", "query": "规格书 图纸 BOM 标签 包装规范"},
        {"id": "ch3", "name": "生产工艺规范", "query": "组装SOP 包装SOP 灭菌规范 工艺参数"},
        {"id": "ch4", "name": "检验规范", "query": "进货检验 过程检验 成品检验 接收标准"},
        {"id": "ch5", "name": "版本管理", "query": "版本 变更历史 分发控制"},
    ],
    "manufacturing_sop": [
        {"id": "ch1", "name": "目的和范围", "query": "生产工艺SOP 目的 范围 引用文件"},
        {"id": "ch2", "name": "职责和资质", "query": "职责 岗位 资质要求 培训要求"},
        {"id": "ch3", "name": "组装操作步骤", "query": "组装 泵体 储药器 电池 贴敷底座 操作步骤"},
        {"id": "ch4", "name": "灌装和灭菌准备", "query": "灌装 灭菌前准备 装载 参数设置"},
        {"id": "ch5", "name": "质量控制点", "query": "关键控制点 检查项目 参数监控 记录"},
        {"id": "ch6", "name": "安全注意事项", "query": "安全 个人防护 设备安全 环境安全"},
    ],
    "inspection_sop": [
        {"id": "ch1", "name": "目的和范围", "query": "检验SOP 目的 范围 引用标准"},
        {"id": "ch2", "name": "进货检验", "query": "电机 传感器 储药器 胶带 电池 检验项目 抽样"},
        {"id": "ch3", "name": "过程检验", "query": "组装检验 功能测试 通信测试 外观检查"},
        {"id": "ch4", "name": "成品检验", "query": "最终性能 输注精度 密封 包装 标签 接收标准"},
        {"id": "ch5", "name": "检验设备和记录", "query": "检验设备 校准 记录表单 填写要求"},
    ],
    "equipment_operation_procedures": [
        {"id": "ch1", "name": "概述", "query": "设备操作规程 范围 适用设备"},
        {"id": "ch2", "name": "生产设备操作", "query": "点胶机 焊接 组装工装 操作步骤 维护"},
        {"id": "ch3", "name": "检验设备操作", "query": "流量测试台 拉力机 泄漏仪 操作步骤 校准"},
        {"id": "ch4", "name": "安全操作", "query": "安全操作 紧急停机 防护 事故处理"},
    ],
    "work_environment_control_doc": [
        {"id": "ch1", "name": "目的和范围", "query": "工作环境 ISO13485 6.4 洁净室 控制"},
        {"id": "ch2", "name": "洁净室管理", "query": "洁净室 级别 温湿度 压差 粒子数 微生物"},
        {"id": "ch3", "name": "ESD控制", "query": "ESD 接地 电离器 腕带 服装"},
        {"id": "ch4", "name": "人员卫生", "query": "更衣 洗手 健康 行为规范"},
        {"id": "ch5", "name": "监测记录", "query": "环境监测 频率 方法 记录 超标处理"},
    ],

    # ================= 七、生产制造阶段 =================
    "batch_production_record": [
        {"id": "ch1", "name": "批次信息", "query": "批次 批号 生产日期 产量 操作人员"},
        {"id": "ch2", "name": "工序操作记录", "query": "组装 灌装 包装 各工序 操作记录 参数"},
        {"id": "ch3", "name": "物料使用记录", "query": "物料编码 批号 用量 追溯"},
        {"id": "ch4", "name": "设备和偏差记录", "query": "设备编号 运行参数 偏差 异常处理"},
    ],
    "batch_inspection_record": [
        {"id": "ch1", "name": "批次信息", "query": "批次 批号 检验日期 检验人员"},
        {"id": "ch2", "name": "进货检验", "query": "原材料 外购件 检验项目 数据 判定"},
        {"id": "ch3", "name": "过程检验", "query": "各工序 检验数据 判定"},
        {"id": "ch4", "name": "成品检验", "query": "性能 外观 包装 检验数据 最终判定"},
    ],
    "device_history_record": [
        {"id": "ch1", "name": "DHR概述", "query": "DHR ISO13485 4.2.5 批次汇总"},
        {"id": "ch2", "name": "生产记录汇总", "query": "BPR 关键工序 参数 操作人"},
        {"id": "ch3", "name": "检验记录汇总", "query": "进货 过程 成品 检验结果 判定"},
        {"id": "ch4", "name": "灭菌和UDI", "query": "灭菌记录 UDI清单 放行批准"},
    ],
    "incoming_inspection_records": [
        {"id": "ch1", "name": "记录概述", "query": "进货检验 记录 检验计划 抽样方案"},
        {"id": "ch2", "name": "检验记录明细", "query": "物料 批次 检验项目 数据 接收标准 判定"},
        {"id": "ch3", "name": "不合格品处理", "query": "不合格物料 数量 处理方式 供方通知"},
    ],
    "supplier_audit_reports": [
        {"id": "ch1", "name": "审核概述", "query": "供应商审核 目的 范围 审核组 审核计划"},
        {"id": "ch2", "name": "审核发现", "query": "检查表 符合项 不符合项 观察项 证据"},
        {"id": "ch3", "name": "审核结论", "query": "审核结论 供应商评级 整改要求 跟进"},
    ],
    "calibration_records": [
        {"id": "ch1", "name": "校准计划", "query": "校准计划 设备清单 校准周期 责任"},
        {"id": "ch2", "name": "校准证书", "query": "校准结果 不确定度 有效期 标准器"},
        {"id": "ch3", "name": "不合格处理", "query": "校准不合格 追溯 影响评估 纠正措施"},
    ],
    "environmental_monitoring_records": [
        {"id": "ch1", "name": "监测计划", "query": "环境监测 计划 频率 监测点 项目"},
        {"id": "ch2", "name": "监测数据", "query": "温度 湿度 压差 粒子 微生物 数据记录"},
        {"id": "ch3", "name": "超标处理", "query": "超标 调查 纠正措施 再监测"},
    ],
    "nonconforming_product_records": [
        {"id": "ch1", "name": "不合格品记录", "query": "不合格品 描述 发现 数量 位置 时间"},
        {"id": "ch2", "name": "评审和处置", "query": "评审结论 让步 返工 报废 处置 责任人"},
        {"id": "ch3", "name": "根本原因和CAPA", "query": "根本原因 纠正措施 预防措施 验证"},
    ],
    "sterilization_process_records": [
        {"id": "ch1", "name": "灭菌批次记录", "query": "灭菌批次 产品批号 灭菌日期 操作人员"},
        {"id": "ch2", "name": "灭菌参数", "query": "温度 EO浓度 时间 湿度 压力 剂量"},
        {"id": "ch3", "name": "指示剂结果", "query": "生物指示剂 化学指示剂 结果 判定"},
        {"id": "ch4", "name": "放行", "query": "灭菌放行 参数审核 批准"},
    ],
    "udi_assignment_records": [
        {"id": "ch1", "name": "UDI概述", "query": "UDI 赋码 YY/T1630 方案"},
        {"id": "ch2", "name": "UDI分配记录", "query": "UDI-DI UDI-PI 批次对应 码值"},
        {"id": "ch3", "name": "赋码质量", "query": "条码 二维码 打印质量 校验 抽查"},
    ],

    # ================= 八、注册申报阶段 =================
    "registration_dossier": [
        {"id": "ch1", "name": "注册申请概述", "query": "注册申请 产品 申请人 注册类型 III类"},
        {"id": "ch2", "name": "产品描述", "query": "贴敷式胰岛素泵 结构组成 原理 规格型号"},
        {"id": "ch3", "name": "性能和安全评价", "query": "性能指标 安全性 风险管理 验证确认"},
        {"id": "ch4", "name": "临床评价资料", "query": "临床评价 CER 临床试验 文献"},
        {"id": "ch5", "name": "质量体系文件", "query": "QMS 体系证明 生产许可证"},
        {"id": "ch6", "name": "标签和说明书", "query": "标签 说明书 IFU 符合性声明"},
    ],
    "product_technical_requirements": [
        {"id": "ch1", "name": "型号规格", "query": "型号 规格 结构组成 贴敷式胰岛素泵"},
        {"id": "ch2", "name": "性能指标", "query": "输注精度 报警 防水 通信 电气安全 性能指标"},
        {"id": "ch3", "name": "检验方法", "query": "检验方法 仪器 步骤 判定"},
        {"id": "ch4", "name": "标志包装运输贮存", "query": "标志 标签 包装 运输条件 贮存条件"},
    ],
    "risk_management_report": [
        {"id": "ch1", "name": "概述", "query": "贴敷式胰岛素泵 风险管理 概述 ISO14971"},
        {"id": "ch2", "name": "风险分析", "query": "危害识别 风险分析 安全性特征 贴敷式胰岛素泵"},
        {"id": "ch3", "name": "风险评价", "query": "风险评价 RPN 严重度 频度数 探测度"},
        {"id": "ch4", "name": "风险控制", "query": "风险控制措施 验证 实施"},
        {"id": "ch5", "name": "综合剩余风险评价", "query": "剩余风险 综合评价 受益-风险"},
        {"id": "ch6", "name": "风险管理评审结论", "query": "评审结论 批准 文档"},
    ],
    "essential_safety_conformity": [
        {"id": "ch1", "name": "声明概述", "query": "基本安全 基本性能 符合性声明 GB9706.1"},
        {"id": "ch2", "name": "逐条符合性检查", "query": "条款 要求 符合性 证据 说明"},
        {"id": "ch3", "name": "不适用条款说明", "query": "不适用条款 理由 合理性"},
        {"id": "ch4", "name": "结论", "query": "符合性结论 声明"},
    ],
    "software_version_description": [
        {"id": "ch1", "name": "版本概述", "query": "软件版本 版本号 发布日期 平台"},
        {"id": "ch2", "name": "版本内容", "query": "功能 变更 修复 新增"},
        {"id": "ch3", "name": "已知问题和限制", "query": "已知问题 限制 使用注意"},
        {"id": "ch4", "name": "软件配置清单", "query": "组件 版本 依赖 配置"},
    ],
    "cybersecurity_disclosure": [
        {"id": "ch1", "name": "概述", "query": "网络安全 披露 范围 设备描述"},
        {"id": "ch2", "name": "风险管理总结", "query": "威胁模型 风险评估 漏洞 缓解"},
        {"id": "ch3", "name": "安全更新策略", "query": "补丁管理 更新机制 验证"},
        {"id": "ch4", "name": "结论", "query": "网络安全结论 符合性"},
    ],
    "clinical_evaluation_report_reg": [
        {"id": "ch1", "name": "评价概述", "query": "临床评价 注册 MEDDEV 评价范围"},
        {"id": "ch2", "name": "文献和临床数据", "query": "文献检索 临床数据 等效器械"},
        {"id": "ch3", "name": "受益-风险评价", "query": "受益 风险 综合评价"},
        {"id": "ch4", "name": "结论", "query": "临床评价结论 安全性 有效性"},
    ],
    "ifu_labeling_for_registration": [
        {"id": "ch1", "name": "说明书审核稿", "query": "说明书 内容 使用步骤 警示 符号"},
        {"id": "ch2", "name": "标签审核稿", "query": "标签 UDI 灭菌标识 法规符号"},
        {"id": "ch3", "name": "法规符合性", "query": "NMPA FDA CE 符合性 多语言"},
    ],
    "declaration_of_conformity": [
        {"id": "ch1", "name": "声明信息", "query": "DoC EU MDR 制造商 产品 公告机构"},
        {"id": "ch2", "name": "符合的法规标准", "query": "法规 标准 清单 符合性"},
        {"id": "ch3", "name": "签署", "query": "签署人 职位 日期 签名"},
    ],
    "qms_certificate_proof": [
        {"id": "ch1", "name": "体系证书", "query": "ISO13485 证书 范围 有效期 认证机构"},
        {"id": "ch2", "name": "GMP证明", "query": "GMP检查 通过证明 检查日期"},
        {"id": "ch3", "name": "其他证书", "query": "MDSAP CE 其他体系认证"},
    ],

    # ================= 九、上市后阶段 =================
    "pms_plan": [
        {"id": "ch1", "name": "目的和范围", "query": "PMS Plan EU MDR Art.84 ISO TR 20416"},
        {"id": "ch2", "name": "数据收集方法", "query": "投诉 不良事件 文献 注册数据 社交媒体 数据源"},
        {"id": "ch3", "name": "数据分析和评价", "query": "数据分析 趋势 统计方法 评价准则"},
        {"id": "ch4", "name": "报告机制", "query": "PMS报告 编制周期 触发条件 分发"},
    ],
    "pmcf_plan": [
        {"id": "ch1", "name": "目的和范围", "query": "PMCF Plan EU MDR Annex XIV 临床跟踪"},
        {"id": "ch2", "name": "数据缺口识别", "query": "上市前 临床数据 不足 缺口 待补充"},
        {"id": "ch3", "name": "PMCF活动设计", "query": "临床研究 问卷 文献 注册数据 活动设计"},
        {"id": "ch4", "name": "时间表和职责", "query": "时间表 责任人 里程碑"},
    ],
    "complaint_handling_records": [
        {"id": "ch1", "name": "投诉登记", "query": "投诉人 产品信息 问题描述 日期 批号"},
        {"id": "ch2", "name": "调查过程", "query": "原因分析 检测 批次追溯 调查结论"},
        {"id": "ch3", "name": "回复和纠正", "query": "回复 纠正措施 监管报告 关闭"},
    ],
    "adverse_event_reports": [
        {"id": "ch1", "name": "不良事件描述", "query": "不良事件 类型 严重程度 器械关联性"},
        {"id": "ch2", "name": "产品信息", "query": "型号 批号 UDI 使用情况"},
        {"id": "ch3", "name": "处理措施", "query": "纠正措施 监管报告 时间表 跟踪"},
    ],
    "periodic_safety_update_report": [
        {"id": "ch1", "name": "报告概述", "query": "PSUR EU MDR Art.86 报告期 范围"},
        {"id": "ch2", "name": "安全性数据汇总", "query": "不良事件 投诉 文献 趋势 分析"},
        {"id": "ch3", "name": "受益-风险更新", "query": "受益 风险 综合评价 更新"},
        {"id": "ch4", "name": "结论和行动", "query": "问题识别 建议 行动 与既往比较"},
    ],
    "capa_records": [
        {"id": "ch1", "name": "CAPA来源", "query": "CAPA来源 投诉 不合格 审核 管理评审"},
        {"id": "ch2", "name": "根本原因分析", "query": "根本原因 5Why 鱼骨图 因果分析"},
        {"id": "ch3", "name": "纠正和预防措施", "query": "纠正措施 预防措施 实施计划 责任人"},
        {"id": "ch4", "name": "有效性验证", "query": "有效性验证 验证方法 验证结果"},
        {"id": "ch5", "name": "CAPA关闭", "query": "CAPA关闭 批准 日期 归档"},
    ],
    "change_control_records": [
        {"id": "ch1", "name": "变更描述", "query": "变更 描述 原因 变更前后状态"},
        {"id": "ch2", "name": "影响评估", "query": "安全 性能 法规 影响 风险评估"},
        {"id": "ch3", "name": "变更验证", "query": "验证 确认 测试 文档更新"},
        {"id": "ch4", "name": "审批和实施", "query": "审批 实施 追溯 变更通知"},
    ],
    "recall_field_safety_notice": [
        {"id": "ch1", "name": "召回决策", "query": "召回 决策 风险 等级 受影响 范围"},
        {"id": "ch2", "name": "召回行动计划", "query": "通知方式 回收流程 时间计划"},
        {"id": "ch3", "name": "监管报告", "query": "监管机构 报告 NMPA FDA 报告内容"},
        {"id": "ch4", "name": "召回归档", "query": "召回效果 评估 关闭 报告"},
    ],
    "management_review_report": [
        {"id": "ch1", "name": "评审概述", "query": "管理评审 ISO13485 5.6 评审周期"},
        {"id": "ch2", "name": "评审输入", "query": "质量目标 审核 CAPA 投诉 变更 改进"},
        {"id": "ch3", "name": "评审输出", "query": "改进措施 资源需求 质量方针修订"},
        {"id": "ch4", "name": "评审结论", "query": "体系有效性 适宜性 充分性 结论"},
    ],
    "internal_audit_reports": [
        {"id": "ch1", "name": "审核概述", "query": "内部审核 ISO13485 8.2.4 审核计划"},
        {"id": "ch2", "name": "审核发现", "query": "符合项 不符合项 观察项 改进机会"},
        {"id": "ch3", "name": "审核结论", "query": "体系有效性 不符合项 纠正措施 跟踪"},
    ],
    "pms_report": [
        {"id": "ch1", "name": "报告概述", "query": "PMS Report EU MDR Art.85 报告期"},
        {"id": "ch2", "name": "数据汇总和分析", "query": "PMS数据 汇总 趋势 统计 分析"},
        {"id": "ch3", "name": "受益-风险结论", "query": "受益 风险 综合评价 更新"},
        {"id": "ch4", "name": "后续行动", "query": "发现 建议 后续行动"},
    ],

    # ================= 保留原有兼容类型 =================
    "fmea_analysis": [
        {"id": "ch1", "name": "FMEA概述", "query": "FMEA概述 目的 范围 方法 贴敷式胰岛素泵"},
        {"id": "ch2", "name": "严重度频度数探测度评价准则", "query": "严重度 频度数 探测度 评价准则 评分标准"},
        {"id": "ch3", "name": "FMEA分析表", "query": "FMEA分析表 失效模式 失效效应 子系统"},
        {"id": "ch4", "name": "高风险项目改进措施", "query": "高风险 改进措施 RPN 降低 验证"},
        {"id": "ch5", "name": "FMEA分析结论", "query": "FMEA结论 风险 可接受性 建议"},
    ],
    "design_output": [
        {"id": "ch1", "name": "概述", "query": "设计输出 目的 范围 概述 ISO13485"},
        {"id": "ch2", "name": "产品图纸和规范", "query": "图纸 规范 技术文档 物料清单 BOM"},
        {"id": "ch3", "name": "生产工艺文件", "query": "生产工艺 作业指导书 SOP 检验规程"},
        {"id": "ch4", "name": "包装和标识规范", "query": "包装规范 标识 标签 IFU"},
        {"id": "ch5", "name": "设计输出评审", "query": "设计输出评审 评审记录 批准 可追溯"},
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
        {"id": "ch2", "name": "临床评价", "query": "临床评价 临床试验 临床数据 CER"},
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
    "risk_acceptance_criteria": [
        {"id": "ch1", "name": "概述", "query": "风险可接受准则 ISO14971 概述 范围"},
        {"id": "ch2", "name": "评分标准", "query": "严重度 频度数 探测度 评分标准 定义"},
        {"id": "ch3", "name": "RPN阈值", "query": "RPN 阈值 设定 依据"},
        {"id": "ch4", "name": "风险处理原则", "query": "风险等级 处理 原则 接受 控制 转移"},
        {"id": "ch5", "name": "批准", "query": "准则批准 审批 记录"},
    ],
    "periodic_risk_evaluation": [
        {"id": "ch1", "name": "概述", "query": "定期风险评价 目的 范围 评价周期"},
        {"id": "ch2", "name": "风险信息汇总", "query": "投诉 不良事件 文献 新的危害"},
        {"id": "ch3", "name": "风险再评价", "query": "新风险识别 已识别风险 再评价"},
        {"id": "ch4", "name": "控制措施有效性", "query": "风险控制 有效性 不足 改进"},
        {"id": "ch5", "name": "结论", "query": "定期风险评价结论 建议"},
    ],
    "sop": [
        {"id": "ch1", "name": "目的和范围", "query": "SOP目的 范围 引用文件"},
        {"id": "ch2", "name": "职责", "query": "职责 部门 人员资质"},
        {"id": "ch3", "name": "操作步骤", "query": "操作步骤 工艺流程 质量控制点"},
        {"id": "ch4", "name": "安全注意事项", "query": "安全注意事项 防护措施 应急处理"},
    ],
    "product_spec": [
        {"id": "ch1", "name": "型号规格", "query": "型号 规格 结构组成 贴敷式胰岛素泵"},
        {"id": "ch2", "name": "性能指标", "query": "性能指标 输注精度 物理性能 电气性能"},
        {"id": "ch3", "name": "检验方法", "query": "检验方法 检验规则 判定标准"},
        {"id": "ch4", "name": "标志包装运输贮存", "query": "标志 包装 运输 贮存"},
    ],
    "instruction": [
        {"id": "ch1", "name": "产品信息", "query": "贴敷式胰岛素泵 产品名称 型号 生产企业"},
        {"id": "ch2", "name": "适用范围", "query": "适用范围 适应症 禁忌症"},
        {"id": "ch3", "name": "使用方法", "query": "使用方法 操作步骤 贴敷 更换 剂量设定"},
        {"id": "ch4", "name": "注意事项", "query": "注意事项 警示 警告 不良反应"},
        {"id": "ch5", "name": "维护保养", "query": "维护 保养 故障排除 客服信息"},
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
        self.use_agent_search = _try_init_agent_search()  # Agent SDK 搜索优先
        self.use_web_search = _try_init_web_search()      # Playwright 作为回退
        self.search_log = []  # 记录每个章节使用的搜索方式

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
        product_params: str = "",
        attachment_content: str = ""
    ) -> str:
        """
        分章节生成文档内容并汇总

        流程：获取章节结构 -> 逐章生成内容 -> 汇总成完整文档
        """
        if not self.api_key:
            raise ValueError("MINIMAX_API_KEY 未设置，请联系管理员配置")

        # 获取文档章节结构
        chapters = DOC_CHAPTERS.get(doc_type, DEFAULT_CHAPTERS)

        # 分章节生成
        full_document = []
        doc_name = DOC_TYPE_LABELS.get(doc_type, doc_type)

        # 添加文档标题
        full_document.append(f"# {product_name} - {doc_name}\n\n")
        full_document.append(f"**产品信息：**\n")
        full_document.append(f"- 产品名称：{product_name}\n")
        full_document.append(f"- 产品类型：{product_type}\n")
        full_document.append(f"- 产品参数：{product_params if product_params else '无'}\n")
        if attachment_content:
            full_document.append(f"\n**附件材料：** 已提供产品相关参考文档\n")
        full_document.append("---\n\n")

        print(f"开始分章节生成文档（共 {len(chapters)} 章）...")
        self.search_log = []  # 重置搜索日志

        for i, chapter in enumerate(chapters, 1):
            chapter_name = chapter["name"]
            chapter_query = f"{chapter['query']} {product_name} {product_type}"

            print(f"  [{i}/{len(chapters)}] 生成章节：{chapter_name}...")

            # 1. 尝试RAG增强（如可用）— 检索 all collection
            chunks = []
            if self.use_rag:
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

            # 1b. 跨collection检索 — 检索 uploads collection（用户上传的附件）
            uploads_chunks = []
            try:
                from app.services.rag.vector_store import VectorStore
                uploads_vs = VectorStore(collection_name="uploads")
                if uploads_vs.count() > 0:
                    uploads_chunks = uploads_vs.retrieve_hybrid(
                        doc_type=doc_type,
                        query=chapter_query,
                        top_k=5,
                        similarity_threshold=0.3,
                        vector_weight=0.7
                    )
                    if uploads_chunks:
                        print(f"    附件检索: 从uploads collection检索到 {len(uploads_chunks)} 条相关段落")
            except Exception as e:
                pass  # uploads collection 不可用时静默跳过

            # 2. 尝试Web搜索补充（如可用）
            # 优先使用 Agent SDK 智能搜索，失败/不可用时回退到 Playwright
            web_info = ""
            downloaded_files = []
            search_method = "none"  # 记录当前章节使用的搜索方式
            if self.use_agent_search and _agent_search_service:
                try:
                    web_info, _ = _agent_search_service.search_regulations(
                        chapter_name=chapter_name,
                        product_type=product_type,
                        product_params=product_params,
                        doc_type=doc_type
                    )
                    if web_info:
                        print(f"    Agent搜索: 获取到 {len(web_info)} 字符相关信息")
                        search_method = "agent"
                except Exception as e:
                    print(f"    [WARNING] Agent搜索失败: {e}")

            # Agent 搜索无结果时，回退到 Playwright
            if not web_info and self.use_web_search and _web_search_service:
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
                        print(f"    Web搜索(Playwright): 获取到 {len(web_info)} 字符相关信息")
                        search_method = "playwright"
                    if downloaded_files:
                        print(f"    下载文件: {len(downloaded_files)} 个")
                        # 将下载的文件添加到知识库
                        self._add_files_to_knowledge_base(downloaded_files, doc_type)
                except Exception as e:
                    print(f"    [WARNING] Web搜索失败: {e}")

            self.search_log.append({
                "chapter": chapter_name,
                "method": search_method
            })

            # 3. 构建本章Prompt
            template = self._get_prompt_template(doc_type)
            base_prompt = template.format(
                product_name=str(product_name),
                product_type=str(product_type),
                product_params=str(product_params) if product_params else "无特殊参数",
                chapter=chapter_name
            )

            # 4. 注入RAG上下文（如检索到相关内容）— 合并 all + uploads
            all_chunks = list(chunks) if chunks else []
            if uploads_chunks:
                all_chunks.extend(uploads_chunks)
            if all_chunks and self.use_rag and _rag_prompt_builder:
                enhanced_prompt = _rag_prompt_builder(
                    base_prompt=base_prompt,
                    doc_type=doc_type,
                    product_name=product_name,
                    product_type=product_type,
                    product_params=product_params,
                    retrieved_chunks=all_chunks
                )
                print(f"    RAG增强: 检索到 {len(all_chunks)} 条相关段落 (all:{len(chunks)}, uploads:{len(uploads_chunks)})")
            elif all_chunks:
                # 有 chunks 但 RAG builder 不可用 — 直接追加为参考文本
                chunk_texts = "\n---\n".join(
                    c.get("text", "") for c in all_chunks[:5]
                )
                enhanced_prompt = base_prompt + "\n\n【参考文档片段】\n" + chunk_texts
                print(f"    直接注入: {len(all_chunks)} 条参考段落 (all:{len(chunks)}, uploads:{len(uploads_chunks)})")
            else:
                enhanced_prompt = base_prompt

            # 5. 注入附件内容 — 第一章全文注入，后续章节关键词匹配
            if attachment_content:
                if i == 1:
                    # 第一章：注入完整附件文本作为产品背景
                    enhanced_prompt = enhanced_prompt.rstrip() + "\n\n" + \
                        "【附件文档 - 产品背景信息】\n" + \
                        "以下内容来自用户上传的产品相关文档，请充分利用这些信息生成内容：\n" + \
                        attachment_content[:3000] + "\n"  # 限制3000字避免超token
                else:
                    # 后续章节：简单关键词匹配注入相关段落
                    relevant = self._match_relevant_paragraphs(attachment_content, chapter_query, max_chars=1500)
                    if relevant:
                        enhanced_prompt = enhanced_prompt.rstrip() + "\n\n" + \
                            "【附件文档 - 相关段落】\n" + relevant + "\n"

            # 6. 注入Web搜索上下文（如获取到相关内容）
            if web_info:
                enhanced_prompt = enhanced_prompt.rstrip() + "\n\n" + "【相关法规标准 - 来自网络搜索】\n" + web_info + "\n"

            # 7. 生成章节内容
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
            "model": "DeepSeek-V4-Pro",
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
        product_params: str = "",
        attachment_content: str = ""
    ) -> str:
        """
        生成文档内容（分章节生成模式，统一入口）

        优先使用分章节生成，当API不可用时降级为占位符
        """
        try:
            # 统一使用分章节生成模式
            return self._generate_by_chapters(
                doc_type, product_name, product_type, product_params, attachment_content
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
        return f"""# {product_name} - {DOC_TYPE_LABELS.get(doc_type, doc_type)}

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

    def _match_relevant_paragraphs(self, text: str, query: str, max_chars: int = 1500) -> str:
        """
        从文本中简单关键词匹配并返回与查询相关的段落

        Args:
            text: 完整文本
            query: 查询关键词
            max_chars: 返回最大字符数

        Returns:
            匹配到的相关段落文本
        """
        if not text or not query:
            return ""

        # 提取关键词（简单分词）
        keywords = [w.strip() for w in query.replace(" ", "").split("_") if w.strip()]
        if not keywords:
            return ""

        # 按段落分割
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        if not paragraphs:
            return ""

        # 为每个段落打分
        scored = []
        for para in paragraphs:
            score = 0
            para_lower = para.lower()
            for kw in keywords:
                for char in kw:
                    if char in para_lower:
                        score += 1
            if score > 0:
                scored.append((score, para))

        # 按分数排序，取前几个
        scored.sort(key=lambda x: x[0], reverse=True)

        result = []
        total_chars = 0
        for _, para in scored:
            if total_chars + len(para) > max_chars:
                # 截断最后一段以不超过限制
                remaining = max_chars - total_chars
                if remaining > 50:
                    result.append(para[:remaining] + "...")
                break
            result.append(para)
            total_chars += len(para) + 2

        return "\n\n".join(result) if result else ""

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

