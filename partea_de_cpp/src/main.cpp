#include <iostream>
#include <opencv2/opencv.hpp>

#include "detector.hpp"
#include "ocr.hpp"

int main(int argc, char** argv) {

    std::string imagePath = "assets/test.jpg";

    if (argc > 1) {
        imagePath = argv[1];
    }

    // Load image
    cv::Mat img = cv::imread(imagePath);

    if (img.empty()) {
        std::cerr << "Error: cannot load image: " << imagePath << std::endl;
        return 1;
    }

    std::cout << "Image loaded successfully\n";

    // Step 1: detection (placeholder)
    cv::Mat plateRegion = detectPlate(img);

    if (plateRegion.empty()) {
        std::cerr << "No plate detected\n";
        return 1;
    }

    // Step 2: OCR
    std::string text = runOCR(plateRegion);

    std::cout << "Detected text: " << text << std::endl;

    return 0;
}
