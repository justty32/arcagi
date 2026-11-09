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
