# Skill: Project Context Compressor

## 一、用途

本 skill 用于将长对话、项目背景、用户目标、已完成任务、当前任务、关键决策、禁止事项、权限边界和 artifact routing 信息，压缩成 Codex 可以直接消费的简洁上下文包。

它服务于 `agents/codex_execution_coordinator.md`，是 ACOS 中的上下文压缩组件。

本 skill 的核心目标，是减少 Codex 在执行任务前需要理解的上下文长度，避免 Codex 因背景过长、信息混杂或任务边界不清而出现误解、越权修改或无效探索。

本 skill 是 provider-neutral 的通用协同能力，不绑定任何具体模型、工具或领域。

---

## 二、适用场景

本 skill 适用于以下场景：

1. 当前对话过长；
2. 项目已经历多轮任务；
3. Codex 需要执行下一任务，但不需要全部历史对话；
4. Codex 出现重复执行旧任务的情况；
5. Codex 混淆当前任务与前序任务；
6. 需要将 ChatGPT 的设计决策转交给 Codex；
7. 需要将项目边界、实例边界或领域限制压缩给 Codex；
8. 需要生成任务前置背景；
9. 需要建立项目阶段总结；
10. 需要把 DONE / ACCEPTED / REWORK / BLOCKED / DECISION 状态整理成任务上下文；
11. 需要在上下文包中明确下一接收方和信息传递理由。

---

## 三、不适用场景

本 skill 不用于：

1. 生成完整 Codex 任务书，此时应使用 `codex_task_writer.md`；
2. 审查 Codex 输出，此时应使用 `codex_output_reviewer.md`；
3. 处理 BLOCKED 问题，此时应使用 `codex_blocker_resolver.md`；
4. 替 Codex 扩大任务范围；
5. 替 Codex 生成领域结论或实例策略；
6. 将未经确认的信息写成项目既定事实；
7. 压缩掉关键禁止事项、权限边界和验收标准；
8. 把上下文包当成执行授权、REVIEW 或 DECISION。

---

## 四、输入信息

使用本 skill 前，应尽量收集以下信息：

1. 用户原始目标；
2. 当前项目阶段；
3. 已完成任务；
4. 已验收任务；
5. 正在执行任务；
6. 待执行任务；
7. 关键设计决策；
8. 文件结构；
9. 任务状态；
10. 当前风险；
11. `.git` 或 diff 审查限制；
12. 项目边界、实例边界或领域限制；
13. Artifact Routing 元数据；
14. 角色权限边界；
15. Codex 禁止事项；
16. 本轮任务只需要知道的最小背景；
17. 不应传给 Codex 的冗余信息。

---

## 五、输出目标

本 skill 应输出一份 `Project Context Pack for Codex`。

该上下文包应做到：

1. 简洁；
2. 准确；
3. 只包含本轮任务相关背景；
4. 区分已确认事实和待确认事项；
5. 明确当前任务状态；
6. 明确已完成文件；
7. 明确禁止事项；
8. 明确项目边界、权限边界和路由边界；
9. 明确 Codex 只能输出 RESULT 或 BLOCKED RESULT；
10. 避免重复长篇历史对话；
11. 避免让 Codex 误以为旧任务仍需执行。

上下文包是辅助 artifact。它不能替代 TASK、REVIEW、DECISION 或用户授权。

---

## 六、上下文包标准格式

输出上下文包时，应使用以下结构：

```markdown
# Project Context Pack for Codex

ARTIFACT TYPE:
CONTEXT PACK

PRODUCER:
ChatGPT

TO:
Codex Executor

MODE:
CONTEXT

PROJECT:
[项目路径或项目名称]

AUTHORITY LIMIT:
[本上下文包只提供背景，不扩大 Codex 授权]

FORBIDDEN:
[本轮仍然禁止的事项]

OUTPUT:
CONTEXT PACK

## 1. Project Goal

[项目总体目标]

## 2. Project / Instance Boundary

1. 
2. 
3. 

## 3. Current Phase

[当前阶段]

## 4. Completed and Accepted Tasks

- [TASK_ID]：[结果]

## 5. Current Task

[TASK_ID + 本轮只做什么]

## 6. Relevant Files

- [本轮相关文件]

## 7. Key Decisions

1. 
2. 
3. 

## 8. Artifact Routing and Authority Context

1. 
2. 
3. 

## 9. Allowed Scope for Current Task

- 

## 10. Forbidden Actions

1. 
2. 
3. 

## 11. Known Risks

1. 
2. 
3. 

## 12. What Codex Should Ignore

1. 
2. 
3. 

## 13. Expected Output

[Codex 本轮应输出什么]

## NEXT RECEIVER

[ChatGPT Review / Codex Executor / User Decision / External Advisory Reviewer / None]

## Reason

[说明为什么交给该接收方]
```

NEXT RECEIVER 和 Reason 必须保留在输出末尾，用于明确信息传递对象。

---

## 七、压缩原则

### 1. 保留任务相关信息

应保留：

1. 当前任务目标；
2. 允许操作范围；
3. 禁止事项；
4. 已完成且会影响当前任务的文件；
5. 项目边界、实例边界或领域限制；
6. Artifact Routing 元数据；
7. 角色权限边界；
8. 验收标准；
9. BLOCKED 规则；
10. 已知风险。

### 2. 删除无关历史讨论

应删除：

1. 已经完成且与当前任务无关的长篇说明；
2. 重复的任务书内容；
3. 用户与 ChatGPT 的探索性讨论；
4. 不影响当前任务的领域讨论；
5. 不影响当前任务的技术设想；
6. 已被否定的方案；
7. Codex 不需要知道的聊天过程。

### 3. 区分事实和判断

上下文包应区分：

1. 已完成事实；
2. Codex 自述事实；
3. ChatGPT 条件验收；
4. 待确认风险；
5. 用户明确要求；
6. 暂未执行事项。

不得把“Codex 声称完成”直接写成“已经实质审查通过”，除非已审查文件内容或 diff。

### 4. 保留任务边界

压缩后仍必须保留：

1. 本轮只做什么；
2. 本轮不做什么；
3. 哪些文件不得修改；
4. 遇到什么情况必须 BLOCKED；
5. 完成后如何回报；
6. 输出末尾的 NEXT RECEIVER 和 Reason。

### 5. 保留角色和权限边界

压缩包必须保留：

1. ChatGPT 负责 TASK / REVIEW / DECISION；
2. Codex 只能执行授权任务并输出 RESULT / BLOCKED RESULT；
3. External Advisory Reviewer 只能输出 ADVISORY REVIEW；
4. Codex 不得自行验收；
5. Codex 不得伪装其他主体；
6. 需要用户授权、凭证或人类判断时，应交给 User Decision。

### 6. 保留项目和实例边界

如果当前任务发生在 ACOS 中，压缩包必须明确：

1. ACOS 是项目无关的协同基础设施；
2. 本轮只修正协同系统；
3. 具体项目推进应在具体项目窗口中进行；
4. 不得把项目实例规则写入 ACOS 核心层；
5. 不得把 ACOS 协同协议误写入项目实例，除非用户明确授权 local ACOS instance mode。

如果当前任务发生在项目实例中，压缩包必须明确：

1. 该项目只是 ACOS 的使用者；
2. Codex 只能处理该项目已授权范围；
3. 未授权领域规则、实例策略或验收口径不应由 Codex 自行决定；
4. 不确定时应 BLOCKED。

---

## 八、当前项目默认上下文摘要

在本项目中，默认项目目标为：

```text
构建 ACOS（AI Collaboration Operating System），使 ChatGPT 负责规划、任务设计、审查和最终决策，Codex 作为唯一执行者负责授权范围内的文件修改、命令执行、Git 操作和结果回报，External Advisory Reviewer 只提供非执行性 ADVISORY REVIEW。
```

当前协同机制优先建立以下构件：

1. `agents/codex_execution_coordinator.md`
2. `skills/codex_task_writer.md`
3. `skills/codex_output_reviewer.md`
4. `skills/codex_blocker_resolver.md`
5. `skills/project_context_compressor.md`
6. `.codex-coordination/` 文件协议目录

本项目只修正 ACOS。具体项目推进必须在具体项目窗口中进行，不应混入本仓库。

---

## 九、上下文压缩示例

示例输出：

```markdown
# Project Context Pack for Codex

ARTIFACT TYPE:
CONTEXT PACK

PRODUCER:
ChatGPT

TO:
Codex Executor

MODE:
CONTEXT

PROJECT:
/Users/zhang/Documents/chatgpt-codex-coordination-system

AUTHORITY LIMIT:
This context pack only summarizes accepted ACOS scope and does not authorize extra file edits.

FORBIDDEN:
Do not modify project instances, do not stage, do not commit, do not push, and do not change files outside the current task.

OUTPUT:
CONTEXT PACK

## 1. Project Goal

建立 ACOS。ChatGPT 负责 TASK / REVIEW / DECISION；Codex 负责授权范围内的执行并输出 RESULT / BLOCKED RESULT；External Advisory Reviewer 只能输出 ADVISORY REVIEW。

## 2. Project / Instance Boundary

本轮只处理 ACOS 仓库。具体项目推进必须在具体项目窗口中进行。

## 3. Current Phase

Skill layer genericization is in progress.

## 4. Completed and Accepted Tasks

- TASK_016A：accepted, genericized `skills/codex_task_writer.md`.
- TASK_016B：accepted, genericized `skills/codex_output_reviewer.md`.
- TASK_016C：accepted, genericized `skills/codex_blocker_resolver.md`.

## 5. Current Task

TASK_016D：only rework `skills/project_context_compressor.md`.

## 6. Relevant Files

- `skills/project_context_compressor.md`

## 7. Key Decisions

1. One skill is reworked per task lifecycle.
2. Codex must not self-review or produce DECISION.
3. Context packs do not expand execution authority.

## 8. Artifact Routing and Authority Context

1. Codex outputs RESULT or BLOCKED RESULT only.
2. ChatGPT Review decides ACCEPTED / REWORK / BLOCKED.
3. NEXT RECEIVER and Reason must appear at the end of the output.

## 9. Allowed Scope for Current Task

- Modify `skills/project_context_compressor.md` only.

## 10. Forbidden Actions

1. Do not modify core governance files.
2. Do not modify project instances.
3. Do not run git add / commit / push.
4. Do not create files.

## 11. Known Risks

1. Other accepted skill edits may still be uncommitted.
2. Existing unrelated worktree changes must remain isolated.

## 12. What Codex Should Ignore

1. Do not handle other modified files.
2. Do not continue into the next task.
3. Do not sync remote state.

## 13. Expected Output

RESULT with modified file, summary, diff stat, git status, and routing.

## NEXT RECEIVER

ChatGPT Review

## Reason

TASK_016D must be reviewed before any commit or next task.
```

---

## 十、常见压缩错误

不得出现以下错误：

1. 把旧任务当成本轮任务；
2. 把尚未执行的任务写成已完成；
3. 把条件验收写成无保留验收；
4. 删除禁止事项；
5. 删除项目边界、实例边界或权限边界；
6. 删除 `.git` 风险；
7. 把多个任务合并给 Codex；
8. 让 Codex 自行选择下一步；
9. 让 Codex 自行处理领域判断；
10. 将用户探索性想法写成既定项目规则；
11. 省略 Artifact Routing 元数据；
12. 省略输出末尾的 NEXT RECEIVER 和 Reason。

---

## 十一、输出风格要求

上下文包应：

1. 直接；
2. 简洁；
3. 准确；
4. 以文件路径和任务状态为核心；
5. 避免长篇解释；
6. 避免重复历史对话；
7. 保留操作边界；
8. 保留风险提示；
9. 保留 artifact routing 元数据；
10. 可直接复制给 Codex；
11. 能防止 Codex 执行错任务。

---

## 十二、最终目标

本 skill 的最终目标，是让 ChatGPT 在长项目协作中稳定生成 Codex 可理解的最小上下文，降低 Codex 重复执行、误解任务、越权修改和消耗额度的风险。

上下文压缩不是简单摘要，而是面向 Codex 执行的任务背景控制。
