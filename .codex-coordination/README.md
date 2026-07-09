# Codex Coordination Protocol

## 一、用途

本目录用于承载 ChatGPT 与 Codex 的文件驱动协同作业协议。

其目标是将“任务下发—Codex 执行—结果回报—ChatGPT 审查—返工或继续执行”的过程结构化、可追踪、可审查。

本目录不存放项目实例源码，不存放密钥，不存放真实外部服务认证信息。

---

## 二、目录结构

```text
.codex-coordination/
  inbox/
  outbox/
  decisions/
  logs/
  templates/
    task_template.md
    result_template.md
    review_template.md
    decision_template.md
    context_pack_template.md
```

---

## 三、目录说明

### 1. inbox/

用于存放 ChatGPT 生成并交给 Codex 执行的任务书。

每个任务建议使用独立文件，例如：

```text
inbox/TASK_006_CREATE_CODEX_COORDINATION_PROTOCOL_DIR.md
```

### 2. outbox/

用于存放 Codex 执行后的结果回报、BLOCKED 问题、文件清单、验证结果和风险说明。

每个任务建议使用独立结果文件，例如：

```text
outbox/TASK_006_RESULT.md
outbox/TASK_006_BLOCKED.md
```

### 3. decisions/

用于存放 ChatGPT 对 Codex 输出的审查结论、返工指令、继续执行指令或用户决策记录。

每个任务建议使用独立决策文件，例如：

```text
decisions/TASK_006_DECISION.md
```

### 4. logs/

用于存放 Codex 执行过程中产生的测试日志、构建日志或错误日志摘要。

不得存放敏感密钥、账号、token 或个人隐私材料。

### 5. templates/

用于存放标准模板，包括：

* task_template.md
* result_template.md
* review_template.md
* decision_template.md
* context_pack_template.md

---

## 四、任务状态

每个任务应处于以下状态之一：

```text
READY
IN_PROGRESS
BLOCKED
DONE
ACCEPTED
REWORK
CANCELLED
```

状态含义：

* READY：任务已明确，可以交给 Codex 执行；
* IN_PROGRESS：Codex 正在执行；
* BLOCKED：Codex 遇到问题，需要 ChatGPT 或用户决策；
* DONE：Codex 已完成，等待 ChatGPT 审查；
* ACCEPTED：ChatGPT 审查通过；
* REWORK：ChatGPT 要求返工；
* CANCELLED：任务取消。

DONE 不等于 ACCEPTED。

---

## 五、基本流转规则

标准流程：

```text
ChatGPT 生成 TASK
        ↓
TASK 放入 inbox/
        ↓
Codex Executor 执行授权任务
        ↓
Codex Executor 将 RESULT 或 BLOCKED RESULT 写入 outbox/
        ↓
ChatGPT Review 审查结果
        ↓
REVIEW 或 DECISION 写入 decisions/
        ↓
ACCEPTED / REWORK / BLOCKED / CANCELLED / NO_FURTHER_ACTION
```

所有 artifact 必须包含以下路由和权限字段：

```text
ARTIFACT TYPE:
PRODUCER:
TO:
NEXT RECEIVER:
MODE:
PROJECT:
AUTHORITY LIMIT:
FORBIDDEN:
OUTPUT:
```

为保持信息传递明确，`NEXT RECEIVER` 和 `Reason` 应出现在 artifact 输出末尾。

---

## 六、Codex 执行规则

Codex 执行任务时必须遵守：

1. 只处理 inbox 中当前 TASK 指定的任务；
2. 只修改 TASK 授权范围内的文件；
3. 不得删除已有文件，除非 TASK 明确授权；
4. 不得修改依赖文件，除非 TASK 明确授权；
5. 不得编造外部服务配置；
6. 遇到不确定事项必须输出 BLOCKED RESULT；
7. 完成后必须输出 RESULT；
8. 不得自行推进下一任务；
9. 不得输出 REVIEW 或 DECISION；
10. 不得自我验收。

---

## 七、ChatGPT 审查规则

ChatGPT 审查 Codex 输出时应判断：

1. 是否完成任务目标；
2. 是否越权修改；
3. 是否删除文件；
4. 是否修改禁止文件；
5. 是否引入未授权依赖；
6. 是否伪造外部配置；
7. 是否运行必要验证；
8. 是否存在风险；
9. 是否可以 ACCEPTED；
10. 是否需要 REWORK 或 BLOCKED。

---

## 八、安全规则

不得在本目录中保存：

1. 真实 API key；
2. 真实 token；
3. 真实账号密码；
4. 未脱敏个人资料；
5. 未脱敏项目实例资料；
6. 银行卡号、身份证号等敏感信息；
7. 外部服务真实认证参数。

如确需记录配置，应使用占位符，例如：

```text
<API_KEY>
<EXTERNAL_SERVICE_URL>
<AUTH_TOKEN>
```

---

## 九、角色权限边界

允许的 artifact 权限如下：

```text
ChatGPT: TASK / REVIEW / DECISION
Codex Executor: RESULT / BLOCKED RESULT
External Advisory Reviewer: ADVISORY REVIEW only
Automation: RESULT / RECORD only
```

禁止的权限漂移：

1. Codex Executor 不得输出 REVIEW 或 DECISION；
2. Codex Executor 不得自我验收；
3. External Advisory Reviewer 不得执行任务或输出 DECISION；
4. Automation 不得输出 REVIEW 或 DECISION；
5. 任何 artifact 不得伪装 PRODUCER 或 TO。

---

## 十、当前阶段说明

当前目录仅用于建立 ACOS 协同作业协议，不直接实现任何项目实例能力。

具体项目实例的推进应在具体项目窗口中进行；本目录只记录协同协议、任务流转、结果、审查和决策 artifact。
