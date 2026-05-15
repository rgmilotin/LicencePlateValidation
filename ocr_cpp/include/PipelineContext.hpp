#pragma once

#include <atomic>
#include <condition_variable>
#include <mutex>
#include <queue>
#include <string>
#include <chrono>
#include <opencv2/core.hpp>

struct DetectionResult {
    cv::Mat                                crop;
    float                                  confidence;
    std::chrono::system_clock::time_point  timestamp;
};

struct PipelineContext {
    // Q1 — shared frame slot (camera overwrites, detector reads latest)
    cv::Mat                       latest_frame;
    std::mutex                    frame_mutex;

    // Q2 — detector → OCR
    std::queue<DetectionResult>   ocr_queue;
    std::mutex                    ocr_mutex;
    std::condition_variable       ocr_cv;
    const int                     ocr_queue_maxsize = 4;

    // Pipe writer queue
    std::queue<std::string>       pipe_queue;
    std::mutex                    pipe_mutex;
    std::condition_variable       pipe_cv;

    // Shutdown signal
    std::atomic<bool>             running{true};
};