
#include "gst-rtsp-server-sink.h"
#include <string.h>


G_DEFINE_TYPE(GstRTSPServerSink, gst_rtsp_server_sink, GST_TYPE_BASE_SINK);

/* RTSP Response helpers */
static void send_rtsp_response(GOutputStream *stream, const gchar *code, 
                             const gchar *content_type, const gchar *content)
{
    GString *response = g_string_new(NULL);
    g_string_append_printf(response, "RTSP/1.0 %s\r\n", code);
    g_string_append_printf(response, "CSeq: 1\r\n");
    
    if (content && content_type) {
        g_string_append_printf(response, "Content-Type: %s\r\n", content_type);
        g_string_append_printf(response, "Content-Length: %zu\r\n", strlen(content));
    }
    
    g_string_append(response, "\r\n");
    
    if (content)
        g_string_append(response, content);
    
    g_output_stream_write_all(stream, response->str, response->len, NULL, NULL, NULL);
    g_string_free(response, TRUE);
}

/* Handle RTSP requests */
static void handle_options(RTSPClient *client)
{
    send_rtsp_response(client->ostream, "200 OK", NULL,
        "Public: OPTIONS, DESCRIBE, SETUP, PLAY, TEARDOWN\r\n");
}

static void handle_describe(GstRTSPServerSink *sink, RTSPClient *client)
{
    if (!sink->sdp) {
        // Generate a basic SDP description
        GString *sdp = g_string_new(NULL);
        g_string_append(sdp, "v=0\r\n");
        g_string_append_printf(sdp, "o=- %ld 1 IN IP4 %s\r\n", time(NULL), sink->host);
        g_string_append(sdp, "s=Stream\r\n");
        g_string_append_printf(sdp, "c=IN IP4 %s\r\n", sink->host);
        g_string_append(sdp, "t=0 0\r\n");
        g_string_append(sdp, "m=video 0 RTP/AVP 96\r\n");
        g_string_append(sdp, "a=rtpmap:96 H264/90000\r\n");
        g_string_append(sdp, "a=control:trackID=1\r\n");
        
        sink->sdp = g_string_free(sdp, FALSE);
    }
    
    send_rtsp_response(client->ostream, "200 OK", "application/sdp", sink->sdp);
}

static void handle_setup(RTSPClient *client)
{
    if (!client->session_id)
        client->session_id = g_strdup_printf("%p", client);
        
    GString *response = g_string_new(NULL);
    g_string_append_printf(response, "Session: %s\r\n", client->session_id);
    g_string_append(response, "Transport: RTP/AVP/TCP;unicast;interleaved=0-1\r\n");
    
    send_rtsp_response(client->ostream, "200 OK", NULL, response->str);
    g_string_free(response, TRUE);
}

static void handle_play(RTSPClient *client)
{
    GString *response = g_string_new(NULL);
    g_string_append_printf(response, "Session: %s\r\n", client->session_id);
    g_string_append(response, "Range: npt=0.000-\r\n");
    
    send_rtsp_response(client->ostream, "200 OK", NULL, response->str);
    g_string_free(response, TRUE);
}

/* Client handling */
static gboolean handle_client_message(GInputStream *stream, RTSPClient *client, 
                                    GstRTSPServerSink *sink)
{
    gchar buffer[4096];
    gssize bytes_read;
    
    bytes_read = g_input_stream_read(stream, buffer, sizeof(buffer) - 1, NULL, NULL);
    if (bytes_read <= 0)
        return FALSE;
        
    buffer[bytes_read] = '\0';
    
    if (g_str_has_prefix(buffer, "OPTIONS"))
        handle_options(client);
    else if (g_str_has_prefix(buffer, "DESCRIBE"))
        handle_describe(sink, client);
    else if (g_str_has_prefix(buffer, "SETUP"))
        handle_setup(client);
    else if (g_str_has_prefix(buffer, "PLAY"))
        handle_play(client);
        
    return TRUE;
}

static gboolean on_client_connection(GSocket *socket, GIOCondition condition, 
                                   GstRTSPServerSink *sink)
{
    if (condition & G_IO_IN) {
        GError *error = NULL;
        GSocket *client_socket = g_socket_accept(socket, NULL, &error);
        
        if (client_socket) {
            RTSPClient *client = g_new0(RTSPClient, 1);
            client->socket = client_socket;
            client->istream = g_io_stream_get_input_stream(G_IO_STREAM(
                g_socket_connection_factory_create_connection(client_socket)));
            client->ostream = g_io_stream_get_output_stream(G_IO_STREAM(
                g_socket_connection_factory_create_connection(client_socket)));
                
            g_mutex_lock(&sink->clients_lock);
            client->next = sink->clients;
            sink->clients = client;
            g_mutex_unlock(&sink->clients_lock);
            
            // Set up watch for client messages
            GSource *source = g_socket_create_source(client_socket, G_IO_IN, NULL);
            g_source_set_callback(source, (GSourceFunc)handle_client_message, 
                                client, NULL);
            g_source_attach(source, NULL);
        }
    }
    
    return TRUE;
}

/* GStreamer element implementation */
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

static gboolean gst_rtsp_server_sink_start(GstBaseSink *base_sink)
{
    GstRTSPServerSink *sink = GST_RTSP_SERVER_SINK(base_sink);
    GError *error = NULL;

    sink->server_socket = g_socket_new(G_SOCKET_FAMILY_IPV4,
                                     G_SOCKET_TYPE_STREAM,
                                     G_SOCKET_PROTOCOL_TCP,
                                     &error);
    if (!sink->server_socket) {
        GST_ERROR_OBJECT(sink, "Failed to create socket: %s", error->message);
        g_error_free(error);
        return FALSE;
    }

    GInetAddress *addr = g_inet_address_new_from_string(sink->host);
    GSocketAddress *socket_addr = g_inet_socket_address_new(addr, sink->port);
    g_object_unref(addr);

    if (!g_socket_bind(sink->server_socket, socket_addr, TRUE, &error)) {
        GST_ERROR_OBJECT(sink, "Failed to bind: %s", error->message);
        g_error_free(error);
        g_object_unref(socket_addr);
        return FALSE;
    }
    g_object_unref(socket_addr);

    if (!g_socket_listen(sink->server_socket, &error)) {
        GST_ERROR_OBJECT(sink, "Failed to listen: %s", error->message);
        g_error_free(error);
        return FALSE;
    }

    sink->server_source = g_socket_create_source(sink->server_socket, G_IO_IN, NULL);
    g_source_set_callback(sink->server_source, (GSourceFunc)on_client_connection,
                         sink, NULL);
    g_source_attach(sink->server_source, NULL);

    GST_INFO_OBJECT(sink, "RTSP server started on %s:%d", sink->host, sink->port);
    return TRUE;
}

static gboolean gst_rtsp_server_sink_stop(GstBaseSink *base_sink)
{
    GstRTSPServerSink *sink = GST_RTSP_SERVER_SINK(base_sink);

    if (sink->server_source) {
        g_source_destroy(sink->server_source);
        g_source_unref(sink->server_source);
        sink->server_source = NULL;
    }

    if (sink->server_socket) {
        g_socket_close(sink->server_socket, NULL);
        g_object_unref(sink->server_socket);
        sink->server_socket = NULL;
    }

    g_mutex_lock(&sink->clients_lock);
    RTSPClient *client = sink->clients;
    while (client) {
        RTSPClient *next = client->next;
        g_socket_close(client->socket, NULL);
        g_object_unref(client->socket);
        g_free(client->session_id);
        g_free(client);
        client = next;
    }
    sink->clients = NULL;
    g_mutex_unlock(&sink->clients_lock);

    return TRUE;
}

static GstFlowReturn gst_rtsp_server_sink_render(GstBaseSink *base_sink,
                                                GstBuffer *buffer)
{
    GstRTSPServerSink *sink = GST_RTSP_SERVER_SINK(base_sink);
    
    GstMapInfo map;
    if (!gst_buffer_map(buffer, &map, GST_MAP_READ))
        return GST_FLOW_ERROR;

    g_mutex_lock(&sink->clients_lock);
    RTSPClient *client = sink->clients;
    while (client) {
        RTSPClient *next = client->next;
        
        // Send RTP packet with interleaved framing
        guint8 header[4] = {0x24, 0x00, (map.size >> 8) & 0xFF, map.size & 0xFF};
        if (!g_output_stream_write_all(client->ostream, header, 4, NULL, NULL, NULL) ||
            !g_output_stream_write_all(client->ostream, map.data, map.size, NULL, NULL, NULL)) {
            // Remove disconnected client
            if (client == sink->clients)
                sink->clients = next;
            else {
                RTSPClient *prev = sink->clients;
                while (prev->next != client)
                    prev = prev->next;
                prev->next = next;
            }
            g_socket_close(client->socket, NULL);
            g_object_unref(client->socket);
            g_free(client->session_id);
            g_free(client);
        }
        client = next;
    }
    g_mutex_unlock(&sink->clients_lock);

    gst_buffer_unmap(buffer, &map);
    return GST_FLOW_OK;
}

static void gst_rtsp_server_sink_class_init(GstRTSPServerSinkClass *klass)
{
    GObjectClass *gobject_class = G_OBJECT_CLASS(klass);
    GstBaseSinkClass *base_sink_class = GST_BASE_SINK_CLASS(klass);
    GstElementClass *element_class = GST_ELEMENT_CLASS(klass);

    gobject_class->set_property = gst_rtsp_server_sink_set_property;
    gobject_class->get_property = gst_rtsp_server_sink_get_property;
    gobject_class->finalize = gst_rtsp_server_sink_finalize;

    base_sink_class->start = gst_rtsp_server_sink_start;
    base_sink_class->stop = gst_rtsp_server_sink_stop;
    base_sink_class->render = gst_rtsp_server_sink_render;

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

    gst_element_class_set_static_metadata(element_class,
        "RTSP Server Sink",
        "Sink/Network",
        "Streams data over RTSP protocol",
        "Your Name <your.email@example.com>");

    static GstStaticPadTemplate sink_template = 
        GST_STATIC_PAD_TEMPLATE("sink",
            GST_PAD_SINK,
            GST_PAD_ALWAYS,
            GST_STATIC_CAPS("application/x-rtp")
        );

    gst_element_class_add_pad_template(element_class,
        gst_static_pad_template_get(&sink_template));
}

static void gst_rtsp_server_sink_init(GstRTSPServerSink *sink)
{
    sink->host = g_strdup(DEFAULT_HOST);
    sink->port = DEFAULT_PORT;
    sink->path = g_strdup(DEFAULT_PATH);
    g_mutex_init(&sink->clients_lock);
}

static void gst_rtsp_server_sink_finalize(GObject *object)
{
    GstRTSPServerSink *sink = GST_RTSP_SERVER_SINK(object);

    g_free(sink->host);
    g_free(sink->path);
    g_free(sink->sdp);
    g_mutex_clear(&sink->clients_lock);

    G_OBJECT_CLASS(gst_rtsp_server_sink_parent_class)->finalize(object);
}

/* Plugin initialization */
static gboolean plugin_init(GstPlugin *plugin)
{
    return gst_element_register(plugin, "rtspserversink",
        GST_RANK_NONE, GST_TYPE_RTSP_SERVER_SINK);
}

#define PACKAGE "rtspserversink"
#define VERSION "1.0"

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