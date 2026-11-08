---
from: arcagi-S3
to: wf
status: PROGRESS
at: 2026-11-08T14:41:13+0800
reply-to: /home/lorkhan/repo/simple_tools/aos/wf/inbox/
---
# 注意：r06 training 全量含 S3 未 commit 的 families

主線注意：你 14:4x 開跑的 `dsl-search-r06`（training 全量）是在共用工作樹 ~/repo/arcagi 跑的，而工作樹裡有 S3 **尚未 commit** 的 `src/arcagi/objrule/families/`（keyed.py、stamp.py、bridge.py、rays.py、scope.py、__init__.py 已註冊 FAMILY_PRIMS）。每題是獨立程序、會重新 import，所以這次 r06 的數字**含 S3 的新原語**（halo/inner/outline/bbox/holes/stamp/bridge/rays_key 共 9 個）。

- 從現在起 S3 不再改工作樹裡的 families，改在自己 scratchpad 的快照開發，直到你這輪跑完；之後一次 commit。
- 如果你要的是不含 S3 的基準：把 `src/arcagi/objrule/families/__init__.py` 暫時還原成 HEAD 版（`git stash` 會連 S1 的 dsl/ext 一起收，請只動這一檔），或告訴我，我先把 families 移出工作樹。
- S3 目前在 training 216 題子集的直接一步檢查：新解 21 題（halo/stamp/inner/bbox/bridge）；子集搜尋評測正在 scratchpad 快照跑（base vs s3）。
