# 独立任务过程记录器：首版决定

## 用户目的与范围

来源是 saddle T38：用户希望按单任务看到派发任务书、JEV 输入/返回、实际采用的模型与验证预算、实现者交付、主控审查及返工，用真实材料改进自己的工作流程。用户不希望个人采集需求侵入通用 corral/drover，已选择独立 repo 与方案 B。

这是采集 CLI，不是新编排器。需要主控显式使用入口；不改三个上游工具、不逐项目改 AGENTS、不常驻、不监听平台流量、不注入 agent、不采集完整会话。不操作 drover。saddle 展示在其仓库另行接入，本仓库不写 UI。

## JEV 方案 B

当前核验的 route.py SHA-256：

`d4ab1cc82fe5c1b10987800eaf1c44d1e1fe026e7b1227b0eeb508cce548167a`

来源：corral 仓库 `corral-dispatch-skill/route.py`，2026-09-29 本机版本。

读取并哈希源码字节后，在记录器自己的进程里加载同一份字节（不生成上游 pycache），调用它的 `build_request`、`call`、`shape`。不替换函数，不修改文件，不复制题目、模型版本、阈值或重试策略。仅复现其密钥取得和结果/异常出口的薄胶水；密钥只用于原有请求函数，不保存。

保存用户传入的摘要、实际请求 JSON、整理前的完整解析 JSON、整理建议。原脚本的 stdin strip 行为保留。解析 JSON 保留被 shape 丢弃的字段和未四舍五入的解析数值，但不是 HTTP 原始字节；解析本身可能改变数值表示、重复键、格式，不采集响应头或重试历史。

版本未知时，发请求前降级 A：运行现有 route.py 一次，只保留公开整理字段与明确缺项。已可能请求 JEV 之后绝不 fallback 重调。原脚本自己的网络重试保持原样。更新适配需核对新源码、离线对照输出/退出码，再更新允许的摘要，不能盲目加哈希。

采集写入失败与路由异常分离；即使本地目录不可写，也不改变成功路由结果。错误任意文本不持久化，仅记录错误类型，原路由错误仍返回主控。

## 关联与证据

- project：主控显式声明的项目根，规范化绝对路径；cwd 是操作的另一字段，不能代替 project。项目移动后不会自动迁移旧键。
- task：项目内任务号，原样保存；不读取 drover 内部状态验证。
- dispatch_id：路由前生成 UUID，并保存在本地。贯穿一次派发的事件，重派/独立审查可以用 parent 引用原派发，不建立状态机。
- operation_id：一次命令或路由的 intent/result 对应关系，只是本记录器的 ID，不是平台原生 turn ID。
- corral name/instance/at/confirmed/pending：直接来自该次公开命令返回，不额外调用 status。
- 主控通过参数声明回复归属；实例一致只是旁证。不同实例显示 mismatch；没有已知实例显示 unknown。未传 dispatch 或上下文损坏明确保留未关联/缺口。
- 任务书在派发命令前读取并按内容哈希保存；记录读取时间，不断言实际读取/送达。
- send 保存发送片段。合并草稿时，完整实际输入未知；pending 不是送达证明。
- 主控决定、预算、审查是 controller_statement，不是工具执行事实；完成回复中的测试结果仍是实现者自报，不是本工具直接观测的测试。
- 模型/强度记录显式命令参数和声明标签，两者分开；未显式给出的默认值保持 null，不推测客户端配置或实际服务端模型。

## 数据格式 v1

默认目录 `~/.local/share/dispatch-log/`，可用全局 `--data-dir` 参数覆盖：

```text
dispatches/<dispatch_id>.json     项目/任务/parent/kind/创建时间
events/<event_id>.json            一事件一文件
blobs/sha256/<前两位>/<sha256>      原文 bytes
```

所有 JSON 带 `schema_version: 1`。事件公共字段：event_id、observed_at（记录器 UTC 时钟）、dispatch_id、project、task、kind、source、association、data。corral 的 at 单独保留，不能当观察时间。

事件类型：`jev.intent`、`jev.route`、`corral.intent`、`corral.start/send/reply`、`controller.decide/note`。intent 只有尝试记录的含义，不能证明命令已发；缺 result 时结果未知。

正文引用为 `{sha256, bytes}`。`dlog cat` 读取时校验哈希；原文独立保存，不依赖 Git 分支、agent 存活或当前任务文件。JSON 解析响应保存为重新序列化的 JSON，而非网络字节。

每个内容文件和事件先写临时文件、fsync、原子 rename、同步所在目录。一事件一文件，无共享追加行或全局计数锁；并发读取可能暂时看不到新事件，但不读到半个 JSON。多文件不是数据库事务：崩溃可能留下孤立 blob/临时文件或只有 intent，首版不自动回收。

新建目录 0700、文件 0600；不改用户已存在目录的权限。数据不默认上传或推送。未知/损坏的版本报错，不默默迁移；读取某条损坏事件可能阻止该次查询，修复需明确处理，不能捏造缺失内容。

## 操作结果与采集结果

公开 corral 命令只执行一次，stdout 原样输出、stderr 继承、退出码保留（信号退出映射为 128+信号）。不使用 shell 拼接、不自动补参数、重试、停止或推进队列。

仅保存白名单字段及明确要求的正文，通用 argv/stdout/stderr/环境不保存。记录失败写 stderr；能写事件时同时写 recording_gaps。目录完全不可写时无法保证缺口持久可见。

纯记录命令 new/decide/note 保存失败会返回非零；它们没有上游副作用。派发执行与记录不是原子事务，极端中断后必须查看公开状态，绝不能自动重放。
