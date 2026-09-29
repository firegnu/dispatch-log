# dispatch-log

独立、显式启用的个人任务过程记录器。保存真实任务书快照、JEV 请求与完整解析响应、主控决定、派发结果、完成回复和审查，供日后复盘流程。

这是一次性命令，不是常驻服务。corral、drover 和共享 corral-dispatch-skill 不依赖它；saddle 的 Dispatch 展示尚未接入。

## 运行

需要 Python 3.10+，运行时仅依赖标准库。无需安装即可使用：

```sh
./dlog --help
# 或
python3 -m dispatch_log --help
```

也提供 `pyproject.toml` 的 `dlog` 命令入口，可在自己的虚拟环境安装。当前未安装到全局 PATH，未改任何客户端全局指令。

主控启用与完整命令示例见 [USAGE.md](USAGE.md)。设计、数据含义见 [docs/DESIGN.md](docs/DESIGN.md)，接手工作先读 [HANDOFF.md](HANDOFF.md)。

## 已实现

- `new / ls / show / cat`：显式项目、任务及派发 ID；查询本地事件与原文。
- `route`：方案 B，调用核验过版本的现有 `route.py` 函数，保存整理前的完整解析 JSON；版本不符在请求前降级为 A，并明确提示。
- `decide / note`：保存主控的模型、强度、验证预算、理由、审查与返工原文，标为主控陈述。
- `start / send / reply`：只执行调用者指定的一条 corral 命令；保存相关白名单字段，不重发、不推进队列。
- 文件快照与事件在本地持久保存；派发前快照不等于 agent 已读证明，reply 关联不等于因果证明。

## 边界

- 不修改上游，不向工作 agent 注入采集指令，不修改客户端或拦截网络，不读取私人会话日志或 corral/drover 内部状态。
- JEV 适配器沿用原脚本读取密钥和请求的方式；不保存密钥、认证头、环境或通用命令参数/输出。不新增额外路由请求，原脚本自带的重试仍保留。
- 记录的数据默认在 `~/.local/share/dispatch-log/`；仓库只存代码和合成测试。首次真实使用才创建默认数据目录。
- 原文材料本身可能包含私人信息；工具会原样保存明确交给它的任务书、提示词和回复，不声称自动清洗正文。不要把凭证或无关内容交给采集入口。
- 没有透明拦截或自动采全：绕过入口、被覆盖的回复无法补回。缺少结果事件表示结果未知，不表示操作没执行。
- 未实现后台观察、自动重试、统计打分、历史补录、saddle UI 或全局自动启用。

## 验证

```sh
python3 -m unittest discover -s tests -v
```

另有对已安装路由脚本的离线契约检查。设置路径后运行同一套件；全部网络请求被测试替身替代，不需要真实密钥：

```sh
DLOG_TEST_ROUTE="$HOME/.agents/skills/corral-dispatch/route.py" \
  python3 -m unittest discover -s tests -v
```

未设置时只跳过这三项已安装源码检查。首版验证记录见 [docs/VALIDATION.md](docs/VALIDATION.md)。
