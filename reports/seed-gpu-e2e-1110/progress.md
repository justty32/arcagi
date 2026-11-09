# N5c progress notes (implementer; report.md is written by the caller)

Status: DONE. Binary `native/bin/arcbatch-gpuseed` (`make -C native gpuseed-e2e`), tests `tests/native/test_gpuseed_e2e.py`.

- Exactness: training first 100, budget 1e6, decomp, 4 threads: rows equal (ignoring seconds/eval_steps) to bin/arcbatch
  and to a fresh build of current native/src, in CPU mode, --gpu-seed (gpu-min 20000 / 200000 / 1e6). Budget 1e5 with
  --gpu-min 1 + ARC_GPUSEED_VERIFY=1: 100/100 equal, 6.25M GPU SKIP/NODE verdicts re-checked on CPU, 0 failures.
- Bug found on the way: the walk must go bucket a -> entry a -> bucket b -> entry b (rows of all b-bucket jobs
  interleave), so the rank of a candidate is group.rank0 + row*stride + col (CJob.rank0/rstride), not job-major.
- Speed (contended GPU, 7 other GPU processes): --gpu-seed is slower end to end at 1e6 (wall 18.8 s vs 8.0 s).
  Per GPU layer ~14 ms launch+wait and ~27 ms sync (entry upload; each new Enumerator re-uploads its whole bank).
  CPU-mode Amdahl: supported first-order segments are 26% of Enumerator time (66% of nodes); lambda/other 74%.
- Debug env: ARC_GPUSEED_DEBUG=1 prints per-layer/segment node counts and sync timings to stderr.

## Handoff (caller, PARTIAL; context limit reached)

Done: implementation + tests (26 passed in tests/native per implementer), one-shot 1e6 equality (0 mismatches) and the --seed-prof numbers above.
NOT done: 3-run medians at 1e6 / 1e7 (acceptance 1), report.md, warp-cooperative hash.

Running unit (systemd user service): `arcagi-n5c-bench` = `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n5c/bench.sh 1000000 3 && /tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n5c/bench.sh 10000000 3`
- interleaved modes per rep: cpu (`native/bin/arcbatch`), gpu (`arcbatch-gpuseed --gpu-seed`, gpu-min 20000), gpuhi (`--gpu-seed --gpu-min 200000`)
- outputs: `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n5c/res-<budget>-<mode>-<rep>.jsonl` (+ .err), wall clock per run in `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n5c/wall.txt`
- task list `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n5c/train100.txt` (training first 100 by filename), configs `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n5c/cfg-<budget>.jsonl` = {"name":"base","budget":B,"decomp":true}, --threads 4
- At handoff only "1000000 cpu 1 10.3" had finished; GPU is shared with overnight gpusearch/gpgp (100% util), so timings are contended.

Next steps:
1. When the unit finishes: `python3 -I /tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n5c/analyze.py /tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n5c` → markdown tables (wall median, nodes/s, train/test ok, row mismatches vs cpu run 1; mismatches listed on stderr).
2. One --seed-prof run per mode at 1e7 for the Amdahl table (`native/bin/arcbatch-gpuseed --mode seed ... --seed-prof` with and without --gpu-seed).
3. Write report.md: table + plain-language paragraph. Known so far: supported first-order segments = 26% of CPU Enumerator time (66% of nodes) → max ~1.35x even with a free GPU; per-layer upload (~27 ms, whole bank re-uploaded per new Enumerator / decomp subproblem) + ~14 ms launch dominate; lambda kernel is where the other 74% is.
4. Commit report + progress.

## N3c 交棒（11-10 00:3x）
- N3c 交棒：bench 結束後跑 analyze.py 寫 report.md＋pytest。1e6 已完（中位 wall cpu 9.1 s／gpu 21.1 s／gpuhi 9.1 s，解集合 0 mismatch，train_ok 7、test_ok 5）；1e7 於 00:22 開跑。pytest tests/native 00:2x 已跑：26 passed。report 草稿（Amdahl、白話待填、下一步）在 `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n3c/n5c-draft.md`，填 `@@TABLE@@`／`@@CONSIST@@`／`@@PLAIN@@` 即可。
