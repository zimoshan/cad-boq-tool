"""webapi/services: 业务层包装（#19 选 A：算法实现保留，入口重写）

设计：所有 Service 函数**包装而非重写** app/ 业务层算法。
Service 层职责：
  1. Pydantic schema 校验
  2. 业务异常 → HTTP 异常映射
  3. PG 事务管理
  4. LLM/JobManager 调用编排
  5. 审计 + 指标

业务算法实现保留在 app/cad / app/engineering / app/binding / app/takeoff / app/boq / app/llm。
"""
