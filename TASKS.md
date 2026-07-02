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

## 当前系统范围

当前项目只建设 ChatGPT-Codex 协同作业系统。

系统本体包括：

- `agents/codex_execution_coordinator.md`
- `skills/codex_task_writer.md`
- `skills/codex_output_reviewer.md`
- `skills/codex_blocker_resolver.md`
- `skills/project_context_compressor.md`
- `.codex-coordination/`
- `PROJECT_BRIEF.md`
- `TASKS.md`
- Git 基础治理文件

当前暂停所有法律业务模块。

---

## 已完成任务

### TASK_001_CREATE_CODEX_EXECUTION_COORDINATOR_AGENT

状态：ACCEPTED_CONDITIONAL

结果：

- 创建 `agents/codex_execution_coordinator.md`

说明：

- 基于 Codex DONE 回报进行条件验收；
- 未逐行审查完整文件内容或 diff。

---

### TASK_002_CREATE_CODEX_TASK_WRITER_SKILL

状态：ACCEPTED_CONDITIONAL

结果：

- 创建 `skills/codex_task_writer.md`

说明：

- 基于 Codex DONE 回报进行条件验收；
- 未逐行审查完整文件内容或 diff。

---

### TASK_003_CREATE_CODEX_OUTPUT_REVIEWER_SKILL

状态：ACCEPTED_CONDITIONAL

结果：

- 创建 `skills/codex_output_reviewer.md`

说明：

- 基于 Codex DONE 回报进行条件验收；
- 未逐行审查完整文件内容或 diff。

---

### TASK_004_CREATE_CODEX_BLOCKER_RESOLVER_SKILL

状态：ACCEPTED_CONDITIONAL

结果：

- 创建 `skills/codex_blocker_resolver.md`

说明：

- 基于 Codex DONE 回报进行条件验收；
- 未逐行审查完整文件内容或 diff。

---

### TASK_005_CREATE_PROJECT_CONTEXT_COMPRESSOR_SKILL

状态：ACCEPTED_CONDITIONAL

结果：

- 创建 `skills/project_context_compressor.md`

说明：

- 基于 Codex DONE 回报进行条件验收；
- 未逐行审查完整文件内容或 diff。

---

### TASK_006_CREATE_CODEX_COORDINATION_PROTOCOL_DIR

状态：ACCEPTED_CONDITIONAL

结果：

- 创建 `.codex-coordination/`
- 创建 `.codex-coordination/README.md`
- 创建 `.codex-coordination/inbox/`
- 创建 `.codex-coordination/outbox/`
- 创建 `.codex-coordination/decisions/`
- 创建 `.codex-coordination/logs/`
- 创建 `.codex-coordination/templates/`
- 创建 `.codex-coordination/templates/task_template.md`
- 创建 `.codex-coordination/templates/result_template.md`
- 创建 `.codex-coordination/templates/decision_template.md`
- 创建 `.codex-coordination/templates/context_pack_template.md`

说明：

- 基于 Codex DONE 回报进行条件验收；
- 未逐行审查完整文件内容或 diff。

---

### TASK_007_CREATE_PROJECT_BRIEF_AND_TASKS

状态：ACCEPTED_CONDITIONAL

结果：

- 创建 `PROJECT_BRIEF.md`
- 创建 `TASKS.md`

说明：

- 基于 Codex DONE 回报进行条件验收；
- 后续通过范围校准任务修正项目边界。

---

### TASK_008_DIAGNOSE_GIT_STATUS

状态：ACCEPTED

结果：

- 确认原 `.git` 是空目录；
- 确认 Git 安装正常；
- 确认当前目录原本不是有效 Git 仓库。

---

### TASK_009_INITIALIZE_LOCAL_GIT_REPOSITORY_NO_COMMIT

状态：ACCEPTED

结果：

- 备份原空 `.git` 为 `.git.empty-backup`；
- 初始化本地 Git 仓库；
- 未执行 `git add`；
- 未执行 `git commit`。

---

### TASK_010_CREATE_PROJECT_GITIGNORE

状态：ACCEPTED

结果：

- 创建 `.gitignore`；
- 排除缓存、临时目录、大型抓包、数据库、生成文档、本地备份等内容；
- 未执行 `git add`；
- 未执行 `git commit`。

---

### TASK_010A_UPDATE_GITIGNORE_FOR_CODEX_LOCAL_DIRS

状态：ACCEPTED

结果：

- 修改 `.gitignore`；
- 增加 `.codex_deps/` 和 `.codex_ssh_lib/` 忽略规则；
- 未执行 `git add`；
- 未执行 `git commit`。

---

### TASK_011_STAGE_COORDINATION_FILES_ONLY_NO_COMMIT

状态：ACCEPTED

结果：

- 只 staging 13 个协同机制相关文件；
- 未 staging 历史旧文件；
- 未执行 `git commit`。

---

### TASK_011A_REPAIR_GIT_OWNERSHIP_AND_PERMISSIONS

状态：ACCEPTED

结果：

- 修复 `.git` ownership / ACL；
- 解决 dubious ownership；
- 未执行 `git add`；
- 未执行 `git commit`。

---

### TASK_012_COMMIT_COORDINATION_BASELINE_IDENTITY_FIX

状态：ACCEPTED

结果：

- 设置本仓库本地 Git identity；
- 创建第一次基线 commit：

```text
c668de9 chore: establish ChatGPT-Codex coordination baseline
```

---

### TASK_013_CREATE_GITATTRIBUTES_FOR_LINE_ENDINGS

状态：DONE_PENDING_REVIEW

结果：

- 创建 `.gitattributes`；
- 未执行 `git add`；
- 未执行 `git commit`。

说明：

- 该文件尚未纳入版本控制；
- 后续应单独 staging 和 commit。

---

## 当前任务

### TASK_SCOPE_CORRECTION_COORDINATION_SYSTEM_ONLY

状态：IN_PROGRESS

目标：

- 只修改 `PROJECT_BRIEF.md` 和 `TASKS.md`；
- 将当前项目范围修正为 ChatGPT-Codex 协同作业系统；
- 将法律业务内容降级为未来可选应用方向。

限制：

- 不得创建法律业务 agent；
- 不得创建法律业务 skill；
- 不得创建 `mcp/`；
- 不得创建 `templates/`；
- 不得创建 `tests/sample_cases/`；
- 不得修改 `agents/`；
- 不得修改 `skills/`；
- 不得修改 `.codex-coordination/`；
- 不得执行 `git add`；
- 不得执行 `git commit`。

---

## 后续待办任务

### TASK_014_COMMIT_GITATTRIBUTES

状态：READY

目标：

- 只 staging `.gitattributes`；
- 创建单独 commit；
- 不 staging 历史旧文件。

---

### TASK_015_EXERCISE_COORDINATION_PROTOCOL_FLOW

状态：READY

目标：

- 创建一个最小协同流程演练；
- 使用 `.codex-coordination/inbox/`、`outbox/`、`decisions/` 记录任务、结果和审查；
- 不进入任何法律业务模块。

---

### TASK_016_REVIEW_COORDINATION_SKILLS

状态：READY

目标：

- 审查四个协同 skills；
- 检查是否存在职责重叠、边界缺口或回报格式不一致；
- 如需修改，拆成单文件 REWORK 任务。

---

## 未来可选应用方向

以下内容不属于当前协同系统建设阶段，仅作为后续可能应用方向保留。除非用户另行明确授权，不得创建相关目录或文件：

- 民事执行财产线索；
- 银行流水分析；
- 公司责任分析；
- 证据审查；
- 法律检索 MCP；
- 法律文书模板；
- 样例案件测试。

---

## 当前全局风险

1. 历史旧文件仍大量处于 untracked 状态，需要继续选择性 add。
2. `.gitattributes` 已创建但尚未纳入 commit。
3. 已完成协同文件中部分内容此前为条件验收，后续如发现缺口应局部返工。
4. 协同协议目录尚未通过真实 inbox / outbox / decisions 流程实测。
