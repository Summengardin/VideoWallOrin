#include <arv.h>
#include <iostream>
#include <thread>
#include <atomic>
#include <gst/gst.h>
#include <gst/app/gstappsrc.h>
#include <vector>
#include <string.h>
#include <cstring>

std::atomic<bool> running(true);
std::vector<uint8_t> frame_data;
int frame_width, frame_height;
std::thread grabber_thread;

void frame_grabber(ArvCamera *camera, ArvStream *stream, std::vector<uint8_t> &frame_data, int width, int height) {
    GError *error = nullptr;
    arv_camera_start_acquisition(camera, &error);
    if (error) {
        std::cerr << "Error starting acquisition: " << error->message << std::endl;
        g_error_free(error);
        return;
    }


    while (running) {
        ArvBuffer *buffer = arv_stream_timeout_pop_buffer(stream, 200000);
        if (buffer) {
            if (arv_buffer_get_status(buffer) == ARV_BUFFER_STATUS_SUCCESS) {
                size_t size;
                const uint8_t *data = static_cast<const uint8_t *>(arv_buffer_get_data(buffer, &size));
                std::copy(data, data + size, frame_data.begin());
            }
            arv_stream_push_buffer(stream, buffer);
        }
    }

    arv_camera_stop_acquisition(camera, &error);
    if (error) {
        std::cerr << "Error stopping acquisition: " << error->message << std::endl;
        g_error_free(error);
    }
}

extern "C" {
    
    void start_frame_grabber(int width, int height, int framerate, const char* camera_name) {
        frame_width = width;
        frame_height = height;
        frame_data.resize(frame_width * frame_height);

        arv_update_device_list();

        GError *error = nullptr;
        ArvCamera *camera = arv_camera_new(camera_name, &error);
        if (!camera) {
            std::cerr << "Error creating camera" << std::endl;
            if(error) {
                std::cerr << "Error: " << error->message << std::endl;
                g_error_free(error);
            }
            return;
        }

        arv_camera_set_region(camera, 0, 0, width, height, &error);
        if (error) {
            std::cerr << "Error setting region: " << error->message << std::endl;
            g_error_free(error);
            return;
        }
        
        arv_camera_set_frame_rate(camera, framerate, &error);
        if (error) {
            std::cerr << "Error setting frame rate: " << error->message << std::endl;
            g_error_free(error);
            return;
        }

        arv_camera_set_pixel_format(camera, ARV_PIXEL_FORMAT_BAYER_RG_8, &error);
        if (error) {
            std::cerr << "Error setting pixel format: " << error->message << std::endl;
            g_error_free(error);
            return;
        }

        ArvStream *stream = arv_camera_create_stream(camera, nullptr, nullptr, &error);
        if (!stream) {
            std::cerr << "Failed to create stream." << std::endl;
            if (error) {
                std::cerr << "Error: " << error->message << std::endl;
                g_error_free(error);
            }
            return;
        }


        for (int i = 0; i < 10; i++) {
            arv_stream_push_buffer(stream, arv_buffer_new_allocate(arv_camera_get_payload(camera, &error)));
            if (error) {
                std::cerr << "Error getting payload: " << error->message << std::endl;
                g_error_free(error);
            }
        }

        std::cout << "Starting frame grabber" << std::endl;
        grabber_thread = std::thread(frame_grabber, camera, stream, std::ref(frame_data), frame_width, frame_height);
    }


    void stop_frame_grabber() {
        // std::cout << "Stopping frame grabber" << std::endl;
        running = false;
        if (grabber_thread.joinable()) {
            grabber_thread.join();
        }

        std::cout << "Frame grabber stopped" << std::endl;
    }

    void get_frame(uint8_t *buffer) {
        std::memcpy(buffer, frame_data.data(), frame_data.size());
    }

}

/*
void push_frame_to_gst(std::vector<uint8_t> &frame_data, GstAppSrc *appsrc) {
    GstBuffer *buffer = gst_buffer_new_allocate(nullptr, frame_data.size(), nullptr);
    gst_buffer_fill(buffer, 0, frame_data.data(), frame_data.size());
    gst_app_src_push_buffer(appsrc, buffer);
}
 


int main(int argc, char *argv[]) {
    gst_init(&argc, &argv);

    int width = 1920;
    int height = 1080;
    int framerate = 50;
    std::string camera_name = "10.1.3.76";

    GstElement *pipeline = gst_pipeline_new("pipeline");
    GstElement *appsrc = gst_element_factory_make("appsrc", "source");
    GstElement *queue = gst_element_factory_make("queue", "queue");
    GstElement *queue2 = gst_element_factory_make("queue", "queue2");
    GstElement *bayer2rgb = gst_element_factory_make("bayer2rgb", "bayer2rgb");
    GstElement *convert = gst_element_factory_make("videoconvert", "convert");
    GstElement *nvconvert = gst_element_factory_make("nvvideoconvert", "nvconvert");
    GstElement *sink = gst_element_factory_make("nv3dsink", "sink");

    if (!pipeline || !appsrc || !bayer2rgb || !convert || !sink) {
        std::cerr << "GStreamer elements could not be created." << std::endl;
        return -1;
    }

    gst_bin_add_many(GST_BIN(pipeline), appsrc, queue, queue2, bayer2rgb, convert, nvconvert, sink, NULL);
    gst_element_link_many(appsrc, queue2, bayer2rgb, convert, queue, nvconvert, sink, NULL);

    GstCaps *caps = gst_caps_new_simple("video/x-bayer",
                                        "format", G_TYPE_STRING, "rggb",
                                        "width", G_TYPE_INT, width,
                                        "height", G_TYPE_INT, height,
                                        "framerate", GST_TYPE_FRACTION, framerate, 1,
                                        NULL);
    g_object_set(appsrc, "caps", caps, NULL);
    gst_caps_unref(caps);

    g_object_set(appsrc, "max-buffers", 1, NULL);
    g_object_set(appsrc, "max-bytes", 0, NULL);
    g_object_set(appsrc, "max-time", 0, NULL);
    g_object_set(appsrc, "leaky-type", 1, NULL);

    g_object_set(queue, "max-size-buffers", 1, NULL);
    g_object_set(queue, "max-size-bytes", 0, NULL);
    g_object_set(queue, "max-size-time", 0, NULL);
    g_object_set(queue, "leaky", 1, NULL);
    
    g_object_set(queue2, "max-size-buffers", 1, NULL);
    g_object_set(queue2, "max-size-bytes", 0, NULL);
    g_object_set(queue2, "max-size-time", 0, NULL);
    g_object_set(queue2, "leaky", 1, NULL);

    g_object_set(convert, "n-threads", 4, NULL);

    g_object_set(sink, "sync", 0, NULL);

    GstStateChangeReturn ret = gst_element_set_state(pipeline, GST_STATE_PLAYING);
    if (ret == GST_STATE_CHANGE_FAILURE) {
        std::cerr << "Unable to set the pipeline to the playing state." << std::endl;
        return -1;
    }

    ArvCamera *camera = arv_camera_new("10.1.3.76", NULL);
    if (!camera) {
        std::cerr << "No camera found." << std::endl;

        return -1;
    }

    GError *error = nullptr;
    arv_camera_set_region(camera, 0, 0, width, height, &error);
    if (error) {
        std::cerr << "Error setting region: " << error->message << std::endl;
        g_error_free(error);
        return -1;
    }

    arv_camera_set_frame_rate(camera, float(framerate), &error);
    if (error) {
        std::cerr << "Error setting frame rate: " << error->message << std::endl;
        g_error_free(error);
        return -1;
    }

    arv_camera_set_pixel_format(camera, ARV_PIXEL_FORMAT_BAYER_RG_8, &error);
    if (error) {
        std::cerr << "Error setting pixel format: " << error->message << std::endl;
        g_error_free(error);
        return -1;
    }

    ArvStream *stream = arv_camera_create_stream(camera, nullptr, nullptr, &error);
    if (!stream) {
        std::cerr << "Failed to create stream." << std::endl;
        if (error) {
            std::cerr << "Error: " << error->message << std::endl;
            g_error_free(error);
        }
        return -1;
    }

    for (int i = 0; i < 10; i++) {
        arv_stream_push_buffer(stream, arv_buffer_new_allocate(arv_camera_get_payload(camera, &error)));
        if (error) {
            std::cerr << "Error getting payload: " << error->message << std::endl;
            g_error_free(error);
            return -1;
        }
    }

    std::vector<uint8_t> frame_data(width * height);

    std::thread grabber_thread(frame_grabber, camera, stream, std::ref(frame_data), width, height);

    while (running) {
        push_frame_to_gst(frame_data, GST_APP_SRC(appsrc));
        // std::this_thread::sleep_for(std::chrono::milliseconds(10);
    }

    grabber_thread.join();
    gst_element_set_state(pipeline, GST_STATE_NULL);
    gst_object_unref(pipeline);

    std::cout << "Done" << std::endl;
    return 0;
}


*/