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

当前暂停所有非协同作业能力。

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

状态：ACCEPTED

结果：

- 创建 `.gitattributes`；
- 通过 commit `5ad1edc` 纳入版本控制。

---

### TASK_014_COMMIT_GITATTRIBUTES

状态：ACCEPTED

结果：

- 只 staging `.gitattributes`并创建单独 commit (`5ad1edc`)。

---

### TASK_015_EXERCISE_COORDINATION_PROTOCOL_FLOW

状态：ACCEPTED

结果：

- 创建一个最小协同流程演练，实测了 `.codex-coordination/inbox/`、`outbox/`、`decisions/` 文件流转流程（编号为 `TASK_017`，对应 commit `9eba7e6`）。

---

### TASK_018_ADD_ADVISORY_ROLE

状态：ACCEPTED

结果：

- 增加非执行性质的顾问角色 (Claude)（对应 commit `45fcf3b`）。

---

### TASK_019_ADD_ROUTING_AND_AUTHORITY_RULES

状态：ACCEPTED

结果：

- 增加文件路由与多 Agent 角色确权边界规则（对应 commit `21ca388`）。

---

### TASK_020_REPLACE_ADVISORY_PROVIDER_WITH_GEMINI

状态：ACCEPTED

结果：

- 将临时顾问角色从 Claude 替换为 Gemini 3.5 Flash，并更新各规则文件（对应 commit `35c028d`）。

---

### TASK_016_REVIEW_COORDINATION_SKILLS

状态：ACCEPTED

结果：

- 完成对 5 个协同 skills 的审计；
- 确认 `scope_guardian.md` 无需修改；
- 将 4 个存在领域残留或 artifact routing 缺口的 skill 拆成单文件 REWORK 任务；
- 完成并验收 TASK_016A-D：
  - `skills/codex_task_writer.md`
  - `skills/codex_output_reviewer.md`
  - `skills/codex_blocker_resolver.md`
  - `skills/project_context_compressor.md`
- 通过 commit `037d257 docs: generalize ACOS skill layer` 固化 skill layer 通用化整改；
- 已 push 到 `origin/master`。

生命周期状态：

```text
COMPLETED
ACCEPTED
COMMITTED
PUSHED
```

相关记录：

- `.codex-coordination/inbox/TASK_016_REVIEW_COORDINATION_SKILLS.md`
- `.codex-coordination/outbox/TASK_016_RESULT.md`

---

## 当前任务

当前无执行中的功能或治理任务。

说明：

- TASK_016 已完成、验收、提交并推送；
- TASK_021 保持 READY，尚未启动；
- 当前仅进行任务记录与项目状态对账。

---

## 后续待办任务

### TASK_021_CORRECT_TEMPLATES_SCOPE_WORDS

状态：READY

目标：

- 修正 `.codex-coordination/templates/` 下的任务模板和上下文压缩模板；
- 清理残留的法律/业务特异性词汇，用标准通用协同描述替换。

---

## 非协同能力边界

非协同作业能力不属于当前系统建设阶段，不作为后续待办或预留规划保留。

---

## 当前全局风险

1. 历史旧文件仍大量处于 untracked 状态，需要继续选择性 add。
2. TASK_016 生命周期已经完成，但相关状态记录与运行 artifact 仍需完成审查和版本固化。
3. TASK_021 已 READY，但不得在状态对账完成前提前启动。

---

## Standard Scope Rules

Current tasks should remain limited to the ChatGPT-Codex coordination system.

Every future task should be classified as one of:

```text
CORE
MAINTENANCE
TEST
DOCS
EXTENSION
OUT_OF_SCOPE
```

Only CORE, MAINTENANCE, TEST, and DOCS tasks may directly enter the current system.

EXTENSION tasks require explicit user approval and are not part of the current core system.

Do not keep reserved extension lists as project planning. Any non-coordination capability requires separate explicit user authorization before implementation.

Before creating extension files or directories, review `SCOPE_POLICY.md` and use `skills/scope_guardian.md`.
