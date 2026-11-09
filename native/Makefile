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
