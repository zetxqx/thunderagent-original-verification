# Working tree the thunder-agent-v3 image was built from

HEAD: 513f072797a8946f08b5dba8851a4fa24d1e35a5
built: 2026-09-17T23:53:03Z
diff sha256: 81439931ca1e82a8 (git diff HEAD, tracked files)
committed afterwards as ae371354 on branch thunder-agent (github.com/zetxqx/llm-d-router); the image content equals that commit
untracked: pkg/epp/framework/plugins/thunderagent/conformance_test.go pkg/epp/framework/plugins/thunderagent/pause_test.go 

```
 deploy/config/thunderagent-config.yaml             |  71 ++++---
 pkg/epp/flowcontrol/thunderagent_ab_sim_test.go    |  15 +-
 .../flowcontrol/thunderagent_integration_test.go   | 146 ++++++++++++--
 ..._sim_test.go => thunderagent_pause_sim_test.go} |  86 ++++----
 .../flowcontrol/thunderagent_realistic_sim_test.go |  19 +-
 pkg/epp/framework/plugins/thunderagent/README.md   |  90 +++++----
 .../framework/plugins/thunderagent/accounting.go   |  78 +++++--
 .../plugins/thunderagent/accounting_test.go        |  70 ++++++-
 pkg/epp/framework/plugins/thunderagent/config.go   |  40 ++--
 pkg/epp/framework/plugins/thunderagent/fairness.go | 145 ++++++++-----
 .../framework/plugins/thunderagent/helpers_test.go |  73 ++++++-
 .../plugins/thunderagent/lifecycle_test.go         |  21 ++
 pkg/epp/framework/plugins/thunderagent/metrics.go  |  21 +-
 pkg/epp/framework/plugins/thunderagent/plugin.go   |  41 +++-
 .../framework/plugins/thunderagent/plugin_test.go  |  16 +-
 .../plugins/thunderagent/program_table.go          | 104 +++++++---
 .../framework/plugins/thunderagent/saturation.go   | 224 ++++++++++++++-------
 .../plugins/thunderagent/saturation_test.go        |  25 ++-
 pkg/epp/framework/plugins/thunderagent/scorer.go   |  29 ++-
 .../framework/plugins/thunderagent/scorer_test.go  |  17 ++
 .../framework/plugins/thunderagent/shed_test.go    | 194 ------------------
 .../framework/plugins/thunderagent/state_dump.go   |  16 +-
 22 files changed, 968 insertions(+), 573 deletions(-)
```

## thunder-agent-v4

Built 2026-09-19 22:36 UTC from llm-d-router commit `8ee881c2` (adds `resumePlacement` with `origin-only`; identical to v3 under the default `most-room`), Cloud Build `98a13127`, amd64. Binary layer differs from v3 (`3675bdb75474` vs `fc7ffc156f66`). Used by the step 13 origin arm and its v4 control cell.

## Tags

Annotated tags `thunder-agent-v3`, `thunder-agent-v4`, `thunder-agent-v5` on `zetxqx/llm-d-router` point at the exact commits of each image (https://github.com/zetxqx/llm-d-router/tags). Reference commits through these tags in write-ups; a branch rebase cannot orphan a tagged commit.
