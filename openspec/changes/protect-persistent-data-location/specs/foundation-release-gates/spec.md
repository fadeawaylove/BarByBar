## ADDED Requirements

### Requirement: Isolated Windows installer smoke test
发布流程 MUST 使用与生产安装状态隔离的安装标识和程序组执行 Windows 安装冒烟，并验证正式快捷方式与卸载记录未被修改。

#### Scenario: Release installer smoke runs
- **WHEN** 发布流程在临时目录安装并启动候选版本
- **THEN** 测试安装使用独立 AppId，且冒烟结束后生产快捷方式目标和生产卸载记录保持不变

#### Scenario: Upgrade path changes installation directory
- **WHEN** 发布验证模拟应用从不同目录启动
- **THEN** 验证结果证明应用继续解析到同一持久数据目录且不会创建误导性空数据库

