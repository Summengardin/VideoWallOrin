#include <arv.h>
#include <gst/gst.h>
#include <glib.h>
#include <iostream>
#include <csignal>

GMainLoop *main_loop;


static void new_buffer_cb(ArvStream *stream, void *user_data) {
    std::cout << "new buffer" << std::endl;
    GstElement *appsrc = GST_ELEMENT(user_data);
    ArvBuffer *buffer = arv_stream_pop_buffer(stream);

    

    if (buffer != NULL) {
        if (arv_buffer_get_status(buffer) == ARV_BUFFER_STATUS_SUCCESS) {
            size_t buffer_size;
            const void *frame_data = arv_buffer_get_data(buffer, &buffer_size);

            GstBuffer *gst_buffer = gst_buffer_new_allocate(NULL, buffer_size, NULL);
            GstMapInfo map;

            gst_buffer_map(gst_buffer, &map, GST_MAP_WRITE);
            memcpy(map.data, frame_data, buffer_size);
            gst_buffer_unmap(gst_buffer, &map);

            GstFlowReturn ret;
            g_signal_emit_by_name(appsrc, "push-buffer", gst_buffer, &ret);

            if (ret != GST_FLOW_OK) {
                std::cerr << "Error pushing buffer to appsrc" << std::endl;
            }

            gst_buffer_unref(gst_buffer);
        }
        arv_stream_push_buffer(stream, buffer);
    }
}

static void handle_signal(int sig) {
    if (main_loop != nullptr) {
        g_main_loop_quit(main_loop);
    }
}




int main(int argc, char **argv) {
    int width = 1920;
    int height = 1080;
    int framerate = 30;
    const char *camera_name = "10.1.3.76";

    gst_init(&argc, &argv);
    arv_update_device_list();
    
    std::cout << "Found " << arv_get_n_devices() << " cameras" << std::endl; 


    if (!camera_name) {
        std::cerr << "No camera found" << std::endl;
        return -1;
    }

    ArvCamera *camera = arv_camera_new(camera_name, NULL);
    if (!camera) {
        std::cerr << "Error initializing camera" << std::endl;
        return -1;
    }

    GError *error = NULL;
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
    
    g_clear_error(&error);
    

    ArvStream *stream = arv_camera_create_stream(camera, NULL, NULL, NULL);
    if (!stream) {
        std::cerr << "Error creating stream" << std::endl;
        return -1;
    }

    for (int i = 0; i < 10; i++) {
        arv_stream_push_buffer(stream, arv_buffer_new_allocate(arv_camera_get_payload(camera, &error)));
    }



    arv_camera_start_acquisition(camera, NULL);

    GstElement *pipeline = gst_pipeline_new("pipeline");
    GstElement *appsrc = gst_element_factory_make("appsrc", "source");
    GstElement *videoconvert = gst_element_factory_make("videoconvert", "convert");
    GstElement *autovideosink = gst_element_factory_make("autovideosink", "sink");

    if (!pipeline || !appsrc || !videoconvert || !autovideosink) {
        std::cerr << "Error creating GStreamer elements" << std::endl;
        return -1;
    }

    gst_bin_add_many(GST_BIN(pipeline), appsrc, videoconvert, autovideosink, NULL);
    gst_element_link_many(appsrc, videoconvert, autovideosink, NULL);

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

    g_signal_connect(stream, "new-buffer", G_CALLBACK(new_buffer_cb), appsrc);

    GstStateChangeReturn ret = gst_element_set_state(pipeline, GST_STATE_PLAYING);
    if (ret == GST_STATE_CHANGE_FAILURE) {
        std::cerr << "Unable to set the pipeline to the playing state." << std::endl;
        return -1;
    }  
    else {
        std::cout << "Pipeline started" << std::endl;
    }


    std::signal(SIGINT, handle_signal);

    main_loop = g_main_loop_new(NULL, FALSE);
    g_main_loop_run(main_loop);

    gst_element_set_state(pipeline, GST_STATE_NULL);
    gst_object_unref(GST_OBJECT(pipeline));

    arv_camera_stop_acquisition(camera, NULL);
    g_object_unref(camera);
    std::cout << "Done" << std::endl;
    return 0;
}
