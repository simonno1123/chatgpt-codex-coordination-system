# Tasks

## 任务状态说明

可用状态：

```text
READY
IN_PROGRESS
BLOCKED
DONE
ACCEPTED
REWORK
CANCELLED
```

DONE 不等于 ACCEPTED。Codex 完成任务后，必须等待 ChatGPT 审查。

---

## 已完成任务

### TASK_001_CREATE_CODEX_EXECUTION_COORDINATOR_AGENT

状态：ACCEPTED_CONDITIONAL

结果：

* 创建 `agents/codex_execution_coordinator.md`

说明：

* 基于 Codex DONE 回报进行条件验收；
* 未逐行审查完整文件内容或 diff。

---

### TASK_002_CREATE_CODEX_TASK_WRITER_SKILL

状态：ACCEPTED_CONDITIONAL

结果：

* 创建 `skills/codex_task_writer.md`

说明：

* 基于 Codex DONE 回报进行条件验收；
* 未逐行审查完整文件内容或 diff。

---

### TASK_003_CREATE_CODEX_OUTPUT_REVIEWER_SKILL

状态：ACCEPTED_CONDITIONAL

结果：

* 创建 `skills/codex_output_reviewer.md`

说明：

* 基于 Codex DONE 回报进行条件验收；
* 未逐行审查完整文件内容或 diff。

---

### TASK_004_CREATE_CODEX_BLOCKER_RESOLVER_SKILL

状态：ACCEPTED_CONDITIONAL

结果：

* 创建 `skills/codex_blocker_resolver.md`

说明：

* 基于 Codex DONE 回报进行条件验收；
* 未逐行审查完整文件内容或 diff。

---

### TASK_005_CREATE_PROJECT_CONTEXT_COMPRESSOR_SKILL

状态：ACCEPTED_CONDITIONAL

结果：

* 创建 `skills/project_context_compressor.md`

说明：

* 基于 Codex DONE 回报进行条件验收；
* 未逐行审查完整文件内容或 diff。

---

### TASK_006_CREATE_CODEX_COORDINATION_PROTOCOL_DIR

状态：ACCEPTED_CONDITIONAL

结果：

* 创建 `.codex-coordination/`
* 创建 `.codex-coordination/README.md`
* 创建 `.codex-coordination/inbox/`
* 创建 `.codex-coordination/outbox/`
* 创建 `.codex-coordination/decisions/`
* 创建 `.codex-coordination/logs/`
* 创建 `.codex-coordination/templates/`
* 创建 `.codex-coordination/templates/task_template.md`
* 创建 `.codex-coordination/templates/result_template.md`
* 创建 `.codex-coordination/templates/decision_template.md`
* 创建 `.codex-coordination/templates/context_pack_template.md`

说明：

* 基于 Codex DONE 回报进行条件验收；
* 未逐行审查完整文件内容或 diff。

---

## 当前任务

### TASK_007_CREATE_PROJECT_BRIEF_AND_TASKS

状态：READY

目标：

* 创建 `PROJECT_BRIEF.md`
* 创建 `TASKS.md`

限制：

* 不得修改已有文件；
* 不得处理 `.git` 问题；
* 不得创建法律业务模块；
* 不得修改 `.codex-coordination/`；
* 如同名文件已存在，必须 BLOCKED。

---

## 后续待办任务

### TASK_008_DIAGNOSE_GIT_STATUS

状态：READY

目标：

* 诊断当前目录下 `.git` 为什么不能被识别为有效仓库；
* 只输出诊断结论；
* 不得自动修复；
* 不得删除或重建 `.git`。

---

### TASK_009_CREATE_LEGAL_CN_BASE_STRUCTURE

状态：READY

目标：

创建中国民商事诉讼与执行本地化系统的基础目录结构。

预期目录：

* templates/
* mcp/
* tests/sample_cases/

说明：

* `agents/` 和 `skills/` 已存在；
* 不得覆盖已有文件。

---

### TASK_010_CREATE_ENFORCEMENT_INVESTIGATOR_AGENT

状态：READY

目标：

创建民事执行财产线索调查 agent。

预期文件：

* agents/enforcement_investigator.md

---

### TASK_011_CREATE_BANK_FLOW_ANALYSIS_SKILL

状态：READY

目标：

创建银行流水分析 skill。

重点分析：

1. 资金流向；
2. 提现；
3. 自我转账；
4. 夫妻或关联账户转移；
5. 最终受益人；
6. 异常交易；
7. 履行能力；
8. 执行策略；
9. 补证清单。

预期文件：

* skills/bank_flow_analysis.md

---

### TASK_012_CREATE_COMPANY_LIABILITY_AGENT

状态：READY

目标：

创建公司人格否认、实控人责任、股东损害债权人利益分析 agent。

预期文件：

* agents/company_liability_analyzer.md

---

### TASK_013_CREATE_EVIDENCE_REVIEW_AGENT

状态：READY

目标：

创建交易事实与证据审查 agent。

适用材料：

1. 微信聊天记录；
2. 对账单；
3. 送货单；
4. 发票；
5. 付款记录；
6. 工商档案；
7. 裁判文书；
8. 谈话笔录。

预期文件：

* agents/evidence_reviewer.md

---

### TASK_014_CREATE_PKULAW_MCP_PLACEHOLDERS

状态：READY

目标：

创建北大法宝法律数据 MCP 与案例数据 MCP 的配置占位说明。

要求：

* 不得编造真实密钥；
* 不得编造认证参数；
* 不得写入真实 token；
* 仅使用 placeholder。

预期目录或文件：

* mcp/

---

### TASK_015_CREATE_OUTPUT_TEMPLATES

状态：READY

目标：

创建常用法律输出模板。

建议模板：

* templates/evidence_catalog.md
* templates/investigation_order_application.md
* templates/enforcement_strategy_report.md
* templates/legal_analysis_report.md

---

## 当前全局风险

1. `.git` 不能被识别为有效仓库，影响 diff 审查。
2. 已完成文件多为条件验收，尚未逐行审查完整内容。
3. 尚未创建法律业务模块。
4. 尚未建立测试样例。
5. 尚未接入外部 MCP。
