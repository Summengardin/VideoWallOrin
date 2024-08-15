import gi
gi.require_version('Gst', '1.0')
gi.require_version('GLib', '2.0')
gi.require_version('Aravis', '0.8')
from gi.repository import Gst, GLib, Aravis


Gst.init(None)


def get_camera_cb(pipeline):
    print("GETTING CAMERA")
    src = pipeline.get_by_name("source")
    camera = src.get_property("camera")
    # exposure = camera.get_property("ExposureTime")



    print(camera.get_float_bounds("ExposureTime"))


    return True



print("\n CREATE")

pipeline = Gst.Pipeline()
source = Gst.ElementFactory.make("aravissrc", "source")
caps = Gst.Caps.from_string("video/x-raw,width=1920,height=1080")
capsfilter = Gst.ElementFactory.make("capsfilter")
capsfilter.set_property("caps", caps)
convert = Gst.ElementFactory.make("videoconvert")
sink = Gst.ElementFactory.make("autovideosink")

print("\n ADD")

pipeline.add(source)
pipeline.add(capsfilter)
pipeline.add(convert)
pipeline.add(sink)

print("\n LINK")

source.link(capsfilter)
capsfilter.link(convert)
convert.link(sink)

print("\n PLAY")

GLib.timeout_add(2000, get_camera_cb, pipeline)


pipeline.set_state(Gst.State.PLAYING)


print("\n LOOP")

try: 
    GLib.MainLoop().run()
except KeyboardInterrupt:
    print("Exiting")
finally:    
    pipeline.set_state(Gst.State.NULL)


