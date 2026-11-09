CXX := g++
CXXFLAGS := -std=c++20 -O3 -march=native -ffp-contract=off -Wall -Wextra -pthread
SOURCES := $(wildcard src/*.cpp)
HEADERS := $(wildcard src/*.hpp)

.PHONY: all spec
all: bin/arcsearch spec bin/solve bin/arcbatch

bin:
	mkdir -p bin

bin/arcsearch: $(SOURCES) $(HEADERS) | bin
	$(CXX) $(CXXFLAGS) $(SOURCES) -o $@

spec:
	cd .. && PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR="$$PWD/native/.uv-cache" uv run --no-sync python native/export_spec.py > native/spec.json

bin/solve: solve.sh | bin
	cp solve.sh $@
	chmod +x $@

bin/arcbatch: arcbatch.sh | bin
	cp arcbatch.sh $@
	chmod +x $@

# CUDA brute-force prototype (native/gpu/, reports/native-cuda-1109/).
# Separate target: `make gpu`; the default build stays CPU-only.
NVCC ?= /opt/cuda/bin/nvcc
NVFLAGS := -O3 -std=c++17 -arch=native -allow-unsupported-compiler
LIB_SOURCES := $(filter-out src/main.cpp,$(SOURCES))
LIB_OBJECTS := $(patsubst src/%.cpp,bin/gpu-obj/%.o,$(LIB_SOURCES))

.PHONY: gpu
gpu: bin/gpusearch

bin/gpu-obj/%.o: src/%.cpp $(HEADERS) | bin
	mkdir -p bin/gpu-obj
	$(CXX) $(CXXFLAGS) -c $< -o $@

bin/gpu-obj/kernel.o: gpu/kernel.cu gpu/space.hpp gpu/gpu.hpp | bin
	mkdir -p bin/gpu-obj
	$(NVCC) $(NVFLAGS) -c $< -o $@

bin/gpu-obj/driver.o: gpu/driver.cpp gpu/space.hpp gpu/gpu.hpp $(HEADERS) | bin
	mkdir -p bin/gpu-obj
	$(CXX) $(CXXFLAGS) -I/opt/cuda/include -c $< -o $@

bin/gpusearch: $(LIB_OBJECTS) bin/gpu-obj/kernel.o bin/gpu-obj/driver.o
	$(CXX) $(CXXFLAGS) $^ -L/opt/cuda/lib64 -Wl,-rpath,/opt/cuda/lib64 -lcudart -o $@

# GPU genetic program search over the gpusearch space (native/gpu/gp/,
# reports/gpu-gp-1109/). Separate target: `make gpugp`. gp_kernel.cu includes
# gpu/kernel.cu so both share the same primitives and verdict.
.PHONY: gpugp
gpugp: bin/gpgp

bin/gp-obj/gp_kernel.o: gpu/gp/gp_kernel.cu gpu/gp/gp.hpp gpu/kernel.cu gpu/space.hpp gpu/gpu.hpp | bin
	mkdir -p bin/gp-obj
	$(NVCC) $(NVFLAGS) -c $< -o $@

bin/gp-obj/gp_main.o: gpu/gp/gp_main.cpp gpu/gp/gp.hpp gpu/space.hpp gpu/gpu.hpp $(HEADERS) | bin
	mkdir -p bin/gp-obj
	$(CXX) $(CXXFLAGS) -I/opt/cuda/include -c $< -o $@

bin/gpgp: $(LIB_OBJECTS) bin/gp-obj/gp_kernel.o bin/gp-obj/gp_main.o
	$(CXX) $(CXXFLAGS) $^ -L/opt/cuda/lib64 -Wl,-rpath,/opt/cuda/lib64 -lcudart -o $@

# GPU near-miss profiler over the gpusearch space (native/gpu/profile/,
# reports/task-features-1109/). Separate target: `make gpuprofile`.
# profile_kernel.cu includes gpu/kernel.cu to share primitives.
.PHONY: gpuprofile
gpuprofile: bin/gpuprofile

bin/profile-obj/profile_kernel.o: gpu/profile/profile_kernel.cu gpu/profile/profile.hpp gpu/kernel.cu gpu/space.hpp gpu/gpu.hpp | bin
	mkdir -p bin/profile-obj
	$(NVCC) $(NVFLAGS) -c $< -o $@

bin/profile-obj/profile_main.o: gpu/profile/profile_main.cpp gpu/profile/profile.hpp gpu/space.hpp gpu/gpu.hpp $(HEADERS) | bin
	mkdir -p bin/profile-obj
	$(CXX) $(CXXFLAGS) -I/opt/cuda/include -c $< -o $@

bin/gpuprofile: $(LIB_OBJECTS) bin/profile-obj/profile_kernel.o bin/profile-obj/profile_main.o
	$(CXX) $(CXXFLAGS) $^ -L/opt/cuda/lib64 -Wl,-rpath,/opt/cuda/lib64 -lcudart -o $@

# Seed enumerator with S1 `forbid` (AST pattern pruning; reports/seed-forbid-1110/).
# Same sources as bin/arcsearch, separate name so running binaries stay untouched.
# Usage: bin/arcbatch-forbid --batch --mode seed ... (configs may carry "forbid").
.PHONY: forbid
forbid: bin/arcbatch-forbid

bin/arcbatch-forbid: $(SOURCES) $(HEADERS) | bin
	$(CXX) $(CXXFLAGS) $(SOURCES) -o $@

# GPU seed layer (native/gpu/seed/, reports/seed-gpu-1110/): one seed Enumerator
# layer on the GPU vs the CPU Enumerator. host.cpp includes src/seed_enum.cpp,
# so that file is left out of the linked objects. Separate target: `make gpuseed`.
.PHONY: gpuseed
gpuseed: bin/gpuseed

SEED_GPU_SOURCES := $(filter-out src/main.cpp src/seed_enum.cpp,$(SOURCES))
SEED_GPU_OBJECTS := $(patsubst src/%.cpp,gpu/seed/obj/%.o,$(SEED_GPU_SOURCES))

gpu/seed/obj/%.o: src/%.cpp $(HEADERS)
	mkdir -p gpu/seed/obj
	$(CXX) $(CXXFLAGS) -c $< -o $@

gpu/seed/obj/kernel.o: gpu/seed/kernel.cu gpu/seed/gpuseed.hpp
	mkdir -p gpu/seed/obj
	$(NVCC) $(NVFLAGS) -c $< -o $@

gpu/seed/obj/host.o: gpu/seed/host.cpp gpu/seed/gpuseed.hpp $(HEADERS) src/seed_enum.cpp
	mkdir -p gpu/seed/obj
	$(CXX) $(CXXFLAGS) -c $< -o $@

bin/gpuseed: $(SEED_GPU_OBJECTS) gpu/seed/obj/host.o gpu/seed/obj/kernel.o | bin
	$(CXX) $(CXXFLAGS) $^ -L/opt/cuda/lib64 -Wl,-rpath,/opt/cuda/lib64 -lcudart -o $@

# GPU seed layer inside the real seed search (N5c, reports/seed-gpu-e2e-1110/):
# bin/arcbatch-gpuseed = bin/arcbatch plus --gpu-seed / --gpu-min N / --seed-prof.
# src/ stays untouched: main.cpp is compiled with -Dmain=arcsearch_main and
# wrapped by gpu/seed/e2e_main.cpp; gpu/seed/seed_enum_gpu.cpp is a modified
# copy of src/seed_enum.cpp (so that file is left out). Separate target: `make gpuseed-e2e`.
.PHONY: gpuseed-e2e
gpuseed-e2e: bin/arcbatch-gpuseed

E2E_DIR := gpu/seed/obj-e2e
E2E_HEADERS := gpu/seed/e2e.hpp gpu/seed/gpuseed.hpp

$(E2E_DIR)/main.o: src/main.cpp $(HEADERS)
	mkdir -p $(E2E_DIR)
	$(CXX) $(CXXFLAGS) -Dmain=arcsearch_main -c $< -o $@

$(E2E_DIR)/seed_enum_gpu.o: gpu/seed/seed_enum_gpu.cpp $(E2E_HEADERS) $(HEADERS)
	mkdir -p $(E2E_DIR)
	$(CXX) $(CXXFLAGS) -Isrc -c $< -o $@

$(E2E_DIR)/e2e_main.o: gpu/seed/e2e_main.cpp $(E2E_HEADERS)
	mkdir -p $(E2E_DIR)
	$(CXX) $(CXXFLAGS) -c $< -o $@

$(E2E_DIR)/e2e_kernel.o: gpu/seed/e2e_kernel.cu gpu/seed/kernel.cu $(E2E_HEADERS)
	mkdir -p $(E2E_DIR)
	$(NVCC) $(NVFLAGS) -c $< -o $@

bin/arcbatch-gpuseed: $(SEED_GPU_OBJECTS) $(E2E_DIR)/main.o $(E2E_DIR)/seed_enum_gpu.o $(E2E_DIR)/e2e_main.o $(E2E_DIR)/e2e_kernel.o | bin
	$(CXX) $(CXXFLAGS) $^ -L/opt/cuda/lib64 -Wl,-rpath,/opt/cuda/lib64 -lcudart -o $@

# gpgp-ho: gpgp built with holdout / MDL / min-simplify flags (reports/gpu-gp-1109/holdout.md).
# Same sources as gpgp but separate objects, so bin/gpgp is never relinked by this target.
.PHONY: gpugp-ho
gpugp-ho: bin/gpgp-ho

bin/gpho-obj/gp_kernel.o: gpu/gp/gp_kernel.cu gpu/gp/gp.hpp gpu/kernel.cu gpu/space.hpp gpu/gpu.hpp | bin
	mkdir -p bin/gpho-obj
	$(NVCC) $(NVFLAGS) -c $< -o $@

bin/gpho-obj/gp_main.o: gpu/gp/gp_main.cpp gpu/gp/gp.hpp gpu/space.hpp gpu/gpu.hpp $(HEADERS) | bin
	mkdir -p bin/gpho-obj
	$(CXX) $(CXXFLAGS) -I/opt/cuda/include -c $< -o $@

bin/gpgp-ho: $(LIB_OBJECTS) bin/gpho-obj/gp_kernel.o bin/gpho-obj/gp_main.o
	$(CXX) $(CXXFLAGS) $^ -L/opt/cuda/lib64 -Wl,-rpath,/opt/cuda/lib64 -lcudart -o $@

# M0 baseline profiler (reports/m0-baseline-1110/): bin/m0prof = bin/arcbatch with
# exclusive time buckets. gpu/seed/m0prof_enum.cpp is generated from src/seed_enum.cpp
# by gpu/seed/m0prof_mk.py (src/ untouched). CPU only. Separate target: `make m0prof`.
.PHONY: m0prof
m0prof: bin/m0prof

M0_DIR := gpu/seed/obj-m0

gpu/seed/m0prof_enum.cpp: src/seed_enum.cpp gpu/seed/m0prof_mk.py
	python3 -I gpu/seed/m0prof_mk.py src/seed_enum.cpp $@

$(M0_DIR)/%.o: gpu/seed/%.cpp gpu/seed/m0prof.hpp $(HEADERS)
	mkdir -p $(M0_DIR)
	$(CXX) $(CXXFLAGS) -Isrc -c $< -o $@

bin/m0prof: $(SEED_GPU_OBJECTS) $(E2E_DIR)/main.o $(M0_DIR)/m0prof_enum.o $(M0_DIR)/m0prof_main.o | bin
	$(CXX) $(CXXFLAGS) $^ -o $@

# E11/E17 prototype (reports/m0-baseline-1110/): GPU reverse synthesis of (input, program, output)
# samples from random first-order programs. Separate target: `make gpusynth`.
.PHONY: gpusynth
gpusynth: bin/gpusynth

bin/gpusynth: gpu/synth/gpusynth.cu | bin
	$(NVCC) $(NVFLAGS) $< -o $@

# E11 gpusynth v2 semantic check (reports/gpusynth-1110/): CPU re-evaluation of gpusynth samples
# with seed::eval. Own object dir. Separate target: `make gpusynth-verify`.
.PHONY: gpusynth-verify
gpusynth-verify: bin/gpusynth_verify
SYNTH_V_SOURCES := $(filter-out src/main.cpp,$(SOURCES))
SYNTH_V_OBJECTS := $(patsubst src/%.cpp,gpu/synth/obj/%.o,$(SYNTH_V_SOURCES))
gpu/synth/obj/%.o: src/%.cpp $(HEADERS)
	mkdir -p gpu/synth/obj
	$(CXX) $(CXXFLAGS) -c $< -o $@
bin/gpusynth_verify: gpu/synth/verify.cpp $(SYNTH_V_OBJECTS) $(HEADERS) | bin
	$(CXX) $(CXXFLAGS) gpu/synth/verify.cpp $(SYNTH_V_OBJECTS) -o $@

# R1 probe (reports/r1-probe-1110/): bin/arcbatch-r1 = bin/arcbatch with cost-bucketed enumeration
# (costs from $ARC_R1_COSTS). gpu/seed/r1_enum.cpp is generated from src/seed_enum.cpp by
# gpu/seed/r1_mk.py (src/ untouched). CPU only. Separate target: `make r1`.
.PHONY: r1
r1: bin/arcbatch-r1

R1_DIR := gpu/seed/obj-r1

gpu/seed/r1_enum.cpp: src/seed_enum.cpp gpu/seed/r1_mk.py
	python3 -I gpu/seed/r1_mk.py src/seed_enum.cpp $@

$(R1_DIR)/%.o: gpu/seed/%.cpp $(HEADERS)
	mkdir -p $(R1_DIR)
	$(CXX) $(CXXFLAGS) -Isrc -c $< -o $@

bin/arcbatch-r1: $(SEED_GPU_OBJECTS) $(E2E_DIR)/main.o $(R1_DIR)/r1_enum.o $(R1_DIR)/r1_main.o | bin
	$(CXX) $(CXXFLAGS) $^ -o $@

# bin/arcbatch-gpuseed-b1 (N5d / B1, reports/seed-gpu-b1-1110/): arcbatch-gpuseed with a
# resident per-thread device context (gpu/seed/b1_kernel.cu): decomposition sub-problems reuse
# stream, buffers, table and pinned staging; fewer stream ops per layer. Same host objects as
# arcbatch-gpuseed (interface e2e.hpp unchanged). Separate target: `make gpuseed-b1`.
.PHONY: gpuseed-b1
gpuseed-b1: bin/arcbatch-gpuseed-b1

$(E2E_DIR)/b1_kernel.o: gpu/seed/b1_kernel.cu gpu/seed/kernel.cu $(E2E_HEADERS)
	mkdir -p $(E2E_DIR)
	$(NVCC) $(NVFLAGS) -c $< -o $@

bin/arcbatch-gpuseed-b1: $(SEED_GPU_OBJECTS) $(E2E_DIR)/main.o $(E2E_DIR)/seed_enum_gpu.o $(E2E_DIR)/e2e_main.o $(E2E_DIR)/b1_kernel.o | bin
	$(CXX) $(CXXFLAGS) $^ -L/opt/cuda/lib64 -Wl,-rpath,/opt/cuda/lib64 -lcudart -o $@

# Isolated CPU seed hot paths (N8, reports/cpu-hot-1110/).
# A = allocation-safe lambda memo; B = enumerator bookkeeping.
.PHONY: hot
hot: bin/arcbatch-hot-a bin/arcbatch-hot

HOT_NAMES := $(notdir $(SOURCES:.cpp=.o))
HOT_A_OBJECTS := $(addprefix hot/obj-a/,$(HOT_NAMES)) hot/obj-a/batch_main.o
HOT_AB_OBJECTS := $(addprefix hot/obj-ab/,$(HOT_NAMES)) hot/obj-ab/batch_main.o

hot/obj-a/main.o hot/obj-ab/main.o: src/main.cpp $(HEADERS)
	mkdir -p $(@D)
	$(CXX) $(CXXFLAGS) -Dmain=arcsearch_main -c $< -o $@

hot/obj-a/batch_main.o hot/obj-ab/batch_main.o: hot/main.cpp
	mkdir -p $(@D)
	$(CXX) $(CXXFLAGS) -c $< -o $@

hot/obj-a/%.o: hot/%.cpp $(HEADERS)
	mkdir -p $(@D)
	$(CXX) $(CXXFLAGS) -Isrc -DHOT_A -c $< -o $@

hot/obj-ab/%.o: hot/%.cpp $(HEADERS)
	mkdir -p $(@D)
	$(CXX) $(CXXFLAGS) -Isrc -DHOT_A -DHOT_B -c $< -o $@

hot/obj-a/%.o: src/%.cpp $(HEADERS)
	mkdir -p $(@D)
	$(CXX) $(CXXFLAGS) -c $< -o $@

hot/obj-ab/%.o: src/%.cpp $(HEADERS)
	mkdir -p $(@D)
	$(CXX) $(CXXFLAGS) -c $< -o $@

bin/arcbatch-hot-a: $(HOT_A_OBJECTS) | bin
	$(CXX) $(CXXFLAGS) $^ -o $@

bin/arcbatch-hot: $(HOT_AB_OBJECTS) | bin
	$(CXX) $(CXXFLAGS) $^ -o $@

# N8b: instrumentation-only A+B binary; normal hot targets are unchanged.
.PHONY: hot-prof
hot-prof: bin/arcbatch-hot-prof

hot/prof/seed_enum.cpp hot/prof/seed_value.cpp &: hot/prof/generate.py hot/seed_enum.cpp hot/seed_value.cpp
	python3 -I hot/prof/generate.py

hot/obj-prof/%.o: hot/prof/%.cpp hot/prof/prof.hpp $(HEADERS)
	mkdir -p $(@D)
	$(CXX) $(CXXFLAGS) -Isrc -DHOT_A -DHOT_B -c $< -o $@

HOT_PROF_OBJECTS := $(filter-out hot/obj-ab/seed_enum.o hot/obj-ab/seed_value.o hot/obj-ab/batch_main.o,$(HOT_AB_OBJECTS)) \
                    hot/obj-prof/seed_enum.o hot/obj-prof/seed_value.o hot/obj-prof/main.o
bin/arcbatch-hot-prof: $(HOT_PROF_OBJECTS) | bin
	$(CXX) $(CXXFLAGS) $^ -o $@

# N8b C: A+B plus whole higher-order result memoization. Reuse identical A+B
# objects except the evaluator; neither existing hot target enables HOT_C.
.PHONY: hot2
hot2: bin/arcbatch-hot-c

hot/obj-c/seed_value.o: hot/seed_value.cpp hot/higher_cache.hpp $(HEADERS)
	mkdir -p $(@D)
	$(CXX) $(CXXFLAGS) -Isrc -DHOT_A -DHOT_B -DHOT_C -c $< -o $@

HOT_C_OBJECTS := $(filter-out hot/obj-ab/seed_value.o,$(HOT_AB_OBJECTS)) hot/obj-c/seed_value.o
bin/arcbatch-hot-c: $(HOT_C_OBJECTS) | bin
	$(CXX) $(CXXFLAGS) $^ -o $@

# N8b D is measured independently of C: A+B plus a reentrant result buffer.
hot2: bin/arcbatch-hot-d
hot/obj-d/seed_value.o: hot/seed_value.cpp hot/result_buffer.hpp $(HEADERS)
	mkdir -p $(@D)
	$(CXX) $(CXXFLAGS) -Isrc -DHOT_A -DHOT_B -DHOT_D -c $< -o $@

HOT_D_OBJECTS := $(filter-out hot/obj-ab/seed_value.o,$(HOT_AB_OBJECTS)) hot/obj-d/seed_value.o
bin/arcbatch-hot-d: $(HOT_D_OBJECTS) | bin
	$(CXX) $(CXXFLAGS) $^ -o $@

# N8c E: A+B plus read-only first-order batches over training examples.
.PHONY: hot-e
hot-e: bin/arcbatch-hot-e

hot/obj-e/seed_enum.o hot/obj-e/seed_value.o: hot/obj-e/%.o: hot/%.cpp hot/scalar_prims.hpp $(HEADERS)
	mkdir -p $(@D)
	$(CXX) $(CXXFLAGS) -Isrc -DHOT_A -DHOT_B -DHOT_E -c $< -o $@

HOT_E_OBJECTS := $(filter-out hot/obj-ab/seed_enum.o hot/obj-ab/seed_value.o,$(HOT_AB_OBJECTS)) \
                 hot/obj-e/seed_enum.o hot/obj-e/seed_value.o
bin/arcbatch-hot-e: $(HOT_E_OBJECTS) | bin
	$(CXX) $(CXXFLAGS) $^ -o $@
