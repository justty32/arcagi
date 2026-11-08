CXX := g++
CXXFLAGS := -std=c++20 -O2 -Wall -Wextra
SOURCES := $(wildcard src/*.cpp)
HEADERS := $(wildcard src/*.hpp)

.PHONY: all spec
all: bin/arcsearch spec bin/solve

bin:
	mkdir -p bin

bin/arcsearch: $(SOURCES) $(HEADERS) | bin
	$(CXX) $(CXXFLAGS) $(SOURCES) -o $@

spec:
	cd .. && PYTHONDONTWRITEBYTECODE=1 UV_CACHE_DIR="$$PWD/native/.uv-cache" uv run --no-sync python native/export_spec.py > native/spec.json

bin/solve: solve.sh | bin
	cp solve.sh $@
	chmod +x $@
