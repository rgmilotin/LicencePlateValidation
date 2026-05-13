
#pragma once
#include <opencv2/opencv.hpp>
#include <thread>
#include <mutex>
#include <atomic>

class Camera {
public:
    Camera();  // constructor
    ~Camera(); // destructor, closes thread and stops camera

    bool init(); // initializes the camera pipeline and starts a recording thread
    cv::Mat getLatestFrame(); // return a clone of the last frame
    bool isRunning() const { return running.load(); }

private:
    void captureLoop(); // the function running in the thread, captures the frames at 30FPS

    cv::VideoCapture cap;
    cv::Mat latestFrame;
    std::thread captureThread;
    std::mutex frameMutex;
    std::atomic<bool> running;
    std::atomic<bool> frameReady;
};