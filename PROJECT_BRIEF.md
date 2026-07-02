# Project Brief

## 一、项目目标

本项目当前目标是建立一套 ChatGPT-Codex 协同作业系统，使 ChatGPT 作为规划、任务拆解、审查和决策中心，Codex 作为受控执行工具。

当前系统本体只包括：

- 主控 agent；
- 配套 skills；
- 协同作业协议目录；
- 任务流转文件；
- Git 基础治理。

非协同作业能力不是当前阶段任务。如需新增，必须由用户另行明确授权。

---

## 二、当前阶段

当前阶段：ChatGPT-Codex 协同作业系统建设。

已完成：

- 主控 agent；
- 任务书生成 skill；
- 输出审查 skill；
- BLOCKED 处理 skill；
- 上下文压缩 skill；
- 文件驱动协作协议目录；
- 项目总控文档；
- Git 初始化、忽略规则和基线提交。

当前允许继续完善：

- 协同 agent；
- 协同 skills；
- `.codex-coordination/` 协议层；
- 任务状态、回报、审查和返工流程；
- Git diff、status、commit、回滚等基础治理；
- 协同流程的实测样例。

当前暂停：

- 任何非协同作业能力；
- 任何未获用户明确授权的独立能力；
- 任何会把本系统变成业务系统的实现。

---

## 三、ChatGPT 职责

ChatGPT 负责：

1. 理解用户目标；
2. 制定协同作业结构；
3. 拆解 Codex 可执行任务；
4. 生成 Codex 任务书；
5. 控制 Codex 修改范围；
6. 处理 Codex BLOCKED 问题；
7. 审查 Codex DONE 回报；
8. 判断 ACCEPTED / REWORK / BLOCKED；
9. 生成返工任务；
10. 维护项目方向和边界。

---

## 四、Codex 职责

Codex 负责：

1. 按任务书创建文件；
2. 按任务书修改文件；
3. 按任务书运行验证命令；
4. 输出新增、修改、删除文件清单；
5. 输出验证方式；
6. 输出测试或检查结果；
7. 输出潜在风险；
8. 遇到不确定事项时进入 BLOCKED；
9. 不自行扩大任务范围；
10. 不自行推进下一任务。

---

## 五、任务状态规范

任务状态包括：

```text
READY
IN_PROGRESS
BLOCKED
DONE
ACCEPTED
REWORK
CANCELLED
```

状态说明：

- READY：任务已明确，可以交给 Codex 执行；
- IN_PROGRESS：Codex 正在执行；
- BLOCKED：Codex 遇到问题，需要 ChatGPT 或用户决策；
- DONE：Codex 已完成，等待 ChatGPT 审查；
- ACCEPTED：ChatGPT 审查通过；
- REWORK：ChatGPT 要求返工；
- CANCELLED：任务取消。

DONE 不等于 ACCEPTED。

---

## 六、协同作业文件结构

当前已建立：

```text
agents/
  codex_execution_coordinator.md

skills/
  codex_task_writer.md
  codex_output_reviewer.md
  codex_blocker_resolver.md
  project_context_compressor.md

.codex-coordination/
  README.md
  inbox/
  outbox/
  decisions/
  logs/
  templates/
    task_template.md
    result_template.md
    decision_template.md
    context_pack_template.md

PROJECT_BRIEF.md
TASKS.md
.gitignore
```

`.gitattributes` 已创建但尚未纳入基线提交，后续应单独 staging 和 commit。

---

## 七、基本工作流

标准流程：

```text
ChatGPT 生成任务书
        ↓
任务书进入 .codex-coordination/inbox/
        ↓
Codex 执行
        ↓
Codex 输出 DONE 或 BLOCKED
        ↓
结果进入 .codex-coordination/outbox/
        ↓
ChatGPT 审查
        ↓
审查结论进入 .codex-coordination/decisions/
        ↓
ACCEPTED / REWORK / BLOCKED / CANCELLED
```

---

## 八、Codex 执行原则

1. 每次只执行一个明确任务。
2. 每次只修改任务书授权范围内的文件。
3. 不得删除已有文件，除非任务书明确授权。
4. 不得修改依赖文件，除非任务书明确授权。
5. 不得编造外部服务配置。
6. 不得写入真实密钥、token、账号或认证参数。
7. 遇到同名文件、路径冲突、权限边界不明时必须 BLOCKED。
8. 不得自行处理当前任务之外的业务判断。
9. 不得自行推进下一任务。
10. DONE 后等待 ChatGPT 审查。

---

## 九、当前边界

当前项目不是业务系统本体，而是 ChatGPT-Codex 协同作业系统。

当前阶段不得启动任何非协同作业能力。

如需新增非协同作业能力，必须由用户另行明确授权，并作为独立任务处理。

---

## 十、当前风险

1. 历史旧文件仍大量处于 untracked 状态，需要继续选择性 add。
2. `.gitattributes` 已创建但尚未纳入 commit。
3. 已提交的协同文件此前多为条件验收，后续如发现内容缺口，应通过小范围 REWORK 修正。
4. 当前尚未实测完整的 inbox / outbox / decisions 文件流转。

---

## 十一、后续优先级

建议后续按以下顺序推进：

1. 单独 staging 并 commit `.gitattributes`；
2. 创建一个最小测试任务，实测 `.codex-coordination/inbox → outbox → decisions` 流程；
3. 对四个协同 skills 做一次内容审查；
4. 根据实测结果局部修订 agent、skills 或模板；
5. 形成稳定的协同作业使用说明。

任何非协同作业能力仅能在用户另行明确授权后启动。

---

## Standard General Coordination Scope

Project name: Standard General ChatGPT-Codex Coordination System.

The current system is a general-purpose coordination system. Its core responsibility is to govern how ChatGPT and Codex collaborate. It does not provide non-coordination capability.

Core system capabilities include:

1. ChatGPT-Codex role separation.
2. Codex task generation.
3. Codex execution boundary control.
4. DONE reporting.
5. BLOCKED interruption handling.
6. ChatGPT review decisions.
7. REWORK task generation.
8. Context compression.
9. Git safety rules.
10. Inbox / outbox / decisions flow.
11. Task state tracking.
12. Scope guarding.

Any non-coordination capability is outside the core system. It must not be listed as current core work.

Scope policy is defined in `SCOPE_POLICY.md`. Future tasks should be checked against that policy before implementation.
