## ADDED Requirements

### Requirement: Consistent database backup
系统 SHALL 允许用户创建当前数据库的一致性备份，并在备份验证成功前不暴露不完整的最终文件。

#### Scenario: Backup succeeds
- **WHEN** 用户选择创建备份且数据库可读写
- **THEN** 系统生成经过验证的备份文件并显示保存位置和完成时间

#### Scenario: Backup fails
- **WHEN** 备份目标不可写或备份验证失败
- **THEN** 系统保留原数据库，清理不完整临时文件并显示可恢复的错误信息

### Requirement: Safe staged restore
系统 MUST 在替换当前数据库前验证恢复文件，并在下一次启动替换前自动保留当前数据库备份。

#### Scenario: Valid restore is selected
- **WHEN** 用户选择结构有效的 BarByBar 备份并确认恢复
- **THEN** 系统登记待恢复文件，并说明恢复将在安全重启流程中完成

#### Scenario: Invalid restore is selected
- **WHEN** 用户选择非 SQLite 文件或缺少必要结构的数据库
- **THEN** 系统拒绝恢复且不修改当前数据库

### Requirement: Stable trade export
系统 SHALL 将案例摘要和交易记录导出为使用稳定用户字段的 UTF-8 CSV 或 JSON 文件。

#### Scenario: Selected session is exported
- **WHEN** 用户从案例或复盘界面导出交易数据
- **THEN** 导出文件包含案例标识、交易方向、入场、出场、数量、盈亏、原因和可用复盘字段

