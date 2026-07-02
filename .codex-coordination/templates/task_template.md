# Codex Task

## 1. Task ID

[TASK_ID]

## 2. Status

READY

## 3. Background

[说明当前项目阶段、已完成任务、本任务来源和本任务边界。]

## 4. Goal

本任务只完成：

- [明确单一目标]

## 5. Allowed Scope

允许新增或修改：

- [具体文件或目录]

## 6. Forbidden Actions

1. 不得删除任何已有文件。
2. 不得修改未授权文件。
3. 不得引入新依赖。
4. 不得修改核心配置文件。
5. 不得处理本任务之外的问题。
6. 不得编造外部服务配置。
7. 遇到不确定事项必须 BLOCKED。

## 7. Requirements

1. [具体要求一]
2. [具体要求二]
3. [具体要求三]

## 8. Acceptance Criteria

1. 完成指定目标。
2. 未越权修改。
3. 未删除文件。
4. 未引入未授权依赖。
5. 输出验证结果。
6. 输出潜在风险。

## 9. BLOCKED Rules

如遇以下情况，暂停并输出 BLOCKED：

1. 目标文件已存在；
2. 需要修改未授权文件；
3. 当前项目结构与任务描述不一致；
4. 存在多个实现路径且影响架构；
5. 外部服务配置不明确；
6. 法律业务逻辑不确定；
7. 测试失败且无法判断是否应在本任务中修复。

## 10. BLOCKED Report Format

```markdown
# Codex Execution Blocker

## 1. Current Task

## 2. Completed Work

## 3. Blocker Description

## 4. Related Files

## 5. Options

### Option A

### Option B

### Option C

## 6. Codex Preliminary Assessment

## 7. Decision Needed from ChatGPT
```

## 11. DONE Report Format

完成后请输出：

```markdown
# Codex Execution Result

## 1. Status

DONE

## 2. Summary

## 3. Files Created

## 4. Files Modified

## 5. Files Deleted

## 6. Commands Run

## 7. Verification Method

## 8. Test Results

## 9. Risks

## 10. Suggested Next Step
```
