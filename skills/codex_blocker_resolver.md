# Skill: Codex Blocker Resolver

## 一、用途

本 skill 用于处理 Codex 在执行任务过程中提出的 BLOCKED 问题。

它服务于 `agents/codex_execution_coordinator.md`，是 ChatGPT-Codex 协同作业机制中的中断决策组件。

本 skill 的核心目标，是在 Codex 遇到路径冲突、权限边界不明、同名文件、项目结构不一致、技术方案选择、外部配置不确定、未授权领域规则或业务逻辑不确定等问题时，由 ChatGPT 对问题进行判断，并给出明确、可执行、边界清楚的继续指令。

本 skill 不鼓励 Codex 自行决定不确定事项。相反，它要求 Codex 在不确定时暂停，并把问题结构化提交给 ChatGPT。

---

## 二、适用场景

本 skill 适用于以下场景：

1. Codex 回报任务状态为 BLOCKED；
2. Codex 发现目标文件已存在；
3. Codex 发现目录结构与任务书不一致；
4. Codex 需要修改未授权文件才能完成任务；
5. Codex 发现已有项目规范与任务书冲突；
6. Codex 面临多个技术实现路径；
7. Codex 无法判断是否应覆盖、迁移、重命名或删除文件；
8. Codex 需要确认外部工具、API、环境变量、认证方式等外部配置；
9. Codex 对未授权领域规则或业务逻辑不确定；
10. Codex 执行测试失败，但无法判断是否应修复；
11. Codex 发现任务书存在矛盾、遗漏或不可执行之处；
12. 用户需要 ChatGPT 对 Codex 的可选方案进行决策。

---

## 三、不适用场景

本 skill 不用于：

1. Codex 已经明确 DONE 且无阻塞事项；
2. 审查 Codex 输出质量，此时应使用 `codex_output_reviewer.md`；
3. 生成新的 Codex 任务书，此时应使用 `codex_task_writer.md`；
4. 让 Codex 自行扩大任务范围；
5. 让 Codex 自行决定未授权领域规则或业务逻辑；
6. 在缺少用户关键授权时强行继续执行；
7. 绕过安全边界处理高风险操作。

---

## 四、输入信息

处理 BLOCKED 问题前，应尽量取得以下信息：

1. 原始 Codex 任务书；
2. 当前任务 ID；
3. Codex 已完成内容；
4. 卡点描述；
5. 涉及文件或目录；
6. Codex 提出的可选方案；
7. Codex 的初步判断；
8. Codex 需要 ChatGPT 决策的问题；
9. 当前项目结构；
10. 是否存在同名文件；
11. 是否涉及未授权文件；
12. 是否涉及依赖、配置、环境变量或外部服务；
13. 是否涉及未授权领域规则或业务逻辑；
14. 是否涉及删除、覆盖、重命名、迁移或大范围重构。

如果缺少关键信息，应优先要求 Codex 补充，不应直接授权继续。

---

## 五、BLOCKED 问题标准格式

Codex 提出 BLOCKED 时，应要求其使用以下格式：

```markdown
# Codex 执行中断问题

ARTIFACT TYPE:
BLOCKED RESULT

PRODUCER:
Codex Executor

TO:
ChatGPT Review

MODE:
BLOCKED

PROJECT:
[项目路径或项目名称]

AUTHORITY LIMIT:
[Codex 当前授权边界]

FORBIDDEN:
[Codex 当前不得继续的事项]

OUTPUT:
BLOCKED RESULT

## 1. 当前任务

## 2. 已完成内容

## 3. 卡点描述

## 4. 涉及文件

## 5. 可选方案

### 方案 A

### 方案 B

### 方案 C

## 6. Codex 初步判断

## 7. 需要 ChatGPT 决策的问题

## 8. NEXT RECEIVER

## 9. Reason
```

NEXT RECEIVER 和 Reason 必须保留在输出末尾，用于明确信息传递对象。

如果 Codex 没有按上述格式提交，应要求其补充，而不是直接决策。

---

## 六、处理原则

### 1. 最小修改原则

优先选择对项目影响最小的方案。

排序通常为：

1. 新增独立文件；
2. 修改明确授权文件；
3. 增加占位说明；
4. 局部补充现有文档；
5. 修改配置文件；
6. 重命名或迁移文件；
7. 删除文件；
8. 大范围重构。

除非用户明确授权，原则上不得选择删除、大范围迁移或重构方案。

### 2. 保护已有项目原则

如果 Codex 发现已有文件、已有规范或已有目录结构，应优先保护已有内容。

不得轻易覆盖已有文件。

如目标文件已存在，优先选择：

1. 读取并报告该文件摘要；
2. 询问是否合并；
3. 创建备选文件；
4. 生成补丁建议；
5. 暂停等待用户确认。

不得直接覆盖。

### 3. 授权边界原则

如果继续执行需要修改未授权文件，应当：

1. 判断该修改是否确有必要；
2. 如果不必要，要求 Codex 回到原任务范围；
3. 如果必要，明确新增授权范围；
4. 限定只修改具体文件；
5. 要求 Codex 回报具体 diff 或内容摘要。

不得使用“可以修改相关文件”这类模糊授权。

### 4. 不确定配置不编造原则

涉及以下内容时，不得让 Codex 编造：

1. API 地址；
2. 外部工具或服务地址；
3. 密钥；
4. token；
5. 环境变量名；
6. 认证方式；
7. 第三方服务参数；
8. 未确认的框架配置。

如果真实信息缺失，应使用占位符或说明文档，并明确“需用户提供真实配置”。

### 5. Domain-specific judgment preservation principle

涉及任何未授权领域规则、业务逻辑、外部知识体系、领域数据、专用工作流、专门工具或外部服务时，Codex 不得自行决策。

常见情形包括：

1. 领域规则或业务逻辑不明确；
2. 外部依据、示例数据或服务能力未经确认；
3. 地域、行业、组织或专用流程规则需要确认；
4. 策略、判断标准或验收口径存在多种可能；
5. 任务需要用户授权、凭证、真实配置或人类判断；
6. 领域结论可能影响后续项目方向或风险承担。

处理方式：

1. ChatGPT 或 User Decision 给出明确判断；
2. Codex 只负责按判断落地授权范围内的内容；
3. 不确定时继续 BLOCKED；
4. 不得将未经确认的领域策略或业务逻辑写成确定结论。

### 6. 测试失败处理原则

如果 Codex 因测试失败 BLOCKED，应先区分：

1. 测试失败是否与本任务有关；
2. 失败是否在授权文件范围内可修复；
3. 是否需要修改未授权文件；
4. 是否是环境问题；
5. 是否是历史遗留问题。

处理规则：

1. 与本任务无关：记录风险，不要求本轮修复；
2. 与本任务有关且在授权范围内：允许局部修复；
3. 与本任务有关但超出授权范围：继续 BLOCKED；
4. 环境问题：要求 Codex 记录日志，不擅自修改环境；
5. 历史遗留问题：单独创建后续任务，不在当前任务中扩大处理。

---

## 七、决策类型

BLOCKED 问题处理结果应归入以下类型之一：

```text
CONTINUE_AS_PLANNED
CONTINUE_WITH_LIMITED_SCOPE
EXPAND_SCOPE
REWORK_TASK
REQUEST_MORE_INFO
USER_DECISION_REQUIRED
CANCEL_TASK
```

### 1. CONTINUE_AS_PLANNED

原任务书足够明确，要求 Codex 按原任务继续。

适用情形：

1. Codex 过度谨慎；
2. 问题不影响任务；
3. 无需扩大修改范围；
4. 无需用户决策。

### 2. CONTINUE_WITH_LIMITED_SCOPE

允许 Codex 继续，但进一步收窄操作范围。

适用情形：

1. 存在风险但可控；
2. 只允许处理部分文件；
3. 明确禁止处理其他问题。

### 3. EXPAND_SCOPE

允许 Codex 扩大操作范围，但必须具体列明新增授权文件。

适用情形：

1. 不扩大范围无法完成任务；
2. 新增修改范围风险可控；
3. 用户或 ChatGPT 已明确授权。

### 4. REWORK_TASK

当前任务书需要调整，生成新的返工或修正任务。

适用情形：

1. 原任务书有遗漏；
2. 任务目标表述不清；
3. 需要重新定义验收标准；
4. Codex 已完成部分内容但方向需要修正。

### 5. REQUEST_MORE_INFO

当前信息不足，要求 Codex 补充。

适用情形：

1. 缺少文件清单；
2. 缺少错误日志；
3. 缺少项目结构；
4. 缺少同名文件内容摘要；
5. 缺少可选方案具体影响。

### 6. USER_DECISION_REQUIRED

需要用户亲自决策。

适用情形：

1. 是否覆盖已有文件；
2. 是否删除文件；
3. 是否修改核心配置；
4. 是否接入外部服务；
5. 是否使用真实密钥或账号；
6. 是否改变项目架构；
7. 是否处理领域策略、业务逻辑或项目方向上的重大选择。

### 7. CANCEL_TASK

当前任务取消。

适用情形：

1. 任务目标已无必要；
2. 任务与项目方向冲突；
3. 风险明显超过收益；
4. 用户取消任务。

---

## 八、BLOCKED 答复格式

处理 BLOCKED 问题时，应使用以下格式：

```markdown
# BLOCKED 问题答复

ARTIFACT TYPE:
REVIEW / DECISION

PRODUCER:
ChatGPT

TO:
Codex Executor / User Decision

MODE:
BLOCKED RESOLUTION

PROJECT:
[项目路径或项目名称]

AUTHORITY LIMIT:
[允许继续的范围和边界]

FORBIDDEN:
[仍然禁止的事项]

OUTPUT:
REVIEW / DECISION

## 一、结论

决策类型：[CONTINUE_AS_PLANNED / CONTINUE_WITH_LIMITED_SCOPE / EXPAND_SCOPE / REWORK_TASK / REQUEST_MORE_INFO / USER_DECISION_REQUIRED / CANCEL_TASK]

选择方案：

## 二、理由

1. 
2. 
3. 

## 三、允许继续操作范围

允许：

- 

## 四、禁止事项

1. 
2. 
3. 

## 五、更新后的执行指令

1. 
2. 
3. 

## 六、更新后的验收标准

1. 
2. 
3. 

## 七、风险提示

1. 
2. 
3. 

## NEXT RECEIVER

[ChatGPT Review / Codex Executor / User Decision / External Advisory Reviewer / None]

## Reason

[说明为什么交给该接收方]
```

---

## 九、常见 BLOCKED 场景处理

### 1. 目标文件已存在

默认处理：

1. 不允许覆盖；
2. 要求 Codex 读取并摘要已有文件；
3. 由 ChatGPT 判断是合并、改名、保留还是返工。

答复示例：

```markdown
# BLOCKED 问题答复

## 一、结论

决策类型：REQUEST_MORE_INFO

选择方案：暂不覆盖目标文件。

## 二、理由

目标文件已存在，直接覆盖可能破坏已有内容。

## 三、允许继续操作范围

允许 Codex 只读取并摘要该文件内容。

## 四、禁止事项

1. 不得覆盖该文件；
2. 不得删除该文件；
3. 不得修改其他文件。

## 五、更新后的执行指令

请输出该文件的章节结构、核心内容摘要、与本任务要求的差异。
```

### 2. 需要修改未授权文件

默认处理：

1. 不允许直接修改；
2. 要求说明为什么必须修改；
3. 若必要，由 ChatGPT 明确追加授权。

### 3. 项目已有不同规范

默认处理：

1. 优先保留已有规范；
2. 要求 Codex 摘要现有规范；
3. ChatGPT 判断是否沿用、兼容或新建。

### 4. 外部配置不明确

默认处理：

1. 不编造；
2. 使用占位符；
3. 写明需用户提供；
4. 不修改真实 `.env`。

### 5. Domain-specific logic uncertain

默认处理：

1. Codex 暂停；
2. ChatGPT 或 User Decision 给出领域或业务判断；
3. Codex 只负责落地；
4. 如材料不足，写成“待确认”或“需补充信息”，不得写成定论。

### 6. 测试失败

默认处理：

1. 要求 Codex 提供失败命令和日志；
2. 判断是否与本任务有关；
3. 不允许大范围修复；
4. 必要时创建单独修复任务。

---

## 十、返工衔接规则

如果 BLOCKED 处理结果需要返工，应生成新的返工任务，而不是让 Codex 自由继续。

返工任务应包含：

1. 返工原因；
2. 允许修改文件；
3. 禁止修改文件；
4. 具体修改要求；
5. 更新后的验收标准；
6. DONE 回报格式。

---

## 十一、Domain-specific BLOCKED format

如果 Codex 因未授权领域规则或业务逻辑不确定而 BLOCKED，应要求其按以下格式提问：

```markdown
# Domain-specific logic BLOCKED

ARTIFACT TYPE:
BLOCKED RESULT

PRODUCER:
Codex Executor

TO:
ChatGPT Review

MODE:
BLOCKED

PROJECT:
[项目路径或项目名称]

AUTHORITY LIMIT:
[Codex 当前授权边界]

FORBIDDEN:
[Codex 当前不得继续的事项]

OUTPUT:
BLOCKED RESULT

## 1. 当前任务

## 2. 不确定的领域或业务问题

## 3. 涉及的模块、数据、工具或流程

例如：领域规则 / 业务流程 / 外部工具 / 数据来源 / 认证配置 / 验收口径 / 用户授权

## 4. Codex 不确定的原因

## 5. 可选处理方式

### 方案 A

### 方案 B

### 方案 C

## 6. 需要 ChatGPT 决策的问题

## 7. NEXT RECEIVER

## 8. Reason
```

ChatGPT 答复时，应明确：

1. 采用哪种方案；
2. 为什么；
3. 是否需要保留风险提示；
4. 是否需要写入假设、替代解释或反向风险；
5. 是否需要写入待确认事项或后续验证清单；
6. 哪些内容不得写成定论。

---

## 十二、高风险 BLOCKED 信号

出现以下情况时，原则上不得直接允许继续：

1. Codex 请求删除文件；
2. Codex 请求覆盖已有文件；
3. Codex 请求修改依赖文件；
4. Codex 请求修改 `.env`；
5. Codex 请求修改 Git 配置；
6. Codex 请求自动提交；
7. Codex 请求自动部署；
8. Codex 请求接入真实外部账号；
9. Codex 请求写入真实密钥；
10. Codex 请求大范围重构；
11. Codex 请求合并多个任务；
12. Codex 请求自行决定未授权领域规则或业务逻辑；
13. Codex 请求跳过 ChatGPT Review 或 User Decision；
14. Codex 请求把 BLOCKED 输出路由给自己验收。

---

## 十三、可直接继续的低风险 BLOCKED

以下情形可在明确边界后继续：

1. 目标目录不存在，需要创建目录；
2. Markdown 文件创建任务未涉及已有文件；
3. Codex 只是需要确认是否可以创建父目录；
4. 文件存在性检查失败但原因明确；
5. 测试未运行但任务仅为文档创建；
6. 日志路径不存在，需要创建授权范围内的日志目录；
7. 占位配置文件需要使用 placeholder。

---

## 十四、输出风格要求

BLOCKED 答复应当：

1. 直接给结论；
2. 明确选择方案；
3. 明确允许范围；
4. 明确禁止事项；
5. 不使用模糊授权；
6. 不让 Codex 自行判断关键问题；
7. 如果需要用户决策，明确暂停；
8. 如果可以继续，给出可执行步骤；
9. 如果需要返工，生成返工任务；
10. 如果信息不足，明确要求补充什么。

---

## 十五、最终目标

本 skill 的最终目标，是让 Codex 在遇到不确定事项时不再自由发挥，而是通过结构化 BLOCKED 机制，把问题交给 ChatGPT 或用户决策。

协同作业的稳定性来自三个规则：

1. 不确定就暂停；
2. 决策要结构化；
3. 继续执行必须有边界。
