#pragma once

#include <atomic>
#include <mutex>
#include <thread>
#include <opencv2/videoio.hpp>
#include <opencv2/core.hpp>

#include "PipelineContext.hpp"

class Camera {
public:
    explicit Camera(std::shared_ptr<PipelineContext> ctx,
                int warmup_frames = 30,
                bool autofocus    = false,
                int  focus_value  = 30);    
    ~Camera();

    bool init();
    void stop();
    bool is_open() const;

private:
    void set_focus(int value);
    void capture_loop();
    std::shared_ptr<PipelineContext> ctx_;
    cv::VideoCapture                 cap_;
    std::thread                      thread_;
    std::atomic<bool>                active_{false};
    bool                             autofocus_;     
    int                              warmup_frames_;
    int                              focus_value_;
};