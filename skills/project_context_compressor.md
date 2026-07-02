# Skill: Project Context Compressor

## 一、用途

本 skill 用于将长对话、项目背景、用户目标、已完成任务、当前任务、关键决策、禁止事项和法律业务边界，压缩成 Codex 可以直接消费的简洁上下文包。

它服务于 `agents/codex_execution_coordinator.md`，是 ChatGPT-Codex 协同作业机制中的上下文压缩组件。

本 skill 的核心目标，是减少 Codex 在执行任务前需要理解的上下文长度，避免 Codex 因背景过长、信息混杂或任务边界不清而出现误解、越权修改或无效探索。

---

## 二、适用场景

本 skill 适用于以下场景：

1. 当前对话过长；
2. 项目已经历多轮任务；
3. Codex 需要执行下一任务，但不需要全部历史对话；
4. Codex 出现重复执行旧任务的情况；
5. Codex 混淆当前任务与前序任务；
6. 需要将 ChatGPT 的设计决策转交给 Codex；
7. 需要将法律业务边界压缩给 Codex；
8. 需要生成任务前置背景；
9. 需要建立项目阶段总结；
10. 需要把 DONE / ACCEPTED / REWORK / BLOCKED 状态整理成任务上下文。

---

## 三、不适用场景

本 skill 不用于：

1. 生成完整 Codex 任务书，此时应使用 `codex_task_writer.md`；
2. 审查 Codex 输出，此时应使用 `codex_output_reviewer.md`；
3. 处理 BLOCKED 问题，此时应使用 `codex_blocker_resolver.md`；
4. 替 Codex 扩大任务范围；
5. 替 Codex 生成法律结论；
6. 将未经确认的信息写成项目既定事实；
7. 压缩掉关键禁止事项和验收标准。

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
12. 法律业务边界；
13. Codex 禁止事项；
14. 本轮任务只需要知道的最小背景；
15. 不应传给 Codex 的冗余信息。

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
8. 明确法律业务边界；
9. 避免重复长篇历史对话；
10. 避免让 Codex 误以为旧任务仍需执行。

---

## 六、上下文包标准格式

输出上下文包时，应使用以下结构：

```markdown
# Project Context Pack for Codex

## 1. Project Goal

[项目总体目标]

## 2. Current Phase

[当前阶段]

## 3. Completed and Accepted Tasks

- [TASK_ID]：[结果]

## 4. Current Task

[TASK_ID + 本轮只做什么]

## 5. Existing Files

- [已存在关键文件]

## 6. Key Decisions

1. 
2. 
3. 

## 7. Legal Business Boundaries

1. 
2. 
3. 

## 8. Allowed Scope for Current Task

- 

## 9. Forbidden Actions

1. 
2. 
3. 

## 10. Known Risks

1. 
2. 
3. 

## 11. What Codex Should Ignore

1. 
2. 
3. 

## 12. Expected Output

[Codex 本轮应输出什么]
```

---

## 七、压缩原则

### 1. 保留任务相关信息

应保留：

1. 当前任务目标；
2. 允许操作范围；
3. 禁止事项；
4. 已完成且会影响当前任务的文件；
5. 法律业务边界；
6. 验收标准；
7. BLOCKED 规则；
8. 已知风险。

### 2. 删除无关历史讨论

应删除：

1. 已经完成且与当前任务无关的长篇说明；
2. 重复的任务书内容；
3. 用户与 ChatGPT 的探索性讨论；
4. 不影响当前任务的法律案例讨论；
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
5. 完成后如何回报。

### 5. 保留法律业务边界

如果项目涉及中国民商事争议解决和民事执行，压缩包必须保留：

1. Codex 不得编造法律依据；
2. Codex 不得编造案例；
3. Codex 不得自行归纳浙江地区裁判规则；
4. Codex 不得将诉讼策略写成确定结论；
5. 材料不足时应写明待补证或待确认；
6. 法律判断由 ChatGPT 或用户决策，Codex 只负责落地。

---

## 八、当前项目默认上下文摘要

在本项目中，默认项目目标为：

```text
构建一套 ChatGPT-Codex 协同作业机制，使 ChatGPT 负责规划、架构、任务拆解、法律业务判断、审查和返工决策，Codex 负责局部文件创建、修改、测试和回报。
```

当前协同机制优先建立以下构件：

1. `agents/codex_execution_coordinator.md`
2. `skills/codex_task_writer.md`
3. `skills/codex_output_reviewer.md`
4. `skills/codex_blocker_resolver.md`
5. `skills/project_context_compressor.md`
6. `.codex-coordination/` 文件协议目录

在上述构件完成前，不应直接开发复杂法律业务模块。

---

## 九、上下文压缩示例

示例输出：

```markdown
# Project Context Pack for Codex

## 1. Project Goal

建立 ChatGPT-Codex 协同作业机制。ChatGPT 负责规划、任务拆解、审查、返工和法律业务判断；Codex 负责小步执行、文件创建、测试和回报。

## 2. Current Phase

正在创建协同机制的基础 agent / skills，尚未进入具体法律业务模块开发。

## 3. Completed and Accepted Tasks

- TASK_001：已条件验收，创建 `agents/codex_execution_coordinator.md`。
- TASK_002：已条件验收，创建 `skills/codex_task_writer.md`。
- TASK_003：已条件验收，创建 `skills/codex_output_reviewer.md`。
- TASK_004：已条件验收，创建 `skills/codex_blocker_resolver.md`。

## 4. Current Task

TASK_005：只创建 `skills/project_context_compressor.md`。

## 5. Existing Files

- `agents/codex_execution_coordinator.md`
- `skills/codex_task_writer.md`
- `skills/codex_output_reviewer.md`
- `skills/codex_blocker_resolver.md`

## 6. Key Decisions

1. 每次只给 Codex 一个小任务。
2. Codex 遇到不确定事项必须 BLOCKED。
3. ChatGPT 负责法律业务判断和验收。
4. 当前不处理 `.git` 问题。

## 7. Legal Business Boundaries

1. Codex 不得编造法律依据或案例。
2. Codex 不得自行确定诉讼策略。
3. 法律业务逻辑由 ChatGPT 或用户确认后再落地。

## 8. Allowed Scope for Current Task

- 新增 `skills/project_context_compressor.md`

## 9. Forbidden Actions

1. 不得修改已有文件。
2. 不得创建其他 skill 或 agent。
3. 不得创建 `.codex-coordination/`。
4. 不得处理 `.git` 问题。
5. 不得引入依赖。

## 10. Known Risks

1. `.git` 当前不可用，后续 diff 审查受影响。
2. 前序任务均为条件验收，尚未逐行审查完整文件内容。

## 11. What Codex Should Ignore

1. 不要重复创建前序文件。
2. 不要处理法律业务模块。
3. 不要处理 Git 问题。
4. 不要创建协作目录协议。

## 12. Expected Output

完成后回报新增文件、修改文件、删除文件、验证方式、测试结果、潜在风险和下一步建议。
```

---

## 十、常见压缩错误

不得出现以下错误：

1. 把旧任务当成本轮任务；
2. 把尚未执行的任务写成已完成；
3. 把条件验收写成无保留验收；
4. 删除禁止事项；
5. 删除法律业务边界；
6. 删除 `.git` 风险；
7. 把多个任务合并给 Codex；
8. 让 Codex 自行选择下一步；
9. 让 Codex 自行处理法律判断；
10. 将用户探索性想法写成既定项目规则。

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
9. 可直接复制给 Codex；
10. 能防止 Codex 执行错任务。

---

## 十二、最终目标

本 skill 的最终目标，是让 ChatGPT 在长项目协作中稳定生成 Codex 可理解的最小上下文，降低 Codex 重复执行、误解任务、越权修改和消耗额度的风险。

上下文压缩不是简单摘要，而是面向 Codex 执行的任务背景控制。
