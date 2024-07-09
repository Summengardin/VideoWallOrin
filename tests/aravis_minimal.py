import gi
gi.require_version("Aravis", "0.8") # or whatever version number you have installed
from gi.repository import Aravis

# other imports
import cv2
import ctypes
import numpy as np

#continue code from above
Aravis.update_device_list ()
camera = Aravis.Camera.new(None)
camera.set_pixel_format_from_string("BayerRG8")
stream = camera.create_stream (None, None)

payload = camera.get_payload ()

for i in range(0,1):
    stream.push_buffer (Aravis.Buffer.new_allocate (payload))

def convert(buf):
    if not buf:
        return None
    
    INTP = ctypes.POINTER(ctypes.c_uint8)

    addr = buf.get_data()
    ptr = ctypes.cast(addr, INTP)
    im = np.ctypeslib.as_array(ptr, (buf.get_image_height(), buf.get_image_width(), 3))
    im = im.copy()
    return im

def convert_bayer(buf):
    if not buf:
        return None

    INTP = ctypes.POINTER(ctypes.c_uint8)
    addr = buf.get_data()
    ptr = ctypes.cast(addr, INTP)
    height = buf.get_image_height()
    width = buf.get_image_width()
    im = np.ctypeslib.as_array(ptr, (height, width))
    im = im.copy()  # Make a copy to ensure the buffer can be reused

    # Convert the BayerRG8 image to RGB using OpenCV
    try:
        im_rgb = cv2.cvtColor(im, cv2.COLOR_BayerRG2BGR)
    except cv2.error:
        print("Error converting image")
        return None 

    return im_rgb



print ("Start acquisition")
camera.start_acquisition()

while True:
    buffer = stream.try_pop_buffer()
    if buffer:
        frame = convert_bayer(buffer)
        stream.push_buffer(buffer) #push buffer back into stream

        if frame is not None:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            cv2.imshow("frame", frame)
            ch = cv2.waitKey(1) & 0xFF
            if ch == 27 or ch == ord('q'):
                break
            elif ch == ord('s'):
                cv2.imwrite("imagename.png",frame)

camera.stop_acquisition()
