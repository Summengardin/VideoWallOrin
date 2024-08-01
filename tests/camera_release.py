import time
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib



def main():
    Gst.init(None)

    pipeline = Gst.Pipeline.new("aravis_pipeline")
    bin = Gst.Bin.new("aravis_bin")
    source = Gst.ElementFactory.make("aravissrc", "source")
    if not source:
        print("Failed to create the source element.")
        return False

    cfg_OffsetY = (1200 - 1184) / 2
    cam1 = "10.1.3.75"

    source.set_property("camera-name", cam1)
    source.set_property("num-arv-buffers", 64)
    source.set_property("packet-resend", False)
    source.set_property("packet-size", 9000)
    source.set_property("auto-packet-size", False)
    
    time.sleep(5)

    videoconvert = Gst.ElementFactory.make("videoconvert", "convertor")
    sink = Gst.ElementFactory.make("autovideosink", "fake_sink")


    if not pipeline or not bin or not source or not videoconvert or not sink:
        print("Not all elements could be created.")
        return -1

    bin.add(source)
    pipeline.add(videoconvert)
    pipeline.add(sink)
    pipeline.add(bin)


    src_pad = source.get_static_pad("src")
    bin.add_pad(Gst.GhostPad.new("src", src_pad))

    if not bin.link(videoconvert):
        print("Bin could not be linked to the convertor.")
        pipeline.set_state(Gst.State.NULL)
        return -1

    if not videoconvert.link(sink):
        print("Videoconvert could not be linked to sink.")
        pipeline.set_state(Gst.State.NULL)
        return -1

    main_loop = GLib.MainLoop()
    print("Starting the pipeline.")
    pipeline.set_state(Gst.State.PLAYING)

    time.sleep(10)

    print("Pausing the pipeline.")
    # Stop camera

    pipeline.set_state(Gst.State.PAUSED)
    
    time.sleep(5)
    # source.set_state(Gst.State.NULL)
    print("Removing the bin.")
    
    bin.unlink(videoconvert)


    bin.set_state(Gst.State.NULL)

    time.sleep(5)
    pipeline.remove(bin)
    
    print("Camera source removed.")
    bin = None

    time.sleep(4)

    print("Starting the pipeline again.")

    bin = Gst.Bin.new("aravis_bin")
    source = Gst.ElementFactory.make("aravissrc", "source")
    if not source:
        print("Failed to create the source element.")
        return False

    cfg_OffsetY = (1200 - 1184) / 2
    cam1 = "10.1.3.75"

    source.set_property("camera-name", cam1)
    source.set_property("num-arv-buffers", 64)
    source.set_property("packet-resend", False)
    source.set_property("packet-size", 9000)
    source.set_property("auto-packet-size", False)
    
    if not bin or not source:
        print("Not all elements could be created.")
        return -1

    bin.add(source)
    pipeline.add(bin)


    src_pad = source.get_static_pad("src")
    bin.add_pad(Gst.GhostPad.new("src", src_pad))

    if not bin.link(videoconvert):
        print("Bin could not be linked to the convertor.")
        pipeline.set_state(Gst.State.NULL)
        return -1


    time.sleep(5)

    print("Starting the pipeline.")
    state_return = pipeline.set_state(Gst.State.PLAYING)
    if state_return == Gst.StateChangeReturn.FAILURE:
        print("Unable to set the pipeline to the playing state.")
        pipeline.set_state(Gst.State.NULL)
        return -1
    
    print("Started")
    main_loop.run()

    # Free resources
    main_loop.quit()
    pipeline.set_state(Gst.State.NULL)
    # pipeline.unref()

if __name__ == "__main__":
    main()
