## ADDED Requirements

### Requirement: Stable packaged data selection
打包应用 MUST 使用独立于安装目录的持久数据选择，且安装位置、工作目录或快捷方式变化不得使应用静默切换到新数据库。

#### Scenario: Application is reinstalled to another directory
- **WHEN** 已有持久数据选择且应用从不同安装目录启动
- **THEN** 系统继续使用同一数据根目录和数据库

#### Scenario: Fresh packaged installation starts
- **WHEN** 不存在显式覆盖、持久选择或旧数据库候选
- **THEN** 系统在当前用户的稳定应用数据目录创建新数据根目录

### Requirement: Explicit data directory override
系统 SHALL 让有效的 `BARBYBAR_DATA_DIR` 覆盖其他数据位置来源，并在日志和设置中标明该来源。

#### Scenario: Environment override is present
- **WHEN** `BARBYBAR_DATA_DIR` 指向有效绝对目录
- **THEN** 数据库、日志、设置、备份、恢复和更新文件全部使用该目录

### Requirement: Safe legacy database adoption
系统 MUST 在创建新数据库前识别兼容的旧数据库，并且不得自动覆盖、删除或复制候选数据库。

#### Scenario: Exactly one populated legacy database exists
- **WHEN** 没有显式覆盖或持久选择且仅发现一个包含用户数据的有效旧数据库
- **THEN** 系统零复制接管该数据目录并原子保存持久选择

#### Scenario: Multiple populated legacy databases exist
- **WHEN** 没有显式覆盖或持久选择且发现多个包含用户数据的有效旧数据库
- **THEN** 系统在创建 Repository 前停止自动选择、列出冲突路径且不修改任一数据库

#### Scenario: Only empty legacy database exists
- **WHEN** 旧安装目录仅包含意外创建且没有用户数据的数据库
- **THEN** 系统不得让该空数据库优先于另一个包含用户数据的有效候选

### Requirement: Data location diagnostics
系统 SHALL 向用户和诊断日志展示当前数据根目录、数据库路径及选择来源。

#### Scenario: User opens data settings
- **WHEN** 应用已完成数据位置解析且用户打开数据管理设置
- **THEN** 界面显示当前数据库路径和数据位置来源

#### Scenario: Application starts successfully
- **WHEN** 数据位置解析完成并开始初始化日志
- **THEN** 启动日志记录数据根目录、数据库路径和选择来源

