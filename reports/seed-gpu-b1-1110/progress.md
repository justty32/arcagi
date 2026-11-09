# N5d / B1 progress

- Code: `native/gpu/seed/b1_kernel.cu` (copy of `e2e_kernel.cu` + per-thread context pool, pinned staging,
  fused table clear / fp insert); `make -C native gpuseed-b1` -> `native/bin/arcbatch-gpuseed-b1`.
  Host side (`seed_enum_gpu.cpp`, `e2e_main.cpp`) is shared with `arcbatch-gpuseed` unchanged.
- Correctness: 1e5, train100, `--gpu-min 0`, `ARC_GPUSEED_VERIFY=1`: 6,251,811 GPU verdicts re-checked, 0 errors;
  rows vs `arcbatch`: 0 mismatches. `uv run pytest -q tests/native`: 29 passed.
- Bench unit: `arcagi-n5d-bench` (systemd --user service, nice 19), script
  `/tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n5d/bench.sh`:
  1e6 then 1e7, modes cpu / gpu (`arcbatch-gpuseed --gpu-min 0`) / b1 (`--gpu-min 0`) / b1hi (`--gpu-min 200000`),
  interleaved x3, then one `--seed-prof` run of gpu and b1 per budget. `DONE` file when finished.
- Analyze: `python3 -I reports/seed-gpu-b1-1110/analyze.py /tmp/claude-1000/-home-lorkhan-repo-arcagi/b2d327dc-6912-4964-832e-dd0c86af8593/scratchpad/n5d`
- 1e6 done (report.md): b1 56.4 s vs cpu 10.2 s -> E8 fails -> freeze `--gpu-min 200000`. 1e7 still running at commit time.
