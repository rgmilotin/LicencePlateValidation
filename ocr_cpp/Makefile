CXX      = g++
CXXFLAGS = -Wall -Wextra -O2 -std=c++17 -Iinclude -I/usr/local/include

OPENCV      = $(shell pkg-config --cflags opencv4)
OPENCV_LIBS = $(shell pkg-config --libs opencv4)

TFLITE_LIBS = -L/usr/local/lib -ltensorflow-lite
TESS        = -ltesseract
MYSQL_LIBS  = -lmariadb

SRC    = $(shell find src -name "*.cpp")
OBJ    = $(SRC:src/%.cpp=build/%.o)
TARGET = build/my_app

all: $(TARGET)

$(TARGET): $(OBJ)
	@mkdir -p build
	$(CXX) $(CXXFLAGS) $^ -o $@ $(OPENCV_LIBS) $(TFLITE_LIBS) $(TESS) $(MYSQL_LIBS) -pthread

build/%.o: src/%.cpp
	@mkdir -p build
	$(CXX) $(CXXFLAGS) $(OPENCV) -c $< -o $@

clean:
	rm -rf build