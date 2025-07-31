import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

import logging
logger = logging.getLogger(__name__)

if not Gst.is_initialized():
    Gst.init(None)


# def create_source_bin(index: int, camera) -> Gst.Bin:
#     uri = camera.uri
#     if uri is None:
#         logger.error("URI is None")
#         return None

#     logger.debug(f"Creating nvurisrcbin for {uri}")

#     bin_name = f"src{index}-bin"
#     bin = Gst.Bin.new(bin_name)
#     if not bin:
#         logger.error("Unable to create bin")
#         return None

#     nvurisrcbin = Gst.ElementFactory.make("nvurisrcbin", f"src{index}-nvurisrcbin")
#     if not nvurisrcbin:
#         logger.error("Unable to create nvurisrcbin")
#         return None

#     nvurisrcbin.set_property("uri", uri)
#     nvurisrcbin.set_property("latency", 0)
#     nvurisrcbin.set_property("drop-frame-interval", 0)
#     nvurisrcbin.set_property("num-extra-surfaces", 0)

#     capsfilter = Gst.ElementFactory.make("capsfilter", f"src{index}-capsfilter")
#     if not capsfilter:
#         logger.error("Unable to create capsfilter")
#         return None

#     caps = Gst.Caps.from_string("video/x-raw(memory:NVMM), format=NV12")
#     capsfilter.set_property("caps", caps)

#     bin.add(nvurisrcbin)
#     bin.add(capsfilter)

#     nvurisrcbin.connect("pad-added", nvurisrcbin_pad_added, (bin, capsfilter))

#     # PRE-CREATE ghost pad with no target
#     ghost_pad = Gst.GhostPad.new_no_target("src", Gst.PadDirection.SRC)
#     bin.add_pad(ghost_pad)
#     logger.debug("Empty ghost pad added to bin at creation time.")

#     return bin


# def nvurisrcbin_pad_added(srcbin, pad, data):
#     bin, capsfilter = data

#     caps = pad.get_current_caps()
#     if not caps:
#         logger.warning("Pad has no caps, ignoring.")
#         return

#     structure = caps.get_structure(0)
#     media_type = structure.get_name()

#     if media_type.startswith("video/"):
#         logger.debug(f"Linking video pad {pad.get_name()} to capsfilter sink")

#         sink_pad = capsfilter.get_static_pad("sink")
#         if pad.link(sink_pad) != Gst.PadLinkReturn.OK:
#             logger.error("Failed to link nvurisrcbin pad to capsfilter sink")
#             return

#         src_pad = capsfilter.get_static_pad("src")

#         # NOW SET the target of the previously created ghost pad
#         ghost_pad = bin.get_static_pad("src")
#         if ghost_pad and not ghost_pad.get_target():
#             ghost_pad.set_target(src_pad)
#             logger.debug("Ghost pad target set to capsfilter src pad.")



def create_source_bin(index: int, camera) -> Gst.Bin:
    if camera is None or camera.uri is None:
        logger.error("Camera or URI is None")
        uri = "file:///app/VisionController/data/assets/image_placeholder.png"
    else:   
        uri = camera.uri

    logger.debug(f"Creating nvurisrcbin for {uri}")

    bin_name = f"src{index}-bin"
    bin = Gst.Bin.new(bin_name)
    if not bin:
        logger.error("Unable to create bin")
        return None

    nvurisrcbin = Gst.ElementFactory.make("nvurisrcbin", f"src{index}-nvurisrcbin")
    if not nvurisrcbin:
        logger.error("Unable to create nvurisrcbin")
        return None

    nvurisrcbin.set_property("uri", uri)
    nvurisrcbin.set_property("latency", 0)  # Jitterbuffer size in milliseconds
    nvurisrcbin.set_property("low-latency-mode", 1)
    nvurisrcbin.set_property("drop-frame-interval", 0)
    nvurisrcbin.set_property("num-extra-surfaces", 0) 
    nvurisrcbin.set_property("file-loop", 1)  # Loop the file
    nvurisrcbin.set_property("rtsp-reconnect-interval", 0)  # Timeout in seconds to wait before reconnection
    nvurisrcbin.set_property("rtsp-reconnect-attempts", 0)  # Set rtsp reconnect attempt value
    # nvurisrcbin.set_property("udp-buffer-size", 0)  # Default UDP buffer size

    # Add error handling
    def on_error(bus, message, data):
        err, debug = message.parse_error()
        logger.error(f"Error from {message.src.name}: {err.message}")
        logger.debug(f"Debug info: {debug}")
        if "rtsp" in err.message.lower() or "connection" in err.message.lower():
            # Signal that we need to switch to fallback
            nvurisrcbin.set_state(Gst.State.NULL)
            return True
        return False

    # Add state change handling
    def on_state_changed(bus, message, data):
        old_state, new_state, pending_state = message.parse_state_changed()
        if message.src == nvurisrcbin:
            logger.debug(f"State changed from {old_state.value_nick} to {new_state.value_nick}")
            if new_state == Gst.State.NULL:
                # Source is disconnected, switch to fallback
                logger.info(f"RTSP source {uri} disconnected, switching to fallback")
                return True
        return False

    # Add pad probe for monitoring buffer flow
    def on_buffer_probe(pad, info, data):
        if info.get_buffer():
            # Reset error count on successful buffer
            return Gst.PadProbeReturn.OK
        return Gst.PadProbeReturn.DROP

    # Add pad probe to monitor buffer flow
    src_pad = nvurisrcbin.get_static_pad("src")
    if src_pad:
        src_pad.add_probe(Gst.PadProbeType.BUFFER, on_buffer_probe, None)

    nvurisrcbin.connect("pad-added", nvurisrcbin_pad_added, (bin, index))
    nvurisrcbin.connect("child-added", decodebin_child_added, bin)

    queue = Gst.ElementFactory.make("queue", f"src{index}-queue")
    if not queue:
        logger.error("Unable to create queue for uri decode bin \n")

    # queue.set_property("leaky", 1)  # Dropping old buffers
    queue.set_property("leaky", 1)  # Dropping old buffers
    queue.set_property("max-size-buffers", 1)
    queue.set_property("max-size-bytes", 0)
    queue.set_property("max-size-time", 0)
    queue.set_property("silent", 1)

    capsfilter = Gst.ElementFactory.make("capsfilter", f"src{index}-capsfilter")
    if not capsfilter:
        logger.error(" Unable to create capsfilter \n")
    caps = Gst.Caps.from_string("video/x-raw(memory:NVMM), format=NV12, width=1920, height=1080")
    capsfilter.set_property("caps", caps)


    bin.add(nvurisrcbin)
    bin.add(capsfilter)
    bin.add(queue)
    
    nvurisrcbin.link(capsfilter)
    capsfilter.link(queue)

    # PRE-CREATE ghost pad with no target
    src_pad = queue.get_static_pad("src")
    bin.add_pad(Gst.GhostPad.new("src", src_pad))

    # Note: The bus connection will be handled by the pipeline manager
    # after this bin is added to the pipeline

    return bin


def decodebin_child_added(child_proxy, Object, name, data):
    element_type = Object.get_factory().get_name()
    logger.debug(f"Child added: {name} ({element_type})")
    if element_type == "decodebin":
        Object.connect("child-added", decodebin_child_added, data)

    if element_type == "nvv4l2decoder":
        Object.set_property("low-latency-mode", 1)
        Object.set_property("drop-frame-interval", 0)
        Object.set_property("num-extra-surfaces", 0)

    if element_type == "queue":
        if name != "dec_queue":
            Object.set_property("max-size-buffers", 1)
            Object.set_property("max-size-bytes", 0)
            Object.set_property("max-size-time", 0)
            Object.set_property("leaky", 1)
            Object.set_property("silent", 1)
        else: 
            Object.set_property("max-size-buffers", 5)
            Object.set_property("max-size-bytes", 0)
            Object.set_property("max-size-time", 0)
            # Object.set_property("leaky", 1)
            Object.set_property("silent", 1)


def nvurisrcbin_pad_added(srcbin, pad, data):
    # caps = pad.get_current_caps()
    # structure = caps.get_structure(0)
    # media_type = structure.get_name()

    # if media_type.startswith("video/"):
    source_bin, index = data
    logger.debug(f"Linking video pad {pad.get_name()} to capsfilter sink")

    queue = source_bin.get_by_name(f"src{index}-capsfilter")
    q_pad = queue.get_static_pad("sink")
    if not q_pad:
        logger.error("Unable to get queue sink pad\n")
        return
    if pad.link(q_pad) != Gst.PadLinkReturn.OK:
        logger.error("Failed to link nvurisrcbin pad to queue sink")
        return
    logger.debug(f"Pad {pad.get_name()} linked to queue sink pad.")
