# 数据字典

- run_id：规则版本与输入 SHA-256 前 12 位组成的稳定批次标识。
- line_no：从 1 开始的物理来源行号，不因隔离或排序改变。
- business_key：本项目声明的业务唯一键，始终按字符串存储。
- reason_code：隔离原因的稳定英文编码。
- accepted：进入业务计算的记录数。
- quarantined：保留证据但不参与业务计算的记录数。
- 数值：金额、税额、用量和权重使用 Decimal；对外序列化为字符串。
- 时间：存储为带偏移的 ISO 8601，分桶使用半开区间。
- 空值：缺失键、空串和业务哨兵分别记录。
- 幂等：完整输入字节与规则版本相同则复用 run_id，不新增结果。
- 期版修订：revision_id 由 (issue, old_edition) 哈希生成，是修订登记的稳定幂等键；edition_archives 保留旧版号 archive 行，分卷归档以 revised 状态另立；edition_revisions.volumes_json 存分卷版号与各自期望页，signature 用于区分幂等重试与内容冲突。
- 分卷版号：旧版号 + 字母后缀（01 -> 01A/01B），纯数字版号与增刊号（S 开头）不得作为卷号；验页按分卷版号分组各自对期望页集合取差集。
- 修订原因码：BAD_VOLUME（卷号格式不合法）、REVISION_CONFLICT（同旧版号内容冲突）、SUPERSEDED_EDITION（扫描件仍打已拆分的旧版号）、UNKNOWN_VOLUME（卷号不在已登记修订中）。

