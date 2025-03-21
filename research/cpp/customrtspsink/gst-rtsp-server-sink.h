#ifndef __GST_RTSP_SERVER_SINK_H__
#define __GST_RTSP_SERVER_SINK_H__

#include <gst/gst.h>
#include <gst/base/gstbasesink.h>
#include <gio/gio.h>

G_BEGIN_DECLS

/* Type definitions */
#define GST_TYPE_RTSP_SERVER_SINK (gst_rtsp_server_sink_get_type())
G_DECLARE_FINAL_TYPE(GstRTSPServerSink, gst_rtsp_server_sink, GST, RTSP_SERVER_SINK, GstBaseSink)


/* Default values */
#define DEFAULT_HOST "0.0.0.0"
#define DEFAULT_PORT 8554
#define DEFAULT_PATH "/stream"

/* Client structure */
typedef struct _RTSPClient {
    GSocket *socket;
    GInputStream *istream;
    GOutputStream *ostream;
    gchar *session_id;
    struct _RTSPClient *next;
} RTSPClient;

/* Sink structure */
struct _GstRTSPServerSink {
    GstBaseSink parent;
    
    /* Properties */
    gchar *host;
    gint port;
    gchar *path;
    
    /* Private */
    GSocket *server_socket;
    GSource *server_source;
    RTSPClient *clients;
    GMutex clients_lock;
    
    /* Stream info */
    GstCaps *caps;
    gchar *sdp;
};

/* Property enumeration */
enum {
    PROP_0,
    PROP_HOST,
    PROP_PORT,
    PROP_PATH,
    N_PROPERTIES
};

/* Function Prototypes */

/* GObject virtual functions */
static void gst_rtsp_server_sink_set_property(GObject *object, guint prop_id,
    const GValue *value, GParamSpec *pspec);
static void gst_rtsp_server_sink_get_property(GObject *object, guint prop_id,
    GValue *value, GParamSpec *pspec);
static void gst_rtsp_server_sink_finalize(GObject *object);
static void gst_rtsp_server_sink_class_init(GstRTSPServerSinkClass *klass);
static void gst_rtsp_server_sink_init(GstRTSPServerSink *sink);

/* GstBaseSink virtual functions */
static gboolean gst_rtsp_server_sink_start(GstBaseSink *base_sink);
static gboolean gst_rtsp_server_sink_stop(GstBaseSink *base_sink);
static GstFlowReturn gst_rtsp_server_sink_render(GstBaseSink *base_sink,
    GstBuffer *buffer);

/* RTSP protocol handling functions */
static void send_rtsp_response(GOutputStream *stream, const gchar *code, 
    const gchar *content_type, const gchar *content);
static void handle_options(RTSPClient *client);
static void handle_describe(GstRTSPServerSink *sink, RTSPClient *client);
static void handle_setup(RTSPClient *client);
static void handle_play(RTSPClient *client);

/* Client handling functions */
static gboolean handle_client_message(GInputStream *stream, RTSPClient *client, 
    GstRTSPServerSink *sink);
static gboolean on_client_connection(GSocket *socket, GIOCondition condition, 
    GstRTSPServerSink *sink);

/* Plugin functions */
static gboolean plugin_init(GstPlugin *plugin);
GST_ELEMENT_REGISTER_DECLARE(rtspserversink);

/* Helper macros */
#define GST_RTSP_SERVER_SINK_LOCK(sink) g_mutex_lock(&sink->clients_lock)
#define GST_RTSP_SERVER_SINK_UNLOCK(sink) g_mutex_unlock(&sink->clients_lock)

/* Buffer sizes */
#define RTSP_BUFFER_SIZE 4096
#define RTP_HEADER_SIZE 4

/* RTSP response codes */
#define RTSP_OK "200 OK"
#define RTSP_BAD_REQUEST "400 Bad Request"
#define RTSP_NOT_FOUND "404 Not Found"
#define RTSP_INTERNAL_ERROR "500 Internal Server Error"

G_END_DECLS

#endif /* __GST_RTSP_SERVER_SINK_H__ */