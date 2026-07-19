## ADDED Requirements

### Requirement: Consistent foundation experience
工作台 SHALL 使用一致的中文术语、明确的操作状态和适应已揭示数据量的初始图表视窗，同时保持现有交易语义。

#### Scenario: A new session has limited revealed bars
- **WHEN** 活动案例已揭示的 K 线少于默认视窗容量
- **THEN** 图表使用有界的自适应视窗减少无意义空白，同时保留右侧未来空间

#### Scenario: Position state is displayed
- **WHEN** 当前持仓为空、做多、做空或案例已完成
- **THEN** 工作台使用一致的中文状态和对应的操作可用性

### Requirement: Persistent save feedback
系统 SHALL 显示保存中、已保存和保存失败状态，且失败状态在用户处理或后续成功前不能被普通提示自动覆盖。

#### Scenario: Background save fails
- **WHEN** 案例后台保存失败
- **THEN** 工作台持续显示失败状态并提供重试或查看详情路径

### Requirement: Release validation evidence
v0.6 完成 MUST 包含聚焦测试、完整测试、关键状态截图、代表性性能基准、Windows 安装包冒烟和远程 Release 产物验证。

#### Scenario: Milestone is ready to release
- **WHEN** 所有实现任务准备标记完成
- **THEN** 任务清单包含所有发布门槛的通过记录或明确阻断项

