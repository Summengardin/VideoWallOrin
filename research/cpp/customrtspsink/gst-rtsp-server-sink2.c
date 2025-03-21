#include <gst/gst.h>
#include <gst/base/gstbasesink.h>
#include <gst/rtsp-server/rtsp-server.h>
#include <gst/app/gstappsrc.h>

#define GST_TYPE_RTSP_SERVER_SINK (gst_rtsp_server_sink_get_type())
G_DECLARE_FINAL_TYPE(GstRTSPServerSink, gst_rtsp_server_sink, GST, RTSP_SERVER_SINK, GstBaseSink)

/* Forward declaration of media_configure */
static void media_configure(GstRTSPMediaFactory *factory, GstRTSPMedia *media, gpointer user_data);

struct _GstRTSPServerSink {
    GstBaseSink parent;
    
    /* Properties */
    gchar *host;
    gint port;
    gchar *path;
    
    /* RTSP Server objects */
    GstRTSPServer *server;
    GMainLoop *loop;
    GThread *server_thread;
    GstElement *pipeline;
    GstElement *appsrc;
};

enum {
    PROP_0,
    PROP_HOST,
    PROP_PORT,
    PROP_PATH,
    N_PROPERTIES
};

#define DEFAULT_HOST "0.0.0.0"
#define DEFAULT_PORT 8554
#define DEFAULT_PATH "/stream"
#define PACKAGE "rtspserversink"
#define VERSION "1.0"

/* GType Registration */
G_DEFINE_TYPE(GstRTSPServerSink, gst_rtsp_server_sink, GST_TYPE_BASE_SINK);

/* Server thread function */
static gpointer server_thread_func(gpointer data) {
    GstRTSPServerSink *sink = GST_RTSP_SERVER_SINK(data);
    sink->loop = g_main_loop_new(NULL, FALSE);
    
    gst_rtsp_server_attach(sink->server, NULL);
    g_main_loop_run(sink->loop);
    
    return NULL;
}

static GstFlowReturn gst_rtsp_server_sink_render(GstBaseSink *base_sink, GstBuffer *buffer) {
    GstRTSPServerSink *sink = GST_RTSP_SERVER_SINK(base_sink);
    
    if (sink->appsrc) {
        GstAppSrc *app_src = GST_APP_SRC(sink->appsrc);
        return gst_app_src_push_buffer(app_src, gst_buffer_ref(buffer));
    }
    
    return GST_FLOW_OK;
}

static gboolean gst_rtsp_server_sink_start(GstBaseSink *base_sink) {
    GstRTSPServerSink *sink = GST_RTSP_SERVER_SINK(base_sink);
    GstRTSPMountPoints *mounts;
    GstRTSPMediaFactory *factory;

    /* Create server */
    sink->server = gst_rtsp_server_new();
    gst_rtsp_server_set_address(sink->server, sink->host);
    gst_rtsp_server_set_service(sink->server, g_strdup_printf("%d", sink->port));

    /* Create mount points and factory */
    mounts = gst_rtsp_server_get_mount_points(sink->server);
    factory = gst_rtsp_media_factory_new();

    /* Set up the pipeline with appsrc */
    gst_rtsp_media_factory_set_launch(factory,
        "( appsrc name=source is-live=true ! queue ! rtph264pay name=pay0 pt=96 )");
    
    gst_rtsp_media_factory_set_shared(factory, TRUE);
    
    /* Connect to media-configure signal */
    g_signal_connect(factory, "media-configure", G_CALLBACK(media_configure), sink);
    
    /* Add the factory to mount points */
    gst_rtsp_mount_points_add_factory(mounts, sink->path, factory);
    g_object_unref(mounts);

    /* Start server thread */
    sink->server_thread = g_thread_new("server-thread", 
                                     (GThreadFunc)server_thread_func, sink);

    return TRUE;
}

static void media_configure(GstRTSPMediaFactory *factory, GstRTSPMedia *media, gpointer user_data) {
    GstRTSPServerSink *sink = GST_RTSP_SERVER_SINK(user_data);
    GstElement *element = gst_rtsp_media_get_element(media);
    
    /* Get the appsrc element */
    sink->appsrc = gst_bin_get_by_name(GST_BIN(element), "source");
    
    /* Configure appsrc */
    if (sink->appsrc) {
        g_object_set(G_OBJECT(sink->appsrc),
                    "format", GST_FORMAT_TIME,
                    "do-timestamp", TRUE,
                    NULL);
    }
    
    gst_object_unref(element);
}

static gboolean gst_rtsp_server_sink_stop(GstBaseSink *base_sink) {
    GstRTSPServerSink *sink = GST_RTSP_SERVER_SINK(base_sink);
    
    if (sink->loop) {
        g_main_loop_quit(sink->loop);
        g_main_loop_unref(sink->loop);
        sink->loop = NULL;
    }
    
    if (sink->server_thread) {
        g_thread_join(sink->server_thread);
        sink->server_thread = NULL;
    }
    
    if (sink->appsrc) {
        gst_object_unref(sink->appsrc);
        sink->appsrc = NULL;
    }
    
    if (sink->server) {
        g_object_unref(sink->server);
        sink->server = NULL;
    }
    
    return TRUE;
}

/* Need to implement property handlers */
static void gst_rtsp_server_sink_set_property(GObject *object, guint prop_id,
    const GValue *value, GParamSpec *pspec)
{
    GstRTSPServerSink *sink = GST_RTSP_SERVER_SINK(object);

    switch (prop_id) {
        case PROP_HOST:
            g_free(sink->host);
            sink->host = g_value_dup_string(value);
            break;
        case PROP_PORT:
            sink->port = g_value_get_int(value);
            break;
        case PROP_PATH:
            g_free(sink->path);
            sink->path = g_value_dup_string(value);
            break;
        default:
            G_OBJECT_WARN_INVALID_PROPERTY_ID(object, prop_id, pspec);
            break;
    }
}

static void gst_rtsp_server_sink_get_property(GObject *object, guint prop_id,
    GValue *value, GParamSpec *pspec)
{
    GstRTSPServerSink *sink = GST_RTSP_SERVER_SINK(object);

    switch (prop_id) {
        case PROP_HOST:
            g_value_set_string(value, sink->host);
            break;
        case PROP_PORT:
            g_value_set_int(value, sink->port);
            break;
        case PROP_PATH:
            g_value_set_string(value, sink->path);
            break;
        default:
            G_OBJECT_WARN_INVALID_PROPERTY_ID(object, prop_id, pspec);
            break;
    }
}

/* Add finalize function */
static void gst_rtsp_server_sink_finalize(GObject *object)
{
    GstRTSPServerSink *sink = GST_RTSP_SERVER_SINK(object);

    g_free(sink->host);
    g_free(sink->path);

    G_OBJECT_CLASS(gst_rtsp_server_sink_parent_class)->finalize(object);
}

static void gst_rtsp_server_sink_class_init(GstRTSPServerSinkClass *klass) {
    GObjectClass *gobject_class = G_OBJECT_CLASS(klass);
    GstBaseSinkClass *base_sink_class = GST_BASE_SINK_CLASS(klass);
    GstElementClass *element_class = GST_ELEMENT_CLASS(klass);

    /* Set virtual functions */
    base_sink_class->render = gst_rtsp_server_sink_render;
    base_sink_class->start = gst_rtsp_server_sink_start;
    base_sink_class->stop = gst_rtsp_server_sink_stop;

    /* Set property handlers */
    gobject_class->set_property = gst_rtsp_server_sink_set_property;
    gobject_class->get_property = gst_rtsp_server_sink_get_property;
    gobject_class->finalize = gst_rtsp_server_sink_finalize;  // Add finalize handler

    /* Add pad templates */
    GstCaps *caps = gst_caps_new_simple("application/x-rtp",
                                      "encoding-name", G_TYPE_STRING, "H264",
                                      NULL);
    GstPadTemplate *templ = gst_pad_template_new("sink", GST_PAD_SINK,
                                               GST_PAD_ALWAYS, caps);
    gst_element_class_add_pad_template(element_class, templ);
    gst_caps_unref(caps);

    /* Set metadata */
    gst_element_class_set_static_metadata(element_class,
        "RTSP Server Sink",
        "Sink/Network",
        "Streams data over RTSP protocol",
        "Your Name <your.email@example.com>");

    /* Install properties */
    g_object_class_install_property(gobject_class, PROP_HOST,
        g_param_spec_string("host", "Host",
            "The host/IP to listen on", DEFAULT_HOST,
            G_PARAM_READWRITE | G_PARAM_STATIC_STRINGS));

    g_object_class_install_property(gobject_class, PROP_PORT,
        g_param_spec_int("port", "Port",
            "The port to listen on", 0, 65535, DEFAULT_PORT,
            G_PARAM_READWRITE | G_PARAM_STATIC_STRINGS));

    g_object_class_install_property(gobject_class, PROP_PATH,
        g_param_spec_string("path", "Path",
            "The RTSP stream path", DEFAULT_PATH,
            G_PARAM_READWRITE | G_PARAM_STATIC_STRINGS));
}

static void gst_rtsp_server_sink_init(GstRTSPServerSink *sink) {
    sink->host = g_strdup(DEFAULT_HOST);
    sink->port = DEFAULT_PORT;
    sink->path = g_strdup(DEFAULT_PATH);
}



/* Plugin registration */
static gboolean plugin_init(GstPlugin *plugin) {
    return gst_element_register(plugin, "rtspserversink",
                              GST_RANK_NONE, GST_TYPE_RTSP_SERVER_SINK);
}

GST_PLUGIN_DEFINE(
    GST_VERSION_MAJOR,
    GST_VERSION_MINOR,
    rtspserversink,
    "RTSP Server Sink Element",
    plugin_init,
    VERSION,
    "LGPL",
    PACKAGE,
    "https://example.com"
)