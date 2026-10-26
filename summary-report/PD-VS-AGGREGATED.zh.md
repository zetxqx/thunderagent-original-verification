# PD 分离与 aggregated 部署对比：在这个 workload 上 PD 到底有什么用

写于 2026-10-26，覆盖本仓库测过的所有 prefill/decode（PD）分离和 aggregated 部署：GLM-5.2-NVFP4（step 25、27、35~40）和 Qwen3.5-397B-A17B-FP8（step 26、33、34）。所有数字都是稳态值（只统计 60 分钟测量中第 5 分钟之后开始的请求），每个配置、每个并发只测一个点。图由 [`make_pd_report_figures.py`](make_pd_report_figures.py) 根据 dashboard bundle 和 step 38、40 的 summary 生成。英文版：[`PD-VS-AGGREGATED.md`](PD-VS-AGGREGATED.md)。

## 0. 结论

1. **在 GLM-5.2 上，没有一种 PD 部署划得来。** PD 最好的结果是每卡 72~73 tok/s（1P2D + thunder、1P1D + thunder），而 TP=8 aggregated + thunder 是 109，DEP8 aggregated + thunder 是 127，PD 只有它们的 0.57~0.67x。在每卡吞吐相同的条件下比较，aggregated 的单用户解码速度和 PD 一样，E2E 交互性更高；所有 PD 点都落在 aggregated 曲线上或曲线下方（图 1）。PD 看起来解码更快，只是因为按“每卡并发相同”来比，而这并不是同等成本。
2. **在 Qwen3.5 上，PD 有竞争力。** 峰值是 aggregated 的 0.88x（每卡 370 对 421 tok/s）。但在每卡约 370 tok/s 时，PD 的单用户解码速度是 aggregated 的 1.55x（111 对约 72），E2E 交互性持平（60.5 对约 59）。而且 PD 能跑到高交互性区间（每卡 180~275 tok/s 时 E2E 94~113），这个区间我们没有测 aggregated（图 2）。
3. **“把 decode 单独拿出来跑”本身在两个模型上都是有效的。** GLM-5.2 上一张 decode 卡的产出是 aggregated 一张卡的 1.3~1.7x（142~181 对 109 tok/s），Qwen3.5 上是 1.76x（739 对 421）。PD 的输赢取决于 prefill 卡能不能“赚回”自己的成本：每卡输出 = decode 卡每卡输出 × decode 卡占比。打平所需的 decode 卡占比：GLM-5.2 约 60~77%（对标 TP=8 + thunder），Qwen3.5 是 57%。测过的 GLM-5.2 部署里，decode 卡占比分别是 33%（2P1D）、50%（1P1D）、67%（1P2D）（图 3）。
4. **提高 decode 占比后，瓶颈就转到了 prefill 服务器，而它必须缓存所有 session 的历史。** 不加 gate 的 1P2D 在 c≤64 时是不带路由器的 PD 部署里最好的（每卡 63），但在 c=96 时崩了：prefill 服务器要承载的 working set 达到约 20M token，超过了它的 GPU 池加 820 GiB CPU tier 的容量，重算比例升到 6.6%，输出掉到 763 tok/s（每卡 31.8）。
5. **准入 gate 比拓扑更重要。** 在所有拓扑上，llm-d-thunder 都能把 TTFT p50 压在 1~4 s（不加 gate 时最高到 175 s），并在 baseline 过载时提升吞吐（2P1D 从 c=64 起 1.05~1.17x；1P2D 在 c=64 是 1.14x，c=96 是 2.13x）。代价是长尾：完成的请求短了 6~39%，E2E p99 是 1.6~7.5x，forced admission 随负载增加。另外它的 ledger 只统计 decode pod，看不到 prefill 服务器已经饱和。
6. **GLM-5.2 为什么输**（第 5 节）：TP=8 下 MLA 的 KV 在每个 rank 上都完整复制一份，所以一台 decode 服务器只能装 1.5M token，也就是 5~8 个 10~25 万 token 的请求；always-disagg 每一轮都在 prefill 服务器上重新 prefill 整段 prompt，而且它必须保存所有 session 的历史；每个请求的 KV 要通过 NIXL 传 8 遍（每小时 165~219 TB，但不是瓶颈）；每个角色至少占一整台 8 卡节点，P:D 比例没法细调。
7. **建议。** GLM-5.2 在这个 workload 上用 aggregated + thunder：要兼顾吞吐和延迟就用 TP=8，每卡 2.5~4 个 session（每卡 100~108 tok/s，TTFT p50 0.7 s，单用户解码 158~164 tok/s）；更看重吞吐就用 DEP8（每卡 118~127 tok/s，但单用户只有 40~55 tok/s）。Qwen3.5 上，如果高负载下要求单用户解码速度在 100 tok/s 以上，PD 值得用；否则 aggregated 每卡产出更多。

## 1. 测试环境

| | |
|---|---|
| 硬件 | GKE `a4-highgpu-8g` 节点（每台 8 张 B200、8 张 RDMA 网卡），集群 `a4-pr` |
| GLM-5.2 | `nvidia/GLM-5.2-NVFP4`，vLLM v0.31.0，FP8 KV，1M 上下文，MTP 3；每台服务器 820 GiB CPU KV tier（`OffloadingConnector`）；PD 通过 `MultiConnector`（RDMA 上的 NIXL + CPU tier），带 vllm#62862 修复；每台 TP=8 服务器的 GPU KV 池为 1,505,088 token（decode）和 1,572,864（prefill） |
| Qwen3.5 | `Qwen3.5-397B-A17B-FP8`，TP=4 服务器；PD 为同一节点上两台 TP=4 组成的 1P1D |
| Workload | AgentX `agentx-v1.0.6` 回放不截断的 `semianalysis_cc_traces_weka_062126` Claude Code session：平均输入 10~16 万 token，输出中位数 420~470 token，前缀命中率 93~99%（主要来自 CPU tier）；每个点 60 分钟，每个点开始前清空 KV |
| 指标 | 每卡输出 tok/s（按部署的全部 GPU 平均）；TTFT；interactivity = 单用户解码速度（输出 token / 解码时间）；E2E-normalized interactivity = 输出 token / 整个请求时间（含 TTFT） |
| Gate | llm-d-thunder-agent-simplified（PD 下用 zetxqx/llm-d-router PR #15）：按 pod 统计 KV 占用的 ledger，空闲 lease 10 s，1800 s 后强制放行；PD 下只有 decode pod 进入 ledger |

## 2. 测过的部署

| 模型 | 部署 | GPU 数 | decode GPU 数 | 路由 | Step |
|---|---|---|---|---|---|
| GLM-5.2 | TP=8 aggregated | 8 | – | 无 | 25 |
| GLM-5.2 | TP=8 aggregated + thunder | 8 | – | thunder EPP | 25 |
| GLM-5.2 | DEP8 aggregated + thunder（数据并行注意力 + 专家并行） | 8 | – | thunder EPP | 27 |
| GLM-5.2 | 1P1D，带 / 不带 thunder | 16 | 8 | vLLM NIXL toy proxy / thunder EPP | 35、36 |
| GLM-5.2 | 2P1D，带 / 不带 thunder | 24 | 8 | toy proxy（按 session 固定 prefill）/ thunder EPP | 37、38 |
| GLM-5.2 | 1P2D，带 / 不带 thunder | 24 | 16 | toy proxy（按 session 固定 decode）/ thunder EPP | 39、40 |
| Qwen3.5 | TP=4 aggregated，带 / 不带 thunder | 4 | – | 无 / thunder EPP | 26 |
| Qwen3.5 | 1P1D，带 / 不带 thunder | 8 | 4 | toy proxy / thunder EPP | 33、34 |

所有 PD 部署都是 always-disagg：每一轮都先在 prefill 服务器上 prefill（`max_tokens=1`），再到 decode 服务器上解码；decode 服务器通过 NIXL 拉取 KV，并复用自己已缓存的前缀（#62862 修复）。

## 3. 峰值吞吐

| 模型 | 部署 | 每卡峰值输出 tok/s（总量） | 并发 c | 峰值点 TTFT p50 | 峰值点单用户解码 tok/s | 峰值点 E2E-norm |
|---|---|---|---|---|---|---|
| GLM-5.2 | **DEP8 aggregated + thunder** | **127.1**（1,017） | 64 | 1.2 s | 40 | 30 |
| GLM-5.2 | **TP=8 aggregated + thunder** | **108.7**（870） | 48 | 0.7 s | 135 | 94 |
| GLM-5.2 | TP=8 aggregated | 102.3（818） | 24 | 7.5 s | 120 | 42 |
| GLM-5.2 | 1P1D + thunder | 72.8（1,165） | 64 | 1.2 s | 168 | 98 |
| GLM-5.2 | 1P2D + thunder | 71.8（1,724） | 64 | 3.4 s | 199 | 78 |
| GLM-5.2 | 1P1D | 70.8（1,132） | 64 | 49 s | 177 | 9 |
| GLM-5.2 | 1P2D | 63.3（1,519） | 48 | 14 s | 216 | 31 |
| GLM-5.2 | 2P1D + thunder | 60.5（1,451） | 64 | 0.9 s | 175 | 115 |
| GLM-5.2 | 2P1D | 53.8（1,292） | 96 | 71 s | 159 | 6 |
| Qwen3.5 | **TP=4 aggregated** | **420.6**（1,682） | 64 | 11 s | 45 | 20 |
| Qwen3.5 | TP=4 aggregated + thunder | 407.5（1,630） | 48 | 0.9 s | 59 | 49 |
| Qwen3.5 | 1P1D | 369.7（2,957） | 64 | 3.2 s | 111 | 61 |
| Qwen3.5 | 1P1D + thunder | 354.7（2,838） | 96 | 4.7 s | 113 | 52 |

PD 部署的总量最大，是因为它们用了 2~3 倍的 GPU；按每卡算，GLM-5.2 的所有 PD 部署都低于所有 aggregated 部署。

## 4. 同等成本下的交互性

![](figures/pd-fig1-glm-pareto.png)

图 1：GLM-5.2 所有部署和并发点。(a) E2E-normalized 交互性、(b) 单用户解码速度，横轴是每卡输出 tok/s（越往右上越好），标签是每卡并发。实线为 aggregated，虚线为 PD。

![](figures/pd-fig2-qwen-pareto.png)

图 2：Qwen3.5 同样的图（aggregated 只测了每卡 8 个 session 以上的点，所以曲线从每卡 315 tok/s 开始）。

在每卡输出相同时对比（`~` 表示用相邻两个测点插值）：

| 模型 | 每卡输出 tok/s | Aggregated：单用户解码 / E2E-norm | PD：单用户解码 / E2E-norm |
|---|---|---|---|
| GLM-5.2 | ~50 | TP=8，每卡 1（53.5）：237 / 163 | 1P2D，每卡 1.33（50.2）：236 / 74 |
| GLM-5.2 | ~60 | TP=8 + thunder，每卡 1.5（64.6）：217 / 157 | 2P1D + thunder，每卡 2.67（60.5）：175 / 115；1P1D，每卡 1.5（60.0）：200 / 81 |
| GLM-5.2 | ~72 | TP=8 + thunder：~200 / ~141 | 1P2D + thunder（71.8）：199 / 78；1P1D + thunder（72.8）：168 / 98 |
| GLM-5.2 | 100~127 | TP=8 + thunder（100.6~108.7）：164~135 / 112~94；DEP8 + thunder（118~127）：55~40 / 42~30 | 达不到 |
| Qwen3.5 | ~355 | TP=4：~77 / ~63 | 1P1D + thunder（354.7）：113 / 52 |
| Qwen3.5 | ~370 | TP=4：~72 / ~59 | 1P1D（369.7）：111 / 60.5 |
| Qwen3.5 | 407~421 | TP=4，带或不带 thunder：59~45 / 49~20 | 达不到 |

- **GLM-5.2**：在 PD 能达到的每一个吞吐水平上，aggregated 只要每卡少跑一些 session，单用户解码速度就和 PD 一样（每卡约 50 tok/s 时 236 对 237，约 72 时 199 对约 200），而 E2E 交互性是 PD 的 1.4~2.2x，因为首 token 前面没有 prefill 排队和 KV 传输。每卡 73 tok/s 以上只有 aggregated 能做到。
- **Qwen3.5**：在每卡 355~370 tok/s 时，PD 的单用户解码速度是 aggregated 的 1.47~1.55x，E2E 交互性持平（60.5 对约 59）或更低（52 对约 63）。aggregated 每卡能多产出 10~14%，但单用户只有 45~59 tok/s。

## 5. GPU 都花在哪了

![](figures/pd-fig3-decode-gpu.png)

图 3：每个 PD 部署峰值点上，每张 decode 卡的输出（浅色）和整个部署每卡的输出（深色），虚线是 aggregated 每卡最好成绩。

每卡输出 = decode 卡每卡输出 × decode 卡占比。GLM-5.2 上一张 decode 卡最好能产出 142~181 tok/s，是 TP=8 + thunder（109）的 1.3~1.7x，但 decode 卡只占 33~67%，所以整个部署每卡只有 54~73。要和 TP=8 + thunder 打平，在测到的最好 decode 效率下（2P1D + thunder）需要 decode 占比 109/181 = 60%，按 1P1D 的效率需要 77%；要和 DEP8 + thunder（127）打平需要 70~90%。Qwen3.5 上一张 decode 卡产出 739，是 aggregated（421）的 1.76x，打平只需要 57%，所以 1P1D（50%）已经接近（0.88x）。

1P2D 说明 decode 占比不能简单往上加：一台 prefill 带两台 decode 时，decode 卡每卡只产出 95~108 tok/s，因为 prefill 服务器喂不饱它们。

### GLM-5.2 各部署的瓶颈

| 部署 | 瓶颈 | 依据（稳态平均值） |
|---|---|---|
| 1P1D | prefill 服务器 | c = 32、48、64 时 P 排队 4.8、19.6、44；decode 受 KV 限制只能跑 5~6 个请求（KV 74%），但排队不到 3.5 |
| 2P1D | decode 服务器 | D 排队 6.5~20，运行 5~8 个，KV 82~89%；c=32 时两台 prefill 几乎闲着 |
| 1P2D | prefill 服务器，然后是它的缓存容量 | c = 32~96 时 P 排队 3.3、14.5、44.8、111；decode KV 34~54%；c=96 时重算 6.6%，处理的 prompt 只有 c=64 的一半 |
| 1P1D + thunder、2P1D + thunder | gate | TTFT p50 0.9~1.4 s，prefill 排队 0.1~6（2P1D c=144 时 12）；2P1D + thunder 的 decode 排队不到 1、KV 46~54%，因为 ledger 把 lease 内空闲的 session 也按完整大小计入 |
| 1P2D + thunder | prefill 服务器（gate 看不到） | P 排队 1.3~41，decode KV 20~35%；c=64 以后 prefill 重算升到 6%，输出下降 |

### 为什么 GLM-5.2 不适合 PD

- **decode batch 太小。** TP=8 下 MLA 的 KV 在每个 rank 上都复制一份，decode 服务器的 GPU 池只有 1.5M token，也就是 5~8 个这种长度的请求。aggregated TP=8 的池也一样大，所以 PD 并没有让 batch 变大；而 DEP8 会（它的 KV 分散在各个 rank 上），所以 DEP8 + thunder 能同时跑约 35 个请求，每卡吞吐最高。
- **每一轮都重复做 prefill。** always-disagg 每一轮都要在 prefill 服务器上 prefill 整段 prompt（主要是从它的 CPU tier 加载），而且这台服务器必须保存所有 session 的历史；aggregated 服务器则把每个 session 的前缀留在负责解码的那台机器上。
- **传输冗余。** 每个 decode rank 都要拉一份完整的 MLA KV，所以每个请求的 KV 要过 8 遍 NIXL：不加 gate 时每小时 165~219 TB（加 thunder 后少 3~6 倍，因为被准入的 session 把 KV 留在 decode 服务器上）。网络链路一直不是瓶颈。
- **P:D 比例太粗。** 每个角色至少占一整台 8 卡节点，所以只测了 1:1、2:1、1:2 三种比例。

## 6. Gate 在 PD 上的效果

| 部署、并发 | 每卡输出 tok/s（gate 对无 gate） | TTFT p50（gate 对无 gate） | 完成请求的输入长度 | E2E p99（gate 对无 gate） |
|---|---|---|---|---|
| 1P1D，c=64 | 72.8 对 70.8（1.03x） | 1.2 对 49 s | 短 32% | 1,109 对 153 s |
| 2P1D，c=64 | 60.5 对 51.6（1.17x） | 0.9 对 42 s | 短 39% | 552 对 132 s |
| 2P1D，c=144 | 50.6 对 48.0（1.05x） | 1.0 对 175 s | 短 23% | 2,081 对 446 s |
| 1P2D，c=64 | 71.8 对 63.2（1.14x） | 3.4 对 34 s | 短 29% | 548 对 134 s |
| 1P2D，c=96 | 67.9 对 31.8（2.13x） | 3.9 对 145 s | 短 35% | 1,307 对 478 s |
| Qwen3.5 1P1D，c=96 | 355 对 287（1.23x） | 4.7 对 36 s | – | 222 对 155 s |

gate 把过载 PD 部署里的排队变成了：被准入的 session TTFT 很短，被挡住的 session 等很久。它优先放行小 session（“放不下的 session 不会挡住其他 session”），所以 TTFT 和交互性的提升有一部分来自请求变短。输出 tok/s 可以直接比，输入 tok/s 和交互性指标则不能直接比。

## 7. 注意事项

- 每个配置、每个并发只测了一个点；本仓库之前的重复实验显示，不同点之间的波动在 2~6%。
- 高负载下名义并发低估了真实的请求并发（因为有子 agent 请求）：c=144 时 2P1D baseline 平均有 206 个请求在跑，thunder 的几组是 80~124。c≤64 左右的对比受影响不大。
- 不带路由器的 PD 组用的是 vLLM toy proxy 加 session hash；thunder 组用的是 llm-d EPP 和 disagg sidecar。2P1D + thunder 的第一次尝试因为 `max-score-picker` 共用平局计数器，把 87% 的请求打到了一台 prefill 上，那次结果已作废。
- Qwen3.5 的测点较少，aggregated 组从每卡 8 个 session 开始。
- 没测过的方向：选择性 PD（`prefix-based-pd-decider`，把小的未缓存后缀直接在 decode 服务器上 prefill）、DEP/wide-EP 的 decode 服务器、2:1 和 1:2 之外的 P:D 比例、prefill 用不同并行度，以及一台 prefill 喂多台 decode 的多节点规模。

## 8. 数据来源

| Step | README | 内容 |
|---|---|---|
| 25 | [`../25-glm52-tp8-offload/`](../25-glm52-tp8-offload/) | GLM-5.2 TP=8 aggregated，带 / 不带 thunder |
| 27 | [`../27-glm52-dep8/`](../27-glm52-dep8/) | GLM-5.2 DEP8 aggregated，带 thunder |
| 35、36 | [`../35-glm52-1p1d/README.md`](../35-glm52-1p1d/README.md)、[`../36-glm52-1p1d-thunder/README.md`](../36-glm52-1p1d-thunder/README.md) | GLM-5.2 1P1D，带 / 不带 thunder |
| 37、38 | [`../37-glm52-2p1d/README.md`](../37-glm52-2p1d/README.md)、[`../38-glm52-2p1d-thunder/README.md`](../38-glm52-2p1d-thunder/README.md) | GLM-5.2 2P1D，带 / 不带 thunder |
| 39、40 | [`../39-glm52-1p2d/README.md`](../39-glm52-1p2d/README.md)、[`../40-glm52-1p2d-thunder/README.md`](../40-glm52-1p2d-thunder/README.md) | GLM-5.2 1P2D，带 / 不带 thunder |
| 26 | [`../26-qwen35-tp4-thunder/`](../26-qwen35-tp4-thunder/) | Qwen3.5 TP=4 aggregated，带 / 不带 thunder |
| 33、34 | [`../33-qwen35-1p1d-baseline/`](../33-qwen35-1p1d-baseline/)、[`../34-qwen35-1p1d-thunder/`](../34-qwen35-1p1d-thunder/) | Qwen3.5 1P1D，带 / 不带 thunder |
| – | [`pd-vs-nonpd.png`](figures/pd-vs-nonpd.png) | 之前只含 1P1D 的同类对比图 |
