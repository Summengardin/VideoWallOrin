import time
from onvif import ONVIFCamera

import threading

hold = threading.Event()

WSDL = '/home/seaonics/.local/lib/python3.10/site-packages/wsdl'

cam = ONVIFCamera('10.1.3.78', 80, 'admin', 'admin', wsdl_dir=WSDL)

media = cam.create_media_service()
# Get target profile
media_profile = media.GetProfiles()[0]
# Use the first profile and Profiles have at least one
token = media_profile.token
# PTZ controls  -------------------------------------------------------------
ptz = cam.create_ptz_service()
# Get available PTZ services
request = ptz.create_type('GetServiceCapabilities')
Service_Capabilities = ptz.GetServiceCapabilities(request)
# Get PTZ status
status = ptz.GetStatus({'ProfileToken': token})

# Get PTZ configuration options for getting option ranges
request = ptz.create_type('GetConfigurationOptions')
request.ConfigurationToken = media_profile.PTZConfiguration.token
ptz_configuration_options = ptz.GetConfigurationOptions(request)


req_abs_move = ptz.create_type('AbsoluteMove')
req_abs_move.ProfileToken = token

if req_abs_move.Position is None:
    req_abs_move.Position = ptz.GetStatus(
        {'ProfileToken': token}).Position

req_con_move = ptz.create_type('ContinuousMove')
req_con_move.ProfileToken = token

if req_con_move.Velocity is None:
    req_con_move.Velocity = ptz.GetStatus({'ProfileToken': token}).Position
    req_con_move.Velocity.PanTilt.space = ptz_configuration_options.Spaces.ContinuousPanTiltVelocitySpace[0].URI
    req_con_move.Velocity.Zoom.space = ptz_configuration_options.Spaces.ContinuousZoomVelocitySpace[0].URI


def absolute_zoom(zoom):
    req_abs_move.Position.Zoom.x = zoom
    ptz.AbsoluteMove(req_abs_move)

def continous_zoom(speed):
    print("Zomming continously with speed: ", speed)
    req_con_move.Velocity.Zoom.x = speed
    ptz.ContinuousMove(req_con_move)


continous_zoom(1)

hold.wait(10)

continous_zoom(-1)

hold.wait(10)



# -- ABSOLUTE ZOOM --
# for i in range(10):
#     absolute_zoom(i)
#     print(ptz.GetStatus({'ProfileToken': token}).Position.Zoom.x)
#     time.sleep(1)






