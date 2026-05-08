CXX = g++
CXXFLAGS = -Wall -Wextra -O2 -std=c++17 -Iinclude

OPENCV = $(shell pkg-config --cflags opencv4)
OPENCV_LIBS = $(shell pkg-config --libs opencv4)
TESS = -ltesseract

SRC = $(shell find src -name "*.cpp")
OBJ = $(SRC:src/%.cpp=build/%.o)

TARGET = build/my_app

all: $(TARGET)

$(TARGET): $(OBJ)
	@mkdir -p build
	$(CXX) $(CXXFLAGS) $^ -o $@ $(OPENCV_LIBS) $(TESS)

build/%.o: src/%.cpp
	@mkdir -p build
	$(CXX) $(CXXFLAGS) $(OPENCV) -c $< -o $@

clean:
	rm -rf build
