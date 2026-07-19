## ADDED Requirements

### Requirement: Bounded replay response
系统 SHALL 为逐根推进和普通图表交互记录延迟，并以逐根推进 40ms、视窗应用 16ms 作为普通案例的初始警告预算。

#### Scenario: Step-forward metric is recorded
- **WHEN** 用户在活动案例中推进一根 K 线
- **THEN** 系统记录完整推进路径的耗时和必要的数据规模上下文

### Requirement: Update only changed workbench state
逐根推进快路径 MUST 避免重建或重设未发生变化的工作台区域和图表层。

#### Scenario: Position and orders remain unchanged
- **WHEN** 推进一根 K 线且持仓、订单线、绘图和交易集合均未变化
- **THEN** 系统只更新光标、当前价格、进度和确实依赖当前 K 线的内容

### Requirement: Representative large-case validation
性能敏感改动 MUST 使用记录了 K 线、交易、订单线和绘图数量的代表性大案例进行前后对比。

#### Scenario: Performance slice is completed
- **WHEN** 一个性能优化任务准备标记完成
- **THEN** 任务记录至少一组优化前后可比较的中位数、P95 和最大延迟

### Requirement: Non-blocking background work
保存、窗口扩展和适合后台执行的导入工作 SHALL 避免阻塞高频图表交互，并对进行中或失败状态提供明确反馈。

#### Scenario: Background save is running
- **WHEN** 自动保存尚未完成且用户继续推进或浏览图表
- **THEN** 图表保持可交互，并显示可理解的保存状态

