#include "Camera.hpp"
#include <iostream>

Camera::Camera(std::shared_ptr<PipelineContext> ctx, int warmup_frames, bool autofocus, int focus_value)
    : ctx_(std::move(ctx))
    , warmup_frames_(warmup_frames)
    , autofocus_(autofocus)
    , focus_value_(focus_value)
{}

Camera::~Camera() {
    stop();
}

void Camera::set_focus(int value) {
    // Disable continuous autofocus first, then set manual value
    int ret = 0;
    ret += std::system("v4l2-ctl --set-ctrl=focus_automatic_continuous=0");
    ret += std::system(("v4l2-ctl --set-ctrl=focus_absolute=" + std::to_string(value)).c_str());

    if (ret != 0)
        std::cerr << "[Camera] WARNING: Focus control may not be supported on this hardware\n";
    else
        std::cout << "[Camera] Focus set to " << value << "\n";
}

bool Camera::init() {
    if (!autofocus_)
        set_focus(focus_value_);
    std::string pipeline =
        "libcamerasrc ! video/x-raw,width=640,height=480,framerate=30/1 "
        "! videoconvert ! video/x-raw,format=BGR "
        "! appsink drop=true max-buffers=1 sync=false";

    cap_.open(pipeline, cv::CAP_GSTREAMER);

    if (!cap_.isOpened()) {
        std::cerr << "[Camera] Failed to open pipeline\n";
        return false;
    }

    active_.store(true);
    thread_ = std::thread(&Camera::capture_loop, this);
    std::cout << "[Camera] Initialized, capture thread started\n";
    return true;
}

void Camera::stop() {
    active_.store(false);

    if (thread_.joinable())
        thread_.join();

    if (cap_.isOpened())
        cap_.release();
}

bool Camera::is_open() const {
    return cap_.isOpened();
}

void Camera::capture_loop() {
    cv::Mat frame;
    int count = 0;

    while (active_.load() && ctx_->running.load()) {
        if (!cap_.grab()) {
            std::cerr << "[Camera] grab() failed\n";
            continue;
        }

        cap_.retrieve(frame);

        if (frame.empty()) {
            std::cerr << "[Camera] Empty frame\n";
            continue;
        }

        // Discard warmup frames silently
        if (count < warmup_frames_) {
            count++;
            continue;
        }

        {
            std::lock_guard<std::mutex> lock(ctx_->frame_mutex);
            frame.copyTo(ctx_->latest_frame);
        }
    }

    std::cout << "[Camera] Capture loop exited\n";
}