#pragma once

#include <atomic>
#include <memory>
#include <string>
#include <thread>
#include <vector>

#include <opencv2/core.hpp>
#include <tensorflow/lite/interpreter.h>
#include <tensorflow/lite/model_builder.h>
#include <tensorflow/lite/kernels/register.h>
#include <tensorflow/lite/delegates/xnnpack/xnnpack_delegate.h>

#include "PipelineContext.hpp"

class Detector {
public:
    explicit Detector(std::shared_ptr<PipelineContext> ctx,
                      const std::string& model_path,
                      float conf_threshold = 0.5f,
                      int   num_threads    = 3,
                      bool  debug          = false);
    ~Detector();

    bool init();
    void stop();

private:
    void detect_loop();
    void preprocess(const cv::Mat& frame);
    std::vector<DetectionResult> postprocess(const cv::Mat& source_frame);
    cv::Mat prepare_crop(const cv::Mat& frame, const cv::Rect& box);

    std::shared_ptr<PipelineContext>            ctx_;
    std::string                                 model_path_;
    float                                       conf_threshold_;
    int                                         num_threads_;
    bool                                        debug_;

    std::unique_ptr<tflite::FlatBufferModel>    model_;
    std::unique_ptr<tflite::Interpreter>        interpreter_;
    TfLiteDelegate*                             xnnpack_delegate_{nullptr};

    std::thread                                 thread_;
    std::atomic<bool>                           active_{false};

    // Read from model at init time
    int input_width_{640};
    int input_height_{640};
    int num_rows_{5};       // 4 box coords + num_classes
    int num_anchors_{3549}; // read dynamically from output tensor
};