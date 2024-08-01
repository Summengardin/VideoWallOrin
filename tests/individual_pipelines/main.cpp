#include <iostream>
#include <string>
#include <map>
#include <thread>
#include <vector>
#include <gst/gst.h>

struct CameraProperties {
    int width;
    int height;
    std::string framerate;
    std::string format;
};

void launch_camera(const std::string& cam, const std::string& dbg) {
    // Properties for each camera
    std::map<std::string, CameraProperties> camera_properties = {
        {"10.1.3.75", {1920, 1080, "54/1", "rggb"}},
        {"10.1.3.74", {1920, 1080, "100/1", "rggb"}},
        {"10.1.3.76", {1920, 1080, "100/1", "rggb"}},
        {"10.1.3.77", {1920, 1080, "100/1", "rggb"}}
    };

    // Determine camera properties
    if (camera_properties.find(cam) != camera_properties.end()) {
        CameraProperties props = camera_properties[cam];
        int width = props.width;
        int height = props.height;
        std::string framerate = props.framerate;
        std::string format = props.format;

        // Initialize GStreamer
        gst_init(nullptr, nullptr);

        // Create GStreamer pipeline elements
        GstElement* pipeline = gst_pipeline_new("camera-pipeline");
        GstElement* source = gst_element_factory_make("aravissrc", "source");
        GstElement* capsfilter = gst_element_factory_make("capsfilter", "caps");
        GstElement* tcamconvert = gst_element_factory_make("tcamconvert", "tcamconvert");
        GstElement* videoconvert = gst_element_factory_make("videoconvert", "videoconvert");
        GstElement* sink = gst_element_factory_make("xvimagesink", "sink");

        if (!pipeline || !source || !capsfilter || !tcamconvert || !videoconvert || !sink) {
            std::cerr << "Not all elements could be created." << std::endl;
            return;
        }

        // Set element properties
        g_object_set(source, "camera-name", cam.c_str(), nullptr);
        g_object_set(sink, "sync", FALSE, nullptr);

        // Create capabilities string
        std::string caps_str = "video/x-bayer,width=" + std::to_string(width) +
                               ",height=" + std::to_string(height) +
                               ",framerate=" + framerate +
                               ",format=" + format;
        GstCaps* caps = gst_caps_from_string(caps_str.c_str());
        g_object_set(capsfilter, "caps", caps, nullptr);
        gst_caps_unref(caps);

        // Build the pipeline
        gst_bin_add_many(GST_BIN(pipeline), source, capsfilter, tcamconvert, videoconvert, sink, nullptr);
        if (!gst_element_link_many(source, capsfilter, tcamconvert, videoconvert, sink, nullptr)) {
            std::cerr << "Elements could not be linked." << std::endl;
            gst_object_unref(pipeline);
            return;
        }

        // Start playing
        gst_element_set_state(pipeline, GST_STATE_PLAYING);

        // Wait until error or EOS
        GstBus* bus = gst_element_get_bus(pipeline);
        GstMessage* msg = gst_bus_timed_pop_filtered(bus, GST_CLOCK_TIME_NONE, static_cast<GstMessageType>(GST_MESSAGE_ERROR | GST_MESSAGE_EOS));

        // Parse message
        if (msg) {
            if (GST_MESSAGE_TYPE(msg) == GST_MESSAGE_ERROR) {
                GError* err;
                gchar* debug_info;
                gst_message_parse_error(msg, &err, &debug_info);
                std::cerr << "Error: " << err->message << ", " << debug_info << std::endl;
                g_clear_error(&err);
                g_free(debug_info);
            } else if (GST_MESSAGE_TYPE(msg) == GST_MESSAGE_EOS) {
                std::cout << "End-Of-Stream reached" << std::endl;
            }
            gst_message_unref(msg);
        }

        // Free resources
        gst_object_unref(bus);
        gst_element_set_state(pipeline, GST_STATE_NULL);
        gst_object_unref(pipeline);
    } else {
        std::cerr << "Camera IP " << cam << " not recognized." << std::endl;
    }
}

int main(int argc, char* argv[]) {
    // Default values
    std::vector<std::string> cam_default = {"10.1.3.75", "10.1.3.74", "10.1.3.76", "10.1.3.77"};
    std::string dbg_default = "0";

    // Parse command-line arguments
    std::vector<std::string> cams;
    std::string dbg = dbg_default;

    if (argc > 1) {
        for (int i = 1; i < argc; ++i) {
            cams.push_back(argv[i]);
        }
    } else {
        cams = cam_default;
    }

    // Launch camera threads
    std::vector<std::thread> threads;
    for (const auto& cam : cams) {
        threads.emplace_back(launch_camera, cam, dbg);
    }

    // Join threads
    for (auto& thread : threads) {
        thread.join();
    }

    return 0;
}
