import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

import logging
logger = logging.getLogger(__name__)

if not Gst.is_initialized():
    Gst.init(None)


def decodebin_child_added(child_proxy, Object, name, user_data):
    logger.debug(f"Decodebin child added: {name}, Object: {Object}")
    if "decodebin" in name: 
        Object.connect("child-added", decodebin_child_added, user_data)
    if "nvv4l2decoder" in name:
        # Object.set_property("enable-max-performance", True)
        Object.set_property("drop-frame-interval", 0)
        Object.set_property("num-extra-surfaces", 0)



def cb_newpad(decodebin, pad, data):
    logger.debug("In cb_newpad\n")
    caps = pad.get_current_caps()
    gststruct = caps.get_structure(0)
    gstname = gststruct.get_name()

    if "video" in gstname:
        source_bin, index = data
        nvconvert = source_bin.get_by_name(f"src{index}-nvvideoconvert")

        q_pad = nvconvert.get_static_pad("sink")
        if not q_pad:
            logger.error("Unable to get nvconvert sink pad\n")

        if not pad.link(q_pad) == Gst.PadLinkReturn.OK:
            logger.error("Unable to link decoder src pad to nvconvert sink pad")




def create_source_bin(index: int, camera) -> Gst.Bin:
    uri = camera.uri
    if uri is None:
        logger.error("URI is None")
        return None

    logger.debug(f"Creating uridecodebin for {uri}")
    

    bin_name = f"src{index}-bin"

    bin = Gst.Bin.new(bin_name)
    if not bin:
        logger.error(" Unable to create bin \n")

    uridecodebin = Gst.ElementFactory.make("uridecodebin", f"src{index}")
    if not uridecodebin:
        logger.error(" Unable to create uri decode bin \n")


    uridecodebin.set_property("uri", uri)
    uridecodebin.connect("pad-added", cb_newpad, (bin, index))
    uridecodebin.connect("child-added", decodebin_child_added, bin)

    nvvideoconvert = Gst.ElementFactory.make("nvvideoconvert", f"src{index}-nvvideoconvert")
    if not nvvideoconvert:
        logger.error(" Unable to create nvvideoconvert \n")
    
    capsfilter = Gst.ElementFactory.make("capsfilter", f"src{index}-capsfilter")
    if not capsfilter:
        logger.error(" Unable to create capsfilter \n")
    caps = Gst.Caps.from_string("video/x-raw(memory:NVMM), format=NV12")
    capsfilter.set_property("caps", caps)

    queue = Gst.ElementFactory.make("queue", f"src{index}-queue")
    if not queue:
        logger.error("Unable to create queue for uri decode bin \n")

    queue.set_property("leaky", 1)  # Dropping old buffers
    queue.set_property("max-size-buffers", 1)
    queue.set_property("max-size-bytes", 0)
    queue.set_property("max-size-time", 0)

    bin.add(uridecodebin)
    bin.add(nvvideoconvert)
    bin.add(capsfilter)
    bin.add(queue)

    uridecodebin.link(nvvideoconvert)
    nvvideoconvert.link(capsfilter)
    capsfilter.link(queue)
    

    src_pad = queue.get_static_pad("src")
    bin.add_pad(Gst.GhostPad.new("src", src_pad))

    # g_source_enabled[index] = True

    return bin