"""
文档类型公共常量 — DOC_TYPES 列表和 doc_type_labels 映射
贴敷式胰岛素泵（Patch Insulin Pump）全生命周期文档类型
覆盖9大阶段：设计策划、设计输入、设计输出、设计验证、设计确认、设计转化、生产制造、注册申报、上市后
"""

# ======================== 全部文档类型 ========================

DOC_TYPES = [
    # ========== 一、设计策划阶段 (Design Planning) — 10份 ==========
    "design_development_plan",           # 设计开发策划书
    "product_requirements_spec",         # 产品需求规格书(PRS)
    "risk_management_plan",              # 风险管理计划
    "software_development_plan",         # 软件开发生命周期计划
    "usability_engineering_plan",        # 可用性工程计划
    "biological_evaluation_plan",        # 生物学评价计划
    "sterilization_validation_plan",     # 灭菌验证计划
    "packaging_validation_plan",         # 包装验证计划
    "supplier_management_plan",          # 供应商管理计划
    "regulatory_strategy_document",      # 注册策略文件

    # ========== 二、设计输入阶段 (Design Input) — 6份 ==========
    "design_input",                      # 设计输入文件
    "software_requirements_spec",        # 软件需求规格书(SRS)
    "hardware_requirements_spec",        # 硬件需求规格书
    "ui_requirements_spec",              # 用户界面需求规格书
    "cybersecurity_requirements",        # 网络安全需求规格书
    "labeling_ifu_requirements",         # 标签和说明书需求

    # ========== 三、设计输出阶段 (Design Output) — 12份 ==========
    "product_drawings",                  # 产品图纸
    "bill_of_materials",                 # 物料清单(BOM)
    "product_specification",             # 产品规格书
    "software_architecture_doc",         # 软件架构文档
    "software_detailed_design",          # 软件详细设计文档
    "hardware_design_doc",               # 硬件设计文档
    "firmware_design_doc",               # 固件设计文档
    "industrial_design_doc",             # 工业设计文档
    "label_nameplate_artwork",           # 标签/铭牌设计稿
    "packaging_design_artwork",          # 包装设计稿
    "instruction_for_use",               # 说明书/用户手册(IFU)
    "manufacturing_process_draft",       # 生产工艺文件(草案)

    # ========== 四、设计验证阶段 (Design Verification) — 17份 ==========
    "design_verification_master_plan",   # 设计验证总计划
    "electrical_safety_test_report",     # 电气安全测试报告
    "emc_test_report",                   # EMC测试报告
    "alarm_system_test_report",          # 报警系统测试报告
    "infusion_accuracy_test_report",     # 输注精度测试报告
    "software_unit_test_report",         # 软件单元测试报告
    "software_integration_test_report",  # 软件集成测试报告
    "software_system_test_report",       # 软件系统测试报告
    "battery_performance_test_report",   # 电池性能测试报告
    "ip_rating_test_report",             # 防水防尘测试报告(IP)
    "environmental_reliability_test",    # 环境可靠性测试报告
    "package_transport_test_report",     # 包装运输测试报告
    "seal_integrity_test_report",        # 密封完整性测试报告
    "material_characterization_report",  # 材料物理/化学测试报告
    "accelerated_aging_test_report",     # 加速老化测试报告
    "sensor_calibration_validation",     # 传感器校准验证报告
    "cybersecurity_test_report",         # 网络安全测试报告

    # ========== 五、设计确认阶段 (Design Validation) — 11份 ==========
    "design_validation_master_plan",     # 设计确认总计划
    "summative_usability_report",        # 总结性可用性工程报告
    "clinical_evaluation_report",        # 临床评价报告(CER)
    "biological_evaluation_report",      # 生物学评价报告
    "cytotoxicity_test_report",          # 细胞毒性试验报告
    "skin_irritation_sensitization",     # 皮肤刺激/致敏试验报告
    "blood_compatibility_test_report",   # 血液相容性试验报告
    "sal_validation_report",             # 无菌保证水平验证报告(SAL)
    "sterilization_residue_test_report", # 灭菌残留测试报告
    "process_validation_iq_oq_pq",       # 过程确认报告(IQ/OQ/PQ)
    "cleaning_validation_report",        # 清洗验证报告

    # ========== 六、设计转化阶段 (Design Transfer) — 7份 ==========
    "design_transfer_plan",              # 设计转化计划
    "design_transfer_report",            # 设计转化报告
    "device_master_record",              # 医疗器械主记录(DMR)
    "manufacturing_sop",                 # 生产工艺SOP
    "inspection_sop",                    # 检验SOP
    "equipment_operation_procedures",    # 设备操作规程
    "work_environment_control_doc",      # 工作环境控制文件

    # ========== 七、生产制造阶段 (Production) — 10份 ==========
    "batch_production_record",           # 批生产记录(BPR)
    "batch_inspection_record",           # 批检验记录
    "device_history_record",             # 器械历史记录(DHR)
    "incoming_inspection_records",       # 进货检验记录
    "supplier_audit_reports",            # 供应商审核报告
    "calibration_records",               # 校准记录
    "environmental_monitoring_records",  # 环境监测记录
    "nonconforming_product_records",     # 不合格品处理记录
    "sterilization_process_records",     # 灭菌过程记录
    "udi_assignment_records",            # UDI赋码记录

    # ========== 八、注册申报阶段 (Registration) — 10份 ==========
    "registration_dossier",              # 产品注册申报资料
    "product_technical_requirements",    # 产品技术要求
    "risk_management_report",            # 风险管理报告
    "essential_safety_conformity",       # 基本安全和基本性能符合性声明
    "software_version_description",      # 软件版本描述文档
    "cybersecurity_disclosure",          # 网络安全披露文档
    "clinical_evaluation_report_reg",    # 临床评价报告(注册用)
    "ifu_labeling_for_registration",     # 说明书/标签审核稿(注册用)
    "declaration_of_conformity",         # 符合性声明(DoC)
    "qms_certificate_proof",             # 质量管理体系证明文件

    # ========== 九、上市后阶段 (Post-Market) — 11份 ==========
    "pms_plan",                          # 上市后监管计划(PMS Plan)
    "pmcf_plan",                         # 上市后临床跟踪计划(PMCF Plan)
    "complaint_handling_records",        # 投诉处理记录
    "adverse_event_reports",             # 不良事件报告
    "periodic_safety_update_report",     # 定期安全更新报告(PSUR)
    "capa_records",                      # 纠正和预防措施记录(CAPA)
    "change_control_records",            # 变更控制记录
    "recall_field_safety_notice",        # 产品召回/现场安全通知记录
    "management_review_report",          # 管理评审报告
    "internal_audit_reports",            # 内部审核报告
    "pms_report",                        # 上市后监管报告(PMS Report)

    # ========== 保留原有兼容类型（映射到新类型） ==========
    "design_output",                     # 设计输出（通用）
    "design_review",                     # 设计评审
    "design_verification",               # 设计验证（通用）
    "design_validation",                 # 设计确认（通用）
    "design_change",                     # 设计变更
    "design_history_file",               # 设计历史文件(DHF)
    "fmea_analysis",                     # FMEA分析报告
    "risk_acceptance_criteria",          # 风险可接受准则
    "periodic_risk_evaluation",          # 定期风险评价报告
    "sop",                               # 作业指导书(SOP)（通用）
]

# 去重
DOC_TYPES = list(dict.fromkeys(DOC_TYPES))

# ======================== 文档类型中文标签 ========================

DOC_TYPE_LABELS = {
    # 一、设计策划阶段
    "design_development_plan": "设计开发策划书",
    "product_requirements_spec": "产品需求规格书(PRS)",
    "risk_management_plan": "风险管理计划",
    "software_development_plan": "软件开发生命周期计划",
    "usability_engineering_plan": "可用性工程计划",
    "biological_evaluation_plan": "生物学评价计划",
    "sterilization_validation_plan": "灭菌验证计划",
    "packaging_validation_plan": "包装验证计划",
    "supplier_management_plan": "供应商管理计划",
    "regulatory_strategy_document": "注册策略文件",

    # 二、设计输入阶段
    "design_input": "设计输入文件",
    "software_requirements_spec": "软件需求规格书(SRS)",
    "hardware_requirements_spec": "硬件需求规格书",
    "ui_requirements_spec": "用户界面需求规格书",
    "cybersecurity_requirements": "网络安全需求规格书",
    "labeling_ifu_requirements": "标签和说明书需求",

    # 三、设计输出阶段
    "product_drawings": "产品图纸",
    "bill_of_materials": "物料清单(BOM)",
    "product_specification": "产品规格书",
    "software_architecture_doc": "软件架构文档",
    "software_detailed_design": "软件详细设计文档",
    "hardware_design_doc": "硬件设计文档",
    "firmware_design_doc": "固件设计文档",
    "industrial_design_doc": "工业设计文档",
    "label_nameplate_artwork": "标签/铭牌设计稿",
    "packaging_design_artwork": "包装设计稿",
    "instruction_for_use": "说明书/用户手册(IFU)",
    "manufacturing_process_draft": "生产工艺文件(草案)",

    # 四、设计验证阶段
    "design_verification_master_plan": "设计验证总计划",
    "electrical_safety_test_report": "电气安全测试报告",
    "emc_test_report": "EMC测试报告",
    "alarm_system_test_report": "报警系统测试报告",
    "infusion_accuracy_test_report": "输注精度测试报告",
    "software_unit_test_report": "软件单元测试报告",
    "software_integration_test_report": "软件集成测试报告",
    "software_system_test_report": "软件系统测试报告",
    "battery_performance_test_report": "电池性能测试报告",
    "ip_rating_test_report": "防水防尘测试报告(IP)",
    "environmental_reliability_test": "环境可靠性测试报告",
    "package_transport_test_report": "包装运输测试报告",
    "seal_integrity_test_report": "密封完整性测试报告",
    "material_characterization_report": "材料物理/化学测试报告",
    "accelerated_aging_test_report": "加速老化测试报告",
    "sensor_calibration_validation": "传感器校准验证报告",
    "cybersecurity_test_report": "网络安全测试报告",

    # 五、设计确认阶段
    "design_validation_master_plan": "设计确认总计划",
    "summative_usability_report": "总结性可用性工程报告",
    "clinical_evaluation_report": "临床评价报告(CER)",
    "biological_evaluation_report": "生物学评价报告",
    "cytotoxicity_test_report": "细胞毒性试验报告",
    "skin_irritation_sensitization": "皮肤刺激/致敏试验报告",
    "blood_compatibility_test_report": "血液相容性试验报告",
    "sal_validation_report": "无菌保证水平验证报告(SAL)",
    "sterilization_residue_test_report": "灭菌残留测试报告",
    "process_validation_iq_oq_pq": "过程确认报告(IQ/OQ/PQ)",
    "cleaning_validation_report": "清洗验证报告",

    # 六、设计转化阶段
    "design_transfer_plan": "设计转化计划",
    "design_transfer_report": "设计转化报告",
    "device_master_record": "医疗器械主记录(DMR)",
    "manufacturing_sop": "生产工艺SOP",
    "inspection_sop": "检验SOP",
    "equipment_operation_procedures": "设备操作规程",
    "work_environment_control_doc": "工作环境控制文件",

    # 七、生产制造阶段
    "batch_production_record": "批生产记录(BPR)",
    "batch_inspection_record": "批检验记录",
    "device_history_record": "器械历史记录(DHR)",
    "incoming_inspection_records": "进货检验记录",
    "supplier_audit_reports": "供应商审核报告",
    "calibration_records": "校准记录",
    "environmental_monitoring_records": "环境监测记录",
    "nonconforming_product_records": "不合格品处理记录",
    "sterilization_process_records": "灭菌过程记录",
    "udi_assignment_records": "UDI赋码记录",

    # 八、注册申报阶段
    "registration_dossier": "产品注册申报资料",
    "product_technical_requirements": "产品技术要求",
    "risk_management_report": "风险管理报告",
    "essential_safety_conformity": "基本安全和基本性能符合性声明",
    "software_version_description": "软件版本描述文档",
    "cybersecurity_disclosure": "网络安全披露文档",
    "clinical_evaluation_report_reg": "临床评价报告(注册用)",
    "ifu_labeling_for_registration": "说明书/标签审核稿(注册用)",
    "declaration_of_conformity": "符合性声明(DoC)",
    "qms_certificate_proof": "质量管理体系证明文件",

    # 九、上市后阶段
    "pms_plan": "上市后监管计划(PMS Plan)",
    "pmcf_plan": "上市后临床跟踪计划(PMCF Plan)",
    "complaint_handling_records": "投诉处理记录",
    "adverse_event_reports": "不良事件报告",
    "periodic_safety_update_report": "定期安全更新报告(PSUR)",
    "capa_records": "纠正和预防措施记录(CAPA)",
    "change_control_records": "变更控制记录",
    "recall_field_safety_notice": "产品召回/现场安全通知记录",
    "management_review_report": "管理评审报告",
    "internal_audit_reports": "内部审核报告",
    "pms_report": "上市后监管报告(PMS Report)",

    # 保留原有兼容类型
    "design_output": "设计输出",
    "design_review": "设计评审",
    "design_verification": "设计验证",
    "design_validation": "设计确认",
    "design_change": "设计变更",
    "design_history_file": "设计历史文件(DHF)",
    "fmea_analysis": "FMEA分析报告",
    "risk_acceptance_criteria": "风险可接受准则",
    "periodic_risk_evaluation": "定期风险评价报告",
    "sop": "作业指导书(SOP)",
    "product_spec": "产品技术要求",
    "instruction": "使用说明书",
}

# ======================== 文档分类（9大生命周期阶段） ========================

DOC_CATEGORIES = {
    "design_planning": {
        "name": "一、设计策划",
        "description": "设计策划阶段 — 定义产品需求、风险管理计划、验证策略、注册路径",
        "icon": "📋",
        "types": [
            "design_development_plan", "product_requirements_spec", "risk_management_plan",
            "software_development_plan", "usability_engineering_plan", "biological_evaluation_plan",
            "sterilization_validation_plan", "packaging_validation_plan", "supplier_management_plan",
            "regulatory_strategy_document"
        ]
    },
    "design_input": {
        "name": "二、设计输入",
        "description": "设计输入阶段 — 功能、性能、安全、法规、使用环境等完整需求定义",
        "icon": "📥",
        "types": [
            "design_input", "software_requirements_spec", "hardware_requirements_spec",
            "ui_requirements_spec", "cybersecurity_requirements", "labeling_ifu_requirements"
        ]
    },
    "design_output": {
        "name": "三、设计输出",
        "description": "设计输出阶段 — 图纸、BOM、软件架构、包装设计、IFU等",
        "icon": "📤",
        "types": [
            "product_drawings", "bill_of_materials", "product_specification",
            "software_architecture_doc", "software_detailed_design", "hardware_design_doc",
            "firmware_design_doc", "industrial_design_doc", "label_nameplate_artwork",
            "packaging_design_artwork", "instruction_for_use", "manufacturing_process_draft"
        ]
    },
    "design_verification": {
        "name": "四、设计验证",
        "description": "设计验证阶段 — 电气安全、EMC、软件测试、输注精度、环境可靠性等17项验证",
        "icon": "🔬",
        "types": [
            "design_verification_master_plan", "electrical_safety_test_report",
            "emc_test_report", "alarm_system_test_report", "infusion_accuracy_test_report",
            "software_unit_test_report", "software_integration_test_report",
            "software_system_test_report", "battery_performance_test_report",
            "ip_rating_test_report", "environmental_reliability_test",
            "package_transport_test_report", "seal_integrity_test_report",
            "material_characterization_report", "accelerated_aging_test_report",
            "sensor_calibration_validation", "cybersecurity_test_report"
        ]
    },
    "design_validation": {
        "name": "五、设计确认",
        "description": "设计确认阶段 — 可用性、临床评价、生物学评价、灭菌确认、过程确认",
        "icon": "✅",
        "types": [
            "design_validation_master_plan", "summative_usability_report",
            "clinical_evaluation_report", "biological_evaluation_report",
            "cytotoxicity_test_report", "skin_irritation_sensitization",
            "blood_compatibility_test_report", "sal_validation_report",
            "sterilization_residue_test_report", "process_validation_iq_oq_pq",
            "cleaning_validation_report"
        ]
    },
    "design_transfer": {
        "name": "六、设计转化",
        "description": "设计转化阶段 — 从研发到生产的交接，DMR、SOP、设备操作规程",
        "icon": "🏭",
        "types": [
            "design_transfer_plan", "design_transfer_report", "device_master_record",
            "manufacturing_sop", "inspection_sop", "equipment_operation_procedures",
            "work_environment_control_doc"
        ]
    },
    "production": {
        "name": "七、生产制造",
        "description": "生产制造阶段 — 批记录、检验记录、DHR、不合格品处理、灭菌记录",
        "icon": "⚙️",
        "types": [
            "batch_production_record", "batch_inspection_record", "device_history_record",
            "incoming_inspection_records", "supplier_audit_reports", "calibration_records",
            "environmental_monitoring_records", "nonconforming_product_records",
            "sterilization_process_records", "udi_assignment_records"
        ]
    },
    "registration": {
        "name": "八、注册申报",
        "description": "注册申报阶段 — NMPA/FDA/CE技术文档、风险管理报告、符合性声明",
        "icon": "📝",
        "types": [
            "registration_dossier", "product_technical_requirements", "risk_management_report",
            "essential_safety_conformity", "software_version_description",
            "cybersecurity_disclosure", "clinical_evaluation_report_reg",
            "ifu_labeling_for_registration", "declaration_of_conformity", "qms_certificate_proof"
        ]
    },
    "post_market": {
        "name": "九、上市后",
        "description": "上市后阶段 — PMS、PMCF、投诉处理、不良事件、CAPA、内部审核",
        "icon": "📊",
        "types": [
            "pms_plan", "pmcf_plan", "complaint_handling_records", "adverse_event_reports",
            "periodic_safety_update_report", "capa_records", "change_control_records",
            "recall_field_safety_notice", "management_review_report", "internal_audit_reports",
            "pms_report"
        ]
    },
    "legacy": {
        "name": "通用/兼容",
        "description": "原有兼容类型 — 通用设计开发、风险管理、SOP等",
        "icon": "📄",
        "types": [
            "design_output", "design_review", "design_verification", "design_validation",
            "design_change", "design_history_file", "fmea_analysis", "risk_acceptance_criteria",
            "periodic_risk_evaluation", "sop", "product_spec", "instruction"
        ]
    }
}

SUPPORTED_UPLOAD_FORMATS = [".docx", ".pdf", ".txt"]
MAX_UPLOAD_SIZE_MB = 10
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024
