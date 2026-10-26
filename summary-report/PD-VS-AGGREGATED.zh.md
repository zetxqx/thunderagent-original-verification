# PD 分离与 aggregated 部署对比：在这个 workload 上 PD 的用处

写于 2026-10-26。本报告对比本仓库测过的所有 prefill/decode（PD）分离部署和所有 aggregated 部署：

- GLM-5.2-NVFP4：step 25、27、35~40。
- Qwen3.5-397B-A17B-FP8：step 26、33、34。

所有数字都是稳态值。稳态只统计 60 分钟测量中第 5 分钟以后开始的请求。每个部署在每个并发下只有一个测点。图由 [`make_pd_report_figures.py`](make_pd_report_figures.py) 根据 dashboard bundle 和 step 38、40 的 summary 生成。英文版见 [`PD-VS-AGGREGATED.md`](PD-VS-AGGREGATED.md)。

术语约定：

- **部署**：一组服务器加路由方式，例如 1P1D + thunder。
- **prefill 服务器 / decode 服务器**：PD 部署里的 P 和 D。
- **每卡输出**：输出 tok/s 除以部署的全部 GPU 数。
- **单用户解码速度**：输出 token 除以解码时间（即 interactivity）。
- **E2E 交互性**：输出 token 除以整个请求时间，包含 TTFT（即 E2E-normalized interactivity）。

## 0. 结论

1. **在 GLM-5.2 上，没有一种 PD 部署值得它占用的 GPU。**
   - PD 最好的部署每卡输出 72~73 tok/s（1P2D + thunder、1P1D + thunder）。
   - TP=8 aggregated + thunder 每卡输出 109，DEP8 aggregated + thunder 每卡输出 127。PD 只有它们的 0.57~0.67x。
   - 每卡输出相同时，aggregated 的单用户解码速度和 PD 相同，E2E 交互性更高（图 1）。
   - 只有按“每卡并发相同”比较时，PD 才显得解码更快。每卡并发相同并不等于成本相同。
2. **在 Qwen3.5 上，PD 有竞争力。**
   - PD 的峰值是 aggregated 峰值的 0.88x（每卡 370 对 421 tok/s）。
   - 每卡约 370 tok/s 时，PD 的单用户解码速度是 aggregated 的 1.55x（111 对约 72 tok/s）。
   - 在这个输出水平上，两者的 E2E 交互性相同（60.5 对约 59）。
   - PD 还能在每卡 180~275 tok/s 时做到 E2E 交互性 94~113。我们没有在这个区间测 aggregated（图 2）。
3. **在两个模型上，decode 服务器的产出都高于 aggregated 服务器。**
   - GLM-5.2 上，一张 decode 卡的输出是一张 aggregated 卡的 1.3~1.7x（142~181 对 109 tok/s）。
   - Qwen3.5 上是 1.76x（739 对 421 tok/s）。
   - PD 部署的每卡输出 = 每张 decode 卡的输出 × decode 卡占比。所以结果取决于 prefill 卡。
   - 打平所需的 decode 卡占比：GLM-5.2 约 60~77%（对标 TP=8 + thunder），Qwen3.5 是 57%。
   - 测过的 GLM-5.2 部署的 decode 卡占比是 33%（2P1D）、50%（1P1D）、67%（1P2D）（图 3）。
4. **提高 decode 卡占比后，瓶颈转到 prefill 服务器。**
   - prefill 服务器要保存所有 session 的历史。
   - 不加 thunder 时，1P2D 在 c≤64 是最好的 PD 部署（每卡 63 tok/s）。
   - c=96 时 1P2D 崩溃。它的 prefill 服务器上的 working set 约 20M token，超过了 GPU 池加 820 GiB CPU tier 的容量。
   - 结果重算比例升到 6.6%，输出降到 763 tok/s（每卡 31.8）。
5. **thunder 的影响比拓扑更大。**
   - 在所有拓扑上，thunder 都把 TTFT p50 保持在 1~4 s。不加 thunder 时，TTFT p50 最高到 175 s。
   - 在 baseline 过载时，thunder 提高输出：2P1D 从 c=64 起是 1.05~1.17x；1P2D 在 c=64 是 1.14x，在 c=96 是 2.13x。
   - 代价是长尾。完成的请求短了 6~39%，E2E p99 是 1.6~7.5x，forced admission 随负载增加。
   - thunder 的 ledger 只包含 decode pod。所以 thunder 看不到已经饱和的 prefill 服务器。
6. **GLM-5.2 有四个特点让 PD 变贵**（第 5 节）：
   - TP=8 下，每个 rank 都保存一份完整的 MLA KV。所以一台 decode 服务器只能装 1.5M token，也就是 5~8 个 10~25 万 token 的请求。
   - always-disagg 在每一轮都要在 prefill 服务器上 prefill 整段 prompt。这台服务器还要保存所有 session 的历史。
   - 每个请求的 KV 要经过 NIXL 传 8 次。每小时 165~219 TB，但网络不是瓶颈。
   - 每个角色占一整台 8 卡节点，所以 P:D 比例只能粗调。
7. **建议：**
   - GLM-5.2 在这个 workload 上用 aggregated + thunder。
   - TP=8、每卡 2.5~4 个 session 时，每卡输出 100~108 tok/s，TTFT p50 0.7 s。每个用户得到 158~164 tok/s。
   - DEP8 的输出更高（每卡 118~127 tok/s），但单用户解码速度更低（40~55 tok/s）。
   - Qwen3.5 上，如果高负载下需要单用户解码速度超过约 100 tok/s，就用 PD。其他情况下，aggregated 的每卡输出更高。

## 1. 测试环境

| | |
|---|---|
| 硬件 | GKE `a4-highgpu-8g` 节点（每台 8 张 B200 和 8 张 RDMA 网卡），集群 `a4-pr` |
| GLM-5.2 | `nvidia/GLM-5.2-NVFP4`，vLLM v0.31.0，FP8 KV，1M 上下文，MTP 3。每台服务器有 820 GiB CPU KV tier（`OffloadingConnector`）。PD 用 `MultiConnector`（RDMA 上的 NIXL，加上 CPU tier），带 vllm#62862 修复。TP=8 服务器的 GPU KV 池是 1,505,088 token（decode）或 1,572,864 token（prefill）。 |
| Qwen3.5 | `Qwen3.5-397B-A17B-FP8`，TP=4 服务器。PD 是同一节点上两台 TP=4 服务器组成的 1P1D。 |
| Workload | AgentX `agentx-v1.0.6` 回放不截断的 `semianalysis_cc_traces_weka_062126` Claude Code session。平均输入 10~16 万 token，输出中位数 420~470 token。前缀命中率 93~99%，大部分来自 CPU tier。每个测点 60 分钟。每个测点开始时 KV 为空。 |
| 指标 | 每卡输出按部署的全部 GPU 计算。单用户解码速度 = 输出 token / 解码时间。E2E 交互性 = 输出 token / 整个请求时间（含 TTFT）。 |
| Thunder | llm-d-thunder-agent-simplified（PD 用 zetxqx/llm-d-router PR #15）。它为每个 pod 维护一个 KV ledger，空闲 lease 10 s，1800 s 后强制放行。PD 下只有 decode pod 在 ledger 里。 |

## 2. 测过的部署

| 模型 | 部署 | GPU 数 | decode GPU 数 | 路由 | Step |
|---|---|---|---|---|---|
| GLM-5.2 | TP=8 aggregated | 8 | – | 无 | 25 |
| GLM-5.2 | TP=8 aggregated + thunder | 8 | – | thunder EPP | 25 |
| GLM-5.2 | DEP8 aggregated + thunder（数据并行注意力 + 专家并行） | 8 | – | thunder EPP | 27 |
| GLM-5.2 | 1P1D，带 / 不带 thunder | 16 | 8 | vLLM NIXL toy proxy / thunder EPP | 35、36 |
| GLM-5.2 | 2P1D，带 / 不带 thunder | 24 | 8 | toy proxy（每个 session 固定一台 prefill 服务器）/ thunder EPP | 37、38 |
| GLM-5.2 | 1P2D，带 / 不带 thunder | 24 | 16 | toy proxy（每个 session 固定一台 decode 服务器）/ thunder EPP | 39、40 |
| Qwen3.5 | TP=4 aggregated，带 / 不带 thunder | 4 | – | 无 / thunder EPP | 26 |
| Qwen3.5 | 1P1D，带 / 不带 thunder | 8 | 4 | toy proxy / thunder EPP | 33、34 |

所有 PD 部署都是 always-disagg。每一轮先由 prefill 服务器做 prefill（`max_tokens=1`）。然后 decode 服务器通过 NIXL 拉取 KV 并解码。decode 服务器会复用自己已缓存的前缀（#62862 修复）。

## 3. 峰值输出

| 模型 | 部署 | 每卡峰值输出 tok/s（总量） | 峰值时的 c | 峰值时 TTFT p50 | 峰值时单用户解码 tok/s | 峰值时 E2E 交互性 |
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

PD 部署的总量最大，因为它们用了 2~3 倍的 GPU。按每卡算，GLM-5.2 的每个 PD 部署都低于每个 aggregated 部署。

## 4. 同等成本下的交互性

![](figures/pd-fig1-glm-pareto.png)

图 1：GLM-5.2 的所有部署和并发。(a) 是 E2E 交互性，(b) 是单用户解码速度，横轴是每卡输出。越往右上越好。标签是每卡并发。aggregated 是实线，PD 是虚线。

![](figures/pd-fig2-qwen-pareto.png)

图 2：Qwen3.5 的同样两张图。我们只测了每卡 8 个 session 以上的 aggregated 点，所以 aggregated 曲线从每卡 315 tok/s 开始。

下表在每卡输出相同时对比。`~` 表示用最近的两个测点插值。

| 模型 | 每卡输出 tok/s | Aggregated：单用户解码 tok/s / E2E 交互性 | PD：单用户解码 tok/s / E2E 交互性 |
|---|---|---|---|
| GLM-5.2 | ~50 | TP=8，每卡 1（53.5）：237 / 163 | 1P2D，每卡 1.33（50.2）：236 / 74 |
| GLM-5.2 | ~60 | TP=8 + thunder，每卡 1.5（64.6）：217 / 157 | 2P1D + thunder，每卡 2.67（60.5）：175 / 115。1P1D，每卡 1.5（60.0）：200 / 81 |
| GLM-5.2 | ~72 | TP=8 + thunder：~200 / ~141 | 1P2D + thunder（71.8）：199 / 78。1P1D + thunder（72.8）：168 / 98 |
| GLM-5.2 | 100~127 | TP=8 + thunder（100.6~108.7）：164~135 / 112~94。DEP8 + thunder（118~127）：55~40 / 42~30 | 没有 PD 部署能达到 |
| Qwen3.5 | ~355 | TP=4：~77 / ~63 | 1P1D + thunder（354.7）：113 / 52 |
| Qwen3.5 | ~370 | TP=4：~72 / ~59 | 1P1D（369.7）：111 / 60.5 |
| Qwen3.5 | 407~421 | TP=4，带或不带 thunder：59~45 / 49~20 | 没有 PD 部署能达到 |

GLM-5.2：

- 在 PD 能达到的每个输出水平上，每卡 session 更少的 aggregated 部署有相同的单用户解码速度。例如每卡约 50 tok/s 时 236 对 237，约 72 时 199 对约 200。
- aggregated 部署的 E2E 交互性还是 PD 的 1.4~2.2x。它的首 token 之前没有 prefill 排队，也没有 KV 传输。
- 只有 aggregated 部署的每卡输出能超过 73 tok/s。

Qwen3.5：

- 每卡 355~370 tok/s 时，PD 的单用户解码速度是 aggregated 的 1.47~1.55x。
- 在这些测点上，E2E 交互性相同（60.5 对约 59）或更低（52 对约 63）。
- aggregated 的每卡输出多 10~14%，但每个用户只有 45~59 tok/s。

## 5. GPU 的使用情况

![](figures/pd-fig3-decode-gpu.png)

图 3：每个 PD 部署在峰值时的输出。浅色柱是每张 decode 卡的输出，深色柱是整个部署的每卡输出。虚线是 aggregated 最好的每卡输出。

每卡输出 = 每张 decode 卡的输出 × decode 卡占比。GLM-5.2 上，一张 decode 卡最好时输出 142~181 tok/s，是 TP=8 + thunder（109 tok/s）的 1.3~1.7x。但 decode 卡只占 33~67%。所以整个部署每卡只有 54~73 tok/s。

对标 TP=8 + thunder，按我们测到的最好 decode 输出（2P1D + thunder），打平需要 decode 卡占比 109 / 181 = 60%。按 1P1D 的 decode 输出，需要 77%。对标 DEP8 + thunder（127），需要 70~90%。

Qwen3.5 上，一张 decode 卡输出 739 tok/s，是 aggregated（421 tok/s）的 1.76x。所以打平只需要 57%。1P1D 的 decode 卡占比是 50%，所以 1P1D 已经接近（0.88x）。

1P2D 说明了 decode 卡占比不能一直往上加。一台 prefill 服务器带两台 decode 服务器时，每张 decode 卡只输出 95~108 tok/s。prefill 服务器供应的 prefill 不够。

### GLM-5.2 各部署的瓶颈

| 部署 | 瓶颈 | 数据（稳态平均值） |
|---|---|---|
| 1P1D | prefill 服务器 | c = 32、48、64 时，prefill 服务器上分别有 4.8、19.6、44 个请求排队。decode 服务器只跑 5~6 个请求（KV 74%），排队不到 3.5 个。 |
| 2P1D | decode 服务器 | decode 服务器上 6.5~20 个请求排队，5~8 个在跑，KV 82~89%。c=32 时两台 prefill 服务器几乎闲着。 |
| 1P2D | prefill 服务器，然后是它的缓存容量 | c = 32~96 时，prefill 服务器上分别有 3.3、14.5、44.8、111 个请求排队。decode 服务器的 KV 使用率 34~54%。c=96 时重算 6.6%，处理的 prompt token 只有 c=64 的一半。 |
| 1P1D + thunder、2P1D + thunder | thunder | TTFT p50 0.9~1.4 s，prefill 服务器上排队 0.1~6 个（2P1D c=144 时 12 个）。2P1D + thunder 的 decode 服务器上排队不到 1 个，KV 46~54%。ledger 把 lease 内空闲的 session 按完整大小计入。 |
| 1P2D + thunder | prefill 服务器（thunder 看不到） | prefill 服务器上排队 1.3~41 个。decode 服务器的 KV 使用率 20~35%。c=64 以后，prefill 服务器的重算升到 6%，输出下降。 |

### 为什么 PD 对 GLM-5.2 来说很贵

- **decode batch 小。** TP=8 下每个 rank 都保存一份完整的 MLA KV。所以 decode 服务器的 GPU 池只有 1.5M token，也就是这个 workload 的 5~8 个请求。aggregated TP=8 的池一样大，所以 PD 没有让 batch 变大。DEP8 把 KV 分散到各个 rank 上，所以 DEP8 + thunder 能跑约 35 个请求，每卡输出最高。
- **每一轮都做 prefill。** always-disagg 在每一轮都要在 prefill 服务器上 prefill 整段 prompt。这台服务器从 CPU tier 加载 prompt 的大部分，还要保存所有 session 的历史。aggregated 服务器把每个 session 的前缀留在负责解码的同一台服务器上。
- **重复传输。** 每个 decode rank 都拉取完整的 MLA KV，所以每个请求的 KV 要经过 NIXL 传 8 次。不加 thunder 时每小时 165~219 TB。加 thunder 后少 3~6 倍，因为被准入的 session 把 KV 留在 decode 服务器上。网络链路一直不是瓶颈。
- **P:D 比例粗。** 每个角色占一整台 8 卡节点。所以我们只测了 1:1、2:1、1:2 三种比例。

## 6. Thunder 在 PD 上的效果

| 部署、并发 | 每卡输出 tok/s（thunder 对无 thunder） | TTFT p50（thunder 对无 thunder） | 完成请求的输入长度 | E2E p99（thunder 对无 thunder） |
|---|---|---|---|---|
| 1P1D，c=64 | 72.8 对 70.8（1.03x） | 1.2 s 对 49 s | 短 32% | 1,109 s 对 153 s |
| 2P1D，c=64 | 60.5 对 51.6（1.17x） | 0.9 s 对 42 s | 短 39% | 552 s 对 132 s |
| 2P1D，c=144 | 50.6 对 48.0（1.05x） | 1.0 s 对 175 s | 短 23% | 2,081 s 对 446 s |
| 1P2D，c=64 | 71.8 对 63.2（1.14x） | 3.4 s 对 34 s | 短 29% | 548 s 对 134 s |
| 1P2D，c=96 | 67.9 对 31.8（2.13x） | 3.9 s 对 145 s | 短 35% | 1,307 s 对 478 s |
| Qwen3.5 1P1D，c=96 | 355 对 287（1.23x） | 4.7 s 对 36 s | – | 222 s 对 155 s |

thunder 改变了过载 PD 部署的排队方式。被准入的 session 得到很短的 TTFT，被挡住的 session 要等很久。thunder 优先服务小 session：放不下的 session 不会挡住其他 session。所以 TTFT 和交互性的提升有一部分来自更短的请求。每卡输出可以公平比较。输入 tok/s 和交互性数值不能公平比较。

## 7. 本对比的限制

- 每个部署在每个并发下只有一个测点。本仓库之前的重复实验里，测点之间的差异是 2~6%。
- 高负载下，名义并发小于真实的请求并发，因为 session 会发出子 agent 请求。c=144 时，2P1D baseline 平均有 206 个请求在进行，thunder 部署有 80~124 个。c≤64 左右的对比变化不大。
- 不加 thunder 的 PD 部署用 vLLM toy proxy 加 session hash。thunder 部署用 llm-d EPP 和 disagg sidecar。
- 2P1D + thunder 的第一次运行把 87% 的请求送到了一台 prefill 服务器。原因是 `max-score-picker` 在不同 profile 之间共用一个平局计数器。我们丢弃了那次运行。
- Qwen3.5 的测点较少。它的 aggregated 部署从每卡 8 个 session 开始。
- 我们没有测这些方案：
  - 选择性 PD（`prefix-based-pd-decider`），把小的未缓存后缀直接在 decode 服务器上 prefill。
  - DEP 或 wide-EP 的 decode 服务器。
  - 1:1、2:1、1:2 以外的 P:D 比例。
  - 使用不同并行度的 prefill 服务器。
  - 多节点规模，即一台 prefill 服务器供应多台 decode 服务器。

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
