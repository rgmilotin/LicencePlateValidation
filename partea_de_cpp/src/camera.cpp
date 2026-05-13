#include "camera.hpp"
#include <iostream>

Camera::Camera() : running(false), frameReady(false) {}

Camera::~Camera() {
    running = false;
    if (captureThread.joinable()) {
        captureThread.join();
    }
    if (cap.isOpened()) {
        cap.release();
    }
}

bool Camera::init() {
    std::string pipeline =
        "libcamerasrc ! video/x-raw,width=640,height=480,framerate=30/1 "
        "! videoconvert ! video/x-raw,format=BGR "
        "! appsink drop=true max-buffers=1 sync=false";

    cap.open(pipeline, cv::CAP_GSTREAMER);
    if (!cap.isOpened()) {
        std::cerr << "ERROR: Failed to open camera pipeline\n";
        return false;
    }

    running = true;
    captureThread = std::thread(&Camera::captureLoop, this);
    std::cout << "Camera initialized, capture thread started\n";
    return true;
}

void Camera::captureLoop() {
    cv::Mat frame;
    int warmupFrames = 30;
    int count = 0;

    while (running) {
        if (!cap.grab()) {
            std::cerr << "WARNING: grab() failed\n";
            continue;
        }

        cap.retrieve(frame);

        if (frame.empty()) {
            std::cerr << "WARNING: Empty frame\n";
            continue;
        }

        // Discard warmup frames silently
        if (count < warmupFrames) {
            count++;
            continue;
        }

        {
            std::lock_guard<std::mutex> lock(frameMutex);
            latestFrame = frame.clone();
            frameReady = true;
        }
    }
}

cv::Mat Camera::getLatestFrame() {
    std::lock_guard<std::mutex> lock(frameMutex);
    if (latestFrame.empty()) {
        std::cerr << "WARNING: No frame available yet\n";
    }
    return latestFrame.clone();
}