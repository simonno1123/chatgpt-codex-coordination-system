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

当前阶段：ACOS v2 Initial Implementation Stage，ACTIVE / NOT CLOSED（2026-10-16事实索引）。本节不构成新的阶段决定或正式状态转换。

当前状态：

```text
Scope: adopted v1.0 Option A / nonproduction only
EC01—EC08: SATISFIED WITH DOCUMENTED LIMITATIONS
EC09: BLOCKED
v0.4 / R01—R08: PASS / CLOSED
GR03: SATISFIED WITH DOCUMENTED PROVENANCE LIMITATIONS
GR04: current consumption, rework and v0.4 coverage CLOSED; GR01 retained
B01/B02 research: ACCEPTED / CLOSED / STOPPED
B03: NOT AUTHORIZED / NOT STARTED
Live: HOLD
Activation / Operational Entry: LOCKED
```

状态依据为“协作一”已接受Review：EA reply `0afc38c9-1524-4b6d-9017-24e40790ec83`，GD reply `15e27311-f1fe-41d8-b13c-d50b8ce0a3ce`，v0.4 reply `8e3ef49c-6e50-41f1-b99f-912fb3a9c61a`，B01/B02 reply `4a0321b4-cc81-4e36-98ba-e0c740afd45d`。原生全文和来源保全副本目前在仓库外；本索引不替代它们，不宣称Review独立重算了本地证据。10月14日Review中的咨询状态仅代表当时，当前GR03/GR04以上述10月16日限定接受为准；历史UNKNOWN不追溯补写。

以下为早期核心建设完成记录，不代表v2 Initial Stage退出或当前运行权限：

- 主控 agent 并更新其角色定义；
- 任务书生成、输出审查、BLOCKED 处理、上下文压缩和范围守护（scope_guardian）共 5 个协同 skills；
- 文件驱动协作协议目录 `.codex-coordination/`；
- 项目总控文档与项目范围修正；
- Git 初始化、忽略规则、attributes 属性以及基线提交；
- 最小协同流程文件流转的实测演练；
- 建立多 Agent 确权边界与文件路由协议，并将顾问角色演进为 Gemini 3.5 Flash。
- 新增 `GOVERNANCE PROPOSAL` artifact type；
- 完成 TASK_016 skill layer 通用化整改，并同步到 `origin/master`。

当前允许继续完善：

- 协同 agent；
- 协同 skills 的维护性修正；
- `.codex-coordination/` 协议层与模板的清理；
- 任务状态、回报、审查和返工流程；
- Git 基础治理；
- 已完成任务的运行记录归档与状态对账。

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
  scope_guardian.md

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
.gitattributes
```

`.gitattributes` 已通过 commit `5ad1edc` 纳入版本控制。

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

## 十、当前风险与历史待办限定

1. 固定基线73aa1b0372b45b3ebc2872fce4708b58c5e44b12下保留4个历史untracked，未授权重新纳管或Git变更。
2. GR01实体改规权限及规范优先关系仍未证明，GR02 PREPARED / NOT EFFECTIVE，GR05 NOT SATISFIED，GR06 CURRENT MATRIX REVIEWED / FINAL DISPOSITION PENDING；不能据此关闭EC09或Stage。
3. TASK016的既有完成/接受/提交/推送记载保留，本轮不重新验收其完整生命周期。TASK021旧READY仅为历史待办，当前模板通用化不证明其历史执行或接受。
4. 实际生产来源、RuntimeBinding、Native Process/Channel、真实可信时钟及生产网络资格未获本次新增确认；正式State Journal转换NOT AUTHORIZED / NOT PERFORMED。

---

## 十一、后续工作边界与索引

1. 当前续作路由仅签发文档维护准备TASK `ACOS-V2-CURRENT-PROJECT-STATUS-DOCS-MAINTENANCE-PREP-TASK-01`，允许Playground内准备两份文档的候选文本并送Review；本页不授予正式仓库编辑权限。
2. B01/B02已关闭并停止；没有新的具体有效材料时不重复权限来源研究，也不启动B03。
3. Shadow路线图、P5整合规划及其他设计候选不是实施队列。后续开发、正式仓库编辑和Git动作分别以实际有界TASK与适用决定为准，不从本索引推导许可。
4. 保持既有ACOS/业务项目边界。上述为状态导航，不变更范围规则、生命周期、D5、退出条件或权限结构。

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
