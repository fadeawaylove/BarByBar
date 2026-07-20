## ADDED Requirements

### Requirement: Non-destructive data location adoption
系统 MUST 在接管已有数据目录时保留原数据库内容和路径，并通过原子定位记录使接管可诊断、可回退。

#### Scenario: Existing database is adopted
- **WHEN** 系统确认唯一有效的旧数据库候选
- **THEN** 系统仅保存数据位置选择，不移动、复制、覆盖或删除候选数据库

#### Scenario: Location record publication fails
- **WHEN** 持久数据位置记录无法完整写入或原子发布
- **THEN** 系统不创建替代数据库，并保留原数据库及不完整记录之前的有效状态

