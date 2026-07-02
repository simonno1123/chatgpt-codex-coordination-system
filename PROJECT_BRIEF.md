# Project Brief

## 一、项目目标

本项目旨在建立一套 ChatGPT-Codex 协同作业机制，使 ChatGPT 负责项目规划、架构设计、任务拆解、法律业务判断、Codex 输出审查和返工决策，Codex 负责局部文件创建、修改、测试、报错回报和执行结果整理。

当前阶段的重点不是直接开发具体法律业务模块，而是先建立稳定、可控、可审查的协同开发基础设施。

---

## 二、当前阶段

当前阶段：ChatGPT-Codex 协同作业基础层建设。

已完成：

- 主控 agent；
- 任务书生成 skill；
- 输出审查 skill；
- BLOCKED 处理 skill；
- 上下文压缩 skill；
- 文件驱动协作协议目录。

暂未进入：

- 民事执行财产线索 agent；
- 银行流水分析 skill；
- 公司人格否认与实控人责任 agent；
- 证据审查 agent；
- 北大法宝 MCP 占位配置；
- 法律业务输出模板；
- 测试样例。

---

## 三、ChatGPT 职责

ChatGPT 负责：

1. 理解用户目标；
2. 制定项目架构；
3. 拆解 Codex 可执行任务；
4. 生成 Codex 任务书；
5. 控制 Codex 修改范围；
6. 处理 Codex BLOCKED 问题；
7. 审查 Codex DONE 回报；
8. 判断 ACCEPTED / REWORK / BLOCKED；
9. 生成返工任务；
10. 决定法律业务逻辑；
11. 维护项目方向和边界。

---

## 四、Codex 职责

Codex 负责：

1. 按任务书创建文件；
2. 按任务书修改文件；
3. 按任务书运行测试；
4. 输出新增、修改、删除文件清单；
5. 输出验证方式；
6. 输出测试结果；
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

* READY：任务已明确，可以交给 Codex 执行；
* IN_PROGRESS：Codex 正在执行；
* BLOCKED：Codex 遇到问题，需要 ChatGPT 或用户决策；
* DONE：Codex 已完成，等待 ChatGPT 审查；
* ACCEPTED：ChatGPT 审查通过；
* REWORK：ChatGPT 要求返工；
* CANCELLED：任务取消。

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
```

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
8. 不得自行处理法律业务判断。
9. 不得自行推进下一任务。
10. DONE 后等待 ChatGPT 审查。

---

## 九、法律业务边界

本项目后续将面向中国民商事争议解决和民事执行场景。

涉及以下内容时，Codex 不得自行作出法律判断：

1. 民事执行财产线索；
2. 银行流水分析；
3. 公司人格否认；
4. 实控人责任；
5. 股东损害债权人利益；
6. 债权人撤销权；
7. 执行异议之诉；
8. 代位析产；
9. 履行能力分析；
10. 职务行为或表见代理；
11. 证据三性；
12. 类案裁判规则；
13. 浙江地区司法实践；
14. 诉讼请求设计；
15. 调查令申请范围。

法律业务文件应保留：

1. 事实梳理；
2. 证据评价；
3. 法律依据；
4. 裁判风险；
5. 反方抗辩；
6. 诉讼策略；
7. 补证清单；
8. 文书表达建议。

---

## 十、当前风险

1. `.git` 当前不能被识别为有效仓库，后续 diff 审查会受到影响。
2. 前序文件多为条件验收，尚未逐行审查完整内容。
3. 当前尚未创建具体法律业务模块。
4. 当前尚未建立测试样例。
5. 当前尚未接入任何外部 MCP 或 API。

---

## 十一、后续优先级

建议后续按以下顺序推进：

1. 创建 `PROJECT_BRIEF.md` 和 `TASKS.md`；
2. 单独诊断 `.git` 问题；
3. 创建法律业务基础目录；
4. 创建民事执行财产线索 agent；
5. 创建银行流水分析 skill；
6. 创建公司人格否认与实控人责任 agent；
7. 创建证据审查 agent；
8. 创建北大法宝 MCP 占位配置；
9. 创建输出模板；
10. 创建样例测试任务。
