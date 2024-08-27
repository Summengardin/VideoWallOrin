#include <gst/gst.h>
#include <glib.h>
#include <iostream>

static gboolean get_camera_cb(gpointer data) {
    std::cout << "GETTING CAMERA" << std::endl;
    GstElement *pipeline = GST_ELEMENT(data);
    GstElement *src = gst_bin_get_by_name(GST_BIN(pipeline), "source");
    
    // Get the "camera" property
    GValue camera_val = G_VALUE_INIT;
    g_object_get_property(G_OBJECT(src), "camera", &camera_val);
    gpointer camera = g_value_get_object(&camera_val);

    // List properties of the camera
    if (camera) {
        GParamSpec **props;
        guint n_props;
        props = g_object_class_list_properties(G_OBJECT_GET_CLASS(camera), &n_props);

        for (guint i = 0; i < n_props; i++) {
            std::cout << "Property name: " << props[i]->name << std::endl;
        }
    }

    double min, max;
    arv_camera_get_float_bounds(camera, "ExposureTime", &min, &max, nullptr);

    std::cout << "min: " << min << ", max: " << max << std::endl;

    g_value_unset(&camera_val);
    return TRUE;
}

int main(int argc, char *argv[]) {
    gst_init(&argc, &argv);

    std::cout << "\nCREATE" << std::endl;

    GstElement *pipeline = gst_pipeline_new(nullptr);
    GstElement *source = gst_element_factory_make("aravissrc", "source");
    GstElement *capsfilter = gst_element_factory_make("capsfilter", nullptr);
    GstElement *convert = gst_element_factory_make("videoconvert", nullptr);
    GstElement *sink = gst_element_factory_make("autovideosink", nullptr);

    if (!pipeline || !source || !capsfilter || !convert || !sink) {
        std::cerr << "Not all elements could be created." << std::endl;
        return -1;
    }

    std::cout << "\nADD" << std::endl;

    gst_bin_add_many(GST_BIN(pipeline), source, capsfilter, convert, sink, nullptr);

    std::cout << "\nLINK" << std::endl;

    GstCaps *caps = gst_caps_new_simple("video/x-raw",
                                        "width", G_TYPE_INT, 1920,
                                        "height", G_TYPE_INT, 1080,
                                        nullptr);
    g_object_set(capsfilter, "caps", caps, nullptr);
    gst_caps_unref(caps);

    if (!gst_element_link(source, capsfilter) ||
        !gst_element_link(capsfilter, convert) ||
        !gst_element_link(convert, sink)) {
        std::cerr << "Elements could not be linked." << std::endl;
        gst_object_unref(pipeline);
        return -1;
    }

    std::cout << "\nPLAY" << std::endl;

    g_timeout_add(2000, get_camera_cb, pipeline);
    gst_element_set_state(pipeline, GST_STATE_PLAYING);

    std::cout << "\nLOOP" << std::endl;

    GMainLoop *loop = g_main_loop_new(nullptr, FALSE);
    g_main_loop_run(loop);

    // Cleanup after the main loop exits
    gst_element_set_state(pipeline, GST_STATE_NULL);
    gst_object_unref(pipeline);
    g_main_loop_unref(loop);

    return 0;
}
