# 扫描期版质检台

面向真实数据复核的中型数据工程工具，包含六个可独立调用的业务模块。规则、失败原因与证据字段见 docs/DATA-DICTIONARY.md，陷阱和测试映射见 docs/DEPTH.md。

## 启动

docker compose up --build

浏览器访问 http://localhost:18217。测试：docker compose exec -T app pytest -q

## 模块

- M1 清单采信：页面 /intake，接口 /api/scans/import
- M2 期版契约：页面 /issues，接口 /api/issues/normalize
  - 期版修订（旧版号拆两卷）：/api/issues/revise
  - 旧号查卷（归档 + 更正分卷）：/api/issues/lookup
  - 采信归属（旧号扫描件隔离）：/api/issues/attribute
- M3 页码序列：页面 /pages，接口 /api/pages/check
  - 分卷验页（按修订逐卷验缺页）：/api/pages/check-volumes
- M4 重扫判定：页面 /rescans，接口 /api/rescans/evaluate
- M5 混期归因：页面 /mixed，接口 /api/mixed/evaluate
- M6 批次对账：页面 /batches，接口 /api/reconcile

## 运行规则

同一输入内容生成相同运行标识，重复执行复用已有批次。隔离记录包含原因码、原始行号与原值；业务导出只保留一份证据清单。

## 期版修订（旧版号拆卷）

报社补发增刊目录把同一旧版号拆成两卷时，旧版号当年归档保留，修订指向两个分卷版号：

- 旧号查卷同时回当年归档与更正后的两卷；
- 旧版号下新到扫描件按 `SUPERSEDED_EDITION` 隔离，必须带分卷版号（如 01A/01B）重新归属；
- 验页按分卷独立期望页执行，避免两卷各缺一页被并账验成一本齐卷；
- 修订登记为单事务且按 `(期号, 旧版号)` 幂等：重试不重复登记，冲突回滚并保留旧版归档。

