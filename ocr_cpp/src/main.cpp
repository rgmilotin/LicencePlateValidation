#include <iostream>
#include <memory>
#include <csignal>
#include <thread>
#include <chrono>
#include <iomanip>
#include <sstream>

#include "PipelineContext.hpp"
#include "Camera.hpp"
#include "Detector.hpp"

static std::shared_ptr<PipelineContext> g_ctx;

void signal_handler(int signal) {
    std::cout << "\n[Main] Caught signal " << signal << ", shutting down...\n";
    if (g_ctx)
        g_ctx->running.store(false);
}

// Drain the OCR queue and print whatever the detector put in it
void print_detections(std::shared_ptr<PipelineContext>& ctx) {
    std::unique_lock<std::mutex> lock(ctx->ocr_mutex);

    while (!ctx->ocr_queue.empty()) {
        DetectionResult det = std::move(ctx->ocr_queue.front());
        ctx->ocr_queue.pop();
        lock.unlock();

        // Format timestamp
        auto time  = std::chrono::system_clock::to_time_t(det.timestamp);
        auto ms    = std::chrono::duration_cast<std::chrono::milliseconds>(
                         det.timestamp.time_since_epoch()) % 1000;

        std::cout << "[Detection] "
                  << std::put_time(std::localtime(&time), "%H:%M:%S")
                  << "." << std::setfill('0') << std::setw(3) << ms.count()
                  << "  conf=" << std::fixed << std::setprecision(2) << det.confidence
                  << "  crop=" << det.crop.cols << "x" << det.crop.rows
                  << "\n";

        lock.lock();
    }

    // Notify detector that space is free in the queue
    ctx->ocr_cv.notify_all();
}

int main() {
    std::signal(SIGINT,  signal_handler);
    std::signal(SIGTERM, signal_handler);

    auto ctx = std::make_shared<PipelineContext>();
    g_ctx = ctx;

    // Camera
    Camera camera(ctx, /*warmup_frames=*/30, /*autofocus=*/false, /*focus_value=*/40);
    if (!camera.init()) {
        std::cerr << "[Main] Camera init failed, exiting\n";
        return 1;
    }

    // Detector — point to your .tflite model
    Detector detector(ctx,
                  "/opt/ocr/models/license_plate_detector.tflite",
                  /*conf_threshold=*/0.5f,
                  /*num_threads=*/3,
                  /*debug=*/true);
    if (!detector.init()) {
        std::cerr << "[Main] Detector init failed, exiting\n";
        return 1;
    }

    std::cout << "[Main] Pipeline running. Press Ctrl+C to stop.\n";

    while (ctx->running.load()) {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        print_detections(ctx);
    }

    std::cout << "[Main] Shutdown complete\n";
    return 0;
}