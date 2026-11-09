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
