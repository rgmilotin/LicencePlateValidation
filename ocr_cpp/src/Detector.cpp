#include "Detector.hpp"

#include <iostream>
#include <algorithm>
#include <chrono>

#include <opencv2/imgproc.hpp>
#include <opencv2/imgcodecs.hpp>

// ─────────────────────────────────────────────
//  Constructor / Destructor
// ─────────────────────────────────────────────

Detector::Detector(std::shared_ptr<PipelineContext> ctx,
                   const std::string& model_path,
                   float conf_threshold,
                   int   num_threads,
                   bool  debug)
    : ctx_(std::move(ctx))
    , model_path_(model_path)
    , conf_threshold_(conf_threshold)
    , num_threads_(num_threads)
    , debug_(debug)
{}

Detector::~Detector() {
    stop();

    if (xnnpack_delegate_) {
        TfLiteXNNPackDelegateDelete(xnnpack_delegate_);
        xnnpack_delegate_ = nullptr;
    }
}

// ─────────────────────────────────────────────
//  Init
// ─────────────────────────────────────────────

bool Detector::init() {
    model_ = tflite::FlatBufferModel::BuildFromFile(model_path_.c_str());
    if (!model_) {
        std::cerr << "[Detector] Failed to load model from: " << model_path_ << "\n";
        return false;
    }

    tflite::ops::builtin::BuiltinOpResolver resolver;
    tflite::InterpreterBuilder builder(*model_, resolver);
    builder(&interpreter_);

    if (!interpreter_) {
        std::cerr << "[Detector] Failed to build interpreter\n";
        return false;
    }

    interpreter_->SetNumThreads(num_threads_);

    TfLiteXNNPackDelegateOptions xnnpack_opts = TfLiteXNNPackDelegateOptionsDefault();
    xnnpack_opts.num_threads = num_threads_;
    xnnpack_delegate_ = TfLiteXNNPackDelegateCreate(&xnnpack_opts);

    if (interpreter_->ModifyGraphWithDelegate(xnnpack_delegate_) != kTfLiteOk) {
        std::cerr << "[Detector] WARNING: XNNPACK delegate failed, falling back to CPU\n";
        TfLiteXNNPackDelegateDelete(xnnpack_delegate_);
        xnnpack_delegate_ = nullptr;
    }

    if (interpreter_->AllocateTensors() != kTfLiteOk) {
        std::cerr << "[Detector] Failed to allocate tensors\n";
        return false;
    }

    // Read input dimensions
    const auto* input_tensor = interpreter_->input_tensor(0);
    input_height_ = input_tensor->dims->data[1];
    input_width_  = input_tensor->dims->data[2];

    std::cout << "[Detector] Model loaded: " << input_width_ << "x" << input_height_ << "\n";

    // ── Print tensor shapes for debugging ───────────────────────
    std::cout << "[Detector] --- Tensor layout ---\n";
    for (int idx : interpreter_->inputs()) {
        const TfLiteTensor* t = interpreter_->tensor(idx);
        std::cout << "[Detector] Input  shape: ";
        for (int d = 0; d < t->dims->size; ++d)
            std::cout << t->dims->data[d] << " ";
        std::cout << "\n";
    }
    for (int idx : interpreter_->outputs()) {
        const TfLiteTensor* t = interpreter_->tensor(idx);
        std::cout << "[Detector] Output shape: ";
        for (int d = 0; d < t->dims->size; ++d)
            std::cout << t->dims->data[d] << " ";
        std::cout << "\n";
    }

    // Read output shape dynamically so postprocess always matches
    const auto* out_tensor = interpreter_->output_tensor(0);
    // Expected: [1, num_rows, num_anchors]
    // num_rows = 4 (box) + num_classes
    if (out_tensor->dims->size == 3) {
        num_rows_    = out_tensor->dims->data[1];
        num_anchors_ = out_tensor->dims->data[2];
    } else {
        std::cerr << "[Detector] WARNING: Unexpected output tensor rank: "
                  << out_tensor->dims->size << "\n";
    }

    std::cout << "[Detector] num_rows=" << num_rows_
              << " num_anchors=" << num_anchors_
              << " num_classes=" << (num_rows_ - 4) << "\n";
    std::cout << "[Detector] -------------------\n";
    // ────────────────────────────────────────────────────────────

    if (debug_) {
        std::system("mkdir -p /tmp/ocr_debug");
        std::cout << "[Detector] Debug mode ON — frames saved to /tmp/ocr_debug/\n";
    }

    active_.store(true);
    thread_ = std::thread(&Detector::detect_loop, this);
    std::cout << "[Detector] Detection thread started\n";
    return true;
}

void Detector::stop() {
    active_.store(false);
    if (thread_.joinable())
        thread_.join();
}

// ─────────────────────────────────────────────
//  Detection loop
// ─────────────────────────────────────────────

void Detector::detect_loop() {
    cv::Mat frame_copy;

    auto last_time = std::chrono::steady_clock::now();

    while (active_.load() && ctx_->running.load()) {
        {
            std::lock_guard<std::mutex> lock(ctx_->frame_mutex);
            if (ctx_->latest_frame.empty())
                continue;
            ctx_->latest_frame.copyTo(frame_copy);
        }

        preprocess(frame_copy);

        if (interpreter_->Invoke() != kTfLiteOk) {
            std::cerr << "[Detector] Inference failed\n";
            continue;
        }

        auto results = postprocess(frame_copy);

        // ── Timing ──────────────────────────────────────────────
        auto now     = std::chrono::steady_clock::now();
        auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>
                           (now - last_time).count();
        last_time    = now;

        std::cout << "[Detector] inference_time=" << elapsed << "ms"
                  << "  detections=" << results.size()
                  << "\n";
        // ────────────────────────────────────────────────────────

        for (auto& det : results) {
            std::unique_lock<std::mutex> lock(ctx_->ocr_mutex);
            ctx_->ocr_cv.wait(lock, [this] {
                return (int)ctx_->ocr_queue.size() < ctx_->ocr_queue_maxsize
                       || !active_.load();
            });
            if (!active_.load()) break;
            ctx_->ocr_queue.push(std::move(det));
            lock.unlock();
            ctx_->ocr_cv.notify_one();
        }
    }

    std::cout << "[Detector] Detection loop exited\n";
}

// ─────────────────────────────────────────────
//  Preprocessing
// ─────────────────────────────────────────────

void Detector::preprocess(const cv::Mat& frame) {
    cv::Mat resized;
    cv::resize(frame, resized, cv::Size(input_width_, input_height_));

    cv::Mat rgb;
    cv::cvtColor(resized, rgb, cv::COLOR_BGR2RGB);

    float* input_data = interpreter_->typed_input_tensor<float>(0);
    const int total   = input_width_ * input_height_ * 3;

    for (int i = 0; i < total; ++i)
        input_data[i] = rgb.data[i] / 255.0f;
}

// ─────────────────────────────────────────────
//  Postprocessing
// ─────────────────────────────────────────────

// YOLOv8 TFLite output layout: [1, num_rows, num_anchors]
//   Rows 0-3 : cx, cy, w, h  (normalized 0..1 relative to input size)
//   Rows 4.. : one score per class (single class model = row 4 only)
//
// Confidence = max class score across rows 4..num_rows-1
// Coordinates are normalized relative to model input size (not source frame)

std::vector<DetectionResult> Detector::postprocess(const cv::Mat& source_frame) {
    const float* output = interpreter_->typed_output_tensor<float>(0);

    const int src_w     = source_frame.cols;
    const int src_h     = source_frame.rows;
    const int num_class = num_rows_ - 4;

    std::vector<DetectionResult> results;

    cv::Mat debug_frame;
    if (debug_)
        debug_frame = source_frame.clone();

    for (int a = 0; a < num_anchors_; ++a) {

        // Find max class score across all class rows
        float conf = 0.0f;
        for (int c = 0; c < num_class; ++c)
            conf = std::max(conf, output[(4 + c) * num_anchors_ + a]);

        if (conf < conf_threshold_)
            continue;

        // Box coordinates — normalized to model input size
        float cx = output[0 * num_anchors_ + a];
        float cy = output[1 * num_anchors_ + a];
        float w  = output[2 * num_anchors_ + a];
        float h  = output[3 * num_anchors_ + a];

        // Convert to pixel coords on source frame
        int x1 = static_cast<int>((cx - w / 2.0f) * src_w);
        int y1 = static_cast<int>((cy - h / 2.0f) * src_h);
        int bw = static_cast<int>(w * src_w);
        int bh = static_cast<int>(h * src_h);

        // Clamp to frame bounds
        x1 = std::max(0, x1);
        y1 = std::max(0, y1);
        bw = std::min(bw, src_w - x1);
        bh = std::min(bh, src_h - y1);

        if (bw <= 0 || bh <= 0)
            continue;

        cv::Rect box(x1, y1, bw, bh);

        if (debug_) {
            cv::rectangle(debug_frame, box, cv::Scalar(0, 255, 0), 2);

            std::string label = "plate " + std::to_string(conf).substr(0, 4);
            int baseline = 0;
            cv::Size text_size = cv::getTextSize(label, cv::FONT_HERSHEY_SIMPLEX,
                                                  0.6, 2, &baseline);
            cv::Point label_pos(x1, std::max(y1 - 5, text_size.height));

            cv::rectangle(debug_frame,
                          label_pos + cv::Point(0, baseline),
                          label_pos + cv::Point(text_size.width, -text_size.height),
                          cv::Scalar(0, 0, 0), cv::FILLED);

            cv::putText(debug_frame, label, label_pos,
                        cv::FONT_HERSHEY_SIMPLEX, 0.6,
                        cv::Scalar(0, 255, 0), 2);

            std::cout << "[Detector] Detection — box=("
                      << x1 << "," << y1 << " " << bw << "x" << bh << ")"
                      << " conf=" << conf << "\n";
        }

        cv::Mat crop = prepare_crop(source_frame, box);
        if (crop.empty())
            continue;

        DetectionResult det;
        det.crop       = std::move(crop);
        det.confidence = conf;
        det.timestamp  = std::chrono::system_clock::now();
        results.push_back(std::move(det));
    }

    if (debug_ && !results.empty()) {
        static int frame_idx = 0;
        std::string path = "/tmp/ocr_debug/frame_" +
                           std::to_string(frame_idx++) + ".jpg";
        cv::imwrite(path, debug_frame);
        std::cout << "[Detector] Debug frame saved: " << path << "\n";
    }

    return results;
}

// ─────────────────────────────────────────────
//  Crop preparation
// ─────────────────────────────────────────────

cv::Mat Detector::prepare_crop(const cv::Mat& frame, const cv::Rect& box) {
    if (box.width <= 0 || box.height <= 0 || box.area() == 0) {
        std::cerr << "[Detector] Skipping degenerate crop: "
                  << box.width << "x" << box.height << "\n";
        return cv::Mat();
    }

    cv::Mat crop = frame(box).clone();

    const int target_height = 64;
    float scale      = static_cast<float>(target_height) / crop.rows;
    int target_width = static_cast<int>(crop.cols * scale);

    if (target_width <= 0) {
        std::cerr << "[Detector] Skipping crop with zero target width\n";
        return cv::Mat();
    }

    cv::resize(crop, crop, cv::Size(target_width, target_height));

    cv::cvtColor(crop, crop, cv::COLOR_BGR2GRAY);

    cv::Ptr<cv::CLAHE> clahe = cv::createCLAHE(2.0, cv::Size(8, 8));
    clahe->apply(crop, crop);

    cv::adaptiveThreshold(crop, crop,
                          255,
                          cv::ADAPTIVE_THRESH_GAUSSIAN_C,
                          cv::THRESH_BINARY,
                          11, 2);

    return crop;
}