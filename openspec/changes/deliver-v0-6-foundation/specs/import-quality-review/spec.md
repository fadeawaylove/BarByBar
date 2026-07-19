## ADDED Requirements

### Requirement: Preview before persistence
系统 MUST 在写入数据库前显示 CSV 字段映射、样例数据、可识别行数和时间范围，并要求用户确认。

#### Scenario: User opens a valid CSV
- **WHEN** 用户选择包含可识别 OHLCV 数据的 CSV 文件
- **THEN** 系统显示自动映射结果、样例行和导入摘要，且尚未创建数据集

### Requirement: Actionable quality findings
导入审查 SHALL 检查必要字段、时间和数值解析、重复时间、时间顺序、异常 OHLC 关系及异常时间间隔，并区分阻断错误和可继续警告。

#### Scenario: Blocking issue is found
- **WHEN** CSV 缺少必要字段、没有有效数据或包含无法建立行情序列的错误
- **THEN** 系统阻止确认导入，并显示对应字段、行或原因

#### Scenario: Non-blocking warning is found
- **WHEN** CSV 存在可识别的重复时间或异常间隔但仍有可导入数据
- **THEN** 系统显示警告数量和示例，并允许用户明确确认后继续

### Requirement: Reuse confirmed mapping
确认后的导入 MUST 使用审查界面中展示的字段映射和质量决定，不能在持久化阶段静默改用不同映射。

#### Scenario: User confirms reviewed import
- **WHEN** 用户确认字段映射和质量警告
- **THEN** 系统使用相同映射执行导入并报告成功、跳过和失败结果

