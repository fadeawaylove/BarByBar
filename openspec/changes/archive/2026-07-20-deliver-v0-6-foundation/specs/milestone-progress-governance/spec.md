## ADDED Requirements

### Requirement: Repository-owned roadmap
项目 SHALL 在仓库中维护长期路线、当前里程碑、执行入口和明确的候选范围，使工作状态不依赖聊天记录。

#### Scenario: New work session resumes current milestone
- **WHEN** 执行者在没有先前聊天上下文的情况下开始工作
- **THEN** 执行者能够从路线图定位当前 OpenSpec change 和未完成任务

### Requirement: Recoverable task checkpoints
当前里程碑 MUST 使用任务清单记录完成状态，并只在实现和相应验证均完成后勾选任务。

#### Scenario: Partial task remains incomplete
- **WHEN** 一项任务只完成了部分实现或尚未完成验证
- **THEN** 任务保持未完成，并记录已完成部分和下一步

### Requirement: Iteration closeout evidence
每轮实现 SHALL 留下可检查的 Git 状态、任务状态和与风险匹配的测试、性能或视觉验证结果。

#### Scenario: Another session continues work
- **WHEN** 后续执行者检查当前里程碑
- **THEN** 能够识别最后完成的切片、验证结果和下一项可执行任务

