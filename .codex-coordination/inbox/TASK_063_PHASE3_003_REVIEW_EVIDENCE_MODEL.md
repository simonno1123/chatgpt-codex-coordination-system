ARTIFACT TYPE:
TASK

TASK ID:
TASK_063_PHASE3_003_REVIEW_EVIDENCE_MODEL

PRODUCER:
ChatGPT Review

TO:
Codex Executor

NEXT RECEIVER:
ChatGPT Review

PROJECT:
/Users/zhang/Documents/chatgpt-codex-coordination-system


MODE:
DOCUMENTATION GOVERNANCE / NON-RUNTIME / NON-ENFORCING


OBJECTIVE:

建立 ACOS Phase 3 Execution Governance Layer 中的 Review Evidence Model。

本任务用于定义：

执行结果经过 Review 时所需的结构化证据模型。

核心目标：

建立：

Execution Receipt

↓

Review Evidence

↓

Review Decision

之间的治理关系。


AUTHORITY LIMIT:

Codex Executor is authorized only to create the approved documentation artifact.

No authority is granted for:

- runtime implementation;
- schema modification;
- validator modification;
- enforcement mechanism;
- automatic review system;
- decision automation;
- cross-project changes;
- task creation.


DELIVERABLE:

docs/review-evidence-model.md


ALLOWED FILES:

- docs/review-evidence-model.md


FORBIDDEN:

- Python changes
- Schema changes
- Validator changes
- Test changes
- Runtime changes
- Orchestrator changes
- Database changes
- Hook / Enforcement changes
- Automatic reviewer implementation
- AI decision engine implementation
- claude-for-legal-cn access
- TASK_064 creation


REQUIRED DOCUMENT CONTENT:


## 1. Review Evidence Definition

必须明确：

Review Evidence

≠

Execution Output

≠

Raw Log

定义：

Review Evidence 是支持 Review Decision 的结构化证据集合。


---

## 2. Evidence Relationship Model

必须表达：

Execution Result

+

Execution Receipt

+

Validation Information

↓

Review Evidence

↓

Review

↓

Decision


---

## 3. Evidence Components

至少包含：

- task_reference
- execution_receipt_reference
- reviewed_artifacts
- validation_results
- boundary_check_result
- reviewer_identity
- findings
- decision_reference


---

## 4. Evidence and Decision Separation

必须明确：

Review Evidence

≠

Decision


Evidence:

提供依据。


Decision:

承担最终判断。


禁止：

Evidence 自动触发 Approval。


---

## 5. Role Boundary

保持：

ChatGPT Review:

Review / Decision Authority


Codex Executor:

Execution Evidence Provider


External Advisory:

Independent Non-binding Observation


---

## 6. Evidence Lifecycle

定义：

GENERATED

↓

COLLECTED

↓

REVIEWED

↓

ACCEPTED


异常：

INCOMPLETE

BLOCKED


---

## 7. Non-Implementation Boundary

必须声明：

本模型不实现：

- Runtime Evidence Collector;
- Database;
- Automatic Reviewer;
- AI Judge;
- Approval Engine.


OUTPUT:

仅返回 RESULT。

不得 commit。

不得 push。
