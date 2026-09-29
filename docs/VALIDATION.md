# 首版验证记录

日期：2026-09-29。全程使用临时数据、假的 corral、合成 JEV 响应；未执行真实 agent/队列操作，未调用 JEV 网络，未安装全局指令。

## RED → GREEN

- CLI 空实现时先运行 8 项行为检查，8 项失败：没有持久派发 ID、没有执行/记录命令。失败来自目标功能缺失，没有语法或导入失败。
- JEV 空实现时先运行 5 项检查，3 项断言失败、2 项因缺少预期 error 字段而失败：没有执行路由、保存完整响应或正确处理失败。
- 实现后核心 13 项全部通过。过程中修正一处 macOS `/var` 与 `/private/var` 的测试期望，按设计比较规范化路径。
- 最后审查补出未关联事件缺陷：未传 dispatch 的 reply 不应与其他未关联 send 推出实例相符。先得到 consistent 而非 unknown 的失败，再限定只在有效派发上下文内校验；补查返工前任务书快照。

## 最终运行

```sh
DLOG_TEST_ROUTE=/Users/firegnu/Developer/personal_projs/corral/corral-dispatch-skill/route.py \
  python3 -m unittest discover -s tests -v
```

20 项通过，0 失败，0 跳过。覆盖：

- 跨 worktree 的显式项目关联、ID 持久查询、错误 parent 拒绝。
- 派发前任务书快照；实际模型参数与标签分别记录；无关参数、env、任意输出不落盘。
- 草稿合并、pending、实例变更、声明关联与未证明因果。
- 未关联事件不互相推断归属；返工 send 保存更新后的任务书快照。
- corral 失败不重发、目录不可写时仍透传真实结果。
- 主控声明与原文、文件权限、并发 32 条事件无覆盖、内容哈希校验入口。
- B 保存完整解析响应，版本不符在调用前降级一次，缺密钥不请求，记录失败不改变 JEV 结果。
- 真实已安装 route.py 的离线契约：成功输出一致；原有两次网络尝试策略保留、无额外重试；shape 失败仍保留完整响应、不重调。

已安装源码检查中 urllib.request.urlopen 全部被替换为合成响应/异常；没有访问真实平台。真实 route.py 字节只读加载，未生成上游 pycache。

## 修正：send 选项在名字之前

日期：2026-09-29。对照 `corral send --help` 发现，`send --after X dev '正文'` 会把 `--after` 记成 agent 名、`X` 记成正文；真实命令本身不受影响。

- RED：新增 2 项检查，均因记录字段错误失败（记成 `--after`/`--force`、`--new-option`），不是语法或导入失败。
- GREEN：按公开选项提取位置参数，无法识别时记为未知。设置 `DLOG_TEST_ROUTE` 为已安装 route.py 后，22 项通过，0 失败，0 跳过。

## 验证范围

没有验证真实平台调用、真实 corral 生命周期、长期真实采集或 saddle 展示。当前可交接的是记录器首版，不宣称全量记录、agent 因果归属或 HTTP 原始报文采集。
