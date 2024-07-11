import gi
gi.require_version('Aravis', '0.8')
from gi.repository import Aravis

import ipaddress
import socket


GEV_PRIMARY_APPLICATION_PORT_REGISTER = 0x0A04
GEV_PRIMARY_APPLICATION_IP_ADDRESS_REGISTER = 0x0A14
GEV_HEARTBEAT_TIMEOUT_REGISTER = 0x0938
GEV_STREAM_CHANNEL_PORT_0 = 0x0D00
# GEV_STREAM_CHANNEL_PORT_0 = 0x0D1C

def fix_port(port):
    # Many firmware versions return a wrong value for the port information
    # The value might require additional conversions
    # Check if valid and fix otherwise
    if port > 65535:
        port = socket.ntohs(socket.ntohl(port))
    return port


def close_camera_connection(camera):
    try:
        # Stop acquisition if it's running
        camera.stop_acquisition()
        
        # Close the control channel
        control_channel = camera.get_device()
        if control_channel:
            control_channel.close()

        # Close the stream channel
        stream = camera.get_stream()
        if stream:
            stream.stop()
            stream.disconnect()

        print("Camera connection closed successfully.")
    except Exception as e:
        print(f"Error closing camera connection: {e}")

def main():
    try:
        # Initialize Aravis
        # Aravis.enable_interface("Fake")
        try:
            Aravis.update_device_list()
        except Exception as e: 
            print(f"Error when updating device list: {e}")
                
        print(f"There are {Aravis.get_n_interfaces()} interfaces")
        for i in range(Aravis.get_n_interfaces()):
            print(f"Interface {i}: {Aravis.get_interface_id(i)}")       
        print()
        # Discover cameras
        Aravis.update_device_list()
        n_devices = Aravis.get_n_devices()

        print(f"Found {n_devices} cameras:")

        if n_devices > 0:

            cameras = []
            streams = []
            for i in range(n_devices):
                camera = Aravis.Camera.new(Aravis.get_device_address(i))
                cameras.append(camera)
                device = camera.get_device()

                print(f"Camera {i}: {Aravis.get_device_address(i)}")

                try:
                    stream = camera.create_stream(None, None)
                    streams.append(stream)
                    camera.start_acquisition()
                except Exception as e:
                    print(f"Could not start stream:\n{e}")

                address = device.read_register(GEV_PRIMARY_APPLICATION_IP_ADDRESS_REGISTER)
                port = device.read_register(GEV_PRIMARY_APPLICATION_PORT_REGISTER)
                heartbeat = device.read_register(GEV_HEARTBEAT_TIMEOUT_REGISTER)
                stream_port = device.read_register(GEV_STREAM_CHANNEL_PORT_0)

                port = fix_port(port)
                stream_port = fix_port(stream_port)

                print(f"Camera is controlled by: {ipaddress.ip_address(address)}")
                print(f"Control port: {port}")
                print(f"Stream port: {stream_port}")
                print(f"Camera heartbeat timeout: {heartbeat}")
                print()


            print()
            for camera in cameras:
                print(f"id: {id(camera)}")
            print()
                
            # Example: Start acquisition
            # camera.start_acquisition()

            # Close the camera connection
            import time
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass

            for i in range(n_devices):
                camera = cameras[i]
                stream = streams[i]
                camera.stop_acquisition()
                device = camera.get_device()

                cameras[i] = None
                streams[i] = None

                address = device.read_register(GEV_PRIMARY_APPLICATION_IP_ADDRESS_REGISTER)
                port = device.read_register(GEV_PRIMARY_APPLICATION_PORT_REGISTER)
                heartbeat = device.read_register(GEV_HEARTBEAT_TIMEOUT_REGISTER)
                stream_port = device.read_register(GEV_STREAM_CHANNEL_PORT_0)

                port = fix_port(port)
                stream_port = fix_port(stream_port)

                print(f"Camera is controlled by: {ipaddress.ip_address(address)}")
                print(f"Control port: {port}")
                print(f"Stream port: {stream_port}")
                print(f"Camera heartbeat timeout: {heartbeat}")
                print()
                for camera in cameras:
                    print(f"id: {id(camera)}")
                print()

                try: 
                    del camera
                    del stream
                    del device
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    pass

        Aravis.update_device_list()
        n_devices = Aravis.get_n_devices()

        print(f"Found {n_devices} cameras:")

        if n_devices > 0:

            cameras = []
            streams = []
            for i in range(n_devices):
                camera = Aravis.Camera.new(Aravis.get_device_address(i))
                cameras.append(camera)
                device = camera.get_device()

                print(f"Camera {i}: {Aravis.get_device_address(i)}")

                try:
                    stream = camera.create_stream(None, None)
                    streams.append(stream)
                    camera.start_acquisition()
                except Exception as e:
                    print(f"Could not start stream:\n{e}")

                address = device.read_register(GEV_PRIMARY_APPLICATION_IP_ADDRESS_REGISTER)
                port = device.read_register(GEV_PRIMARY_APPLICATION_PORT_REGISTER)
                heartbeat = device.read_register(GEV_HEARTBEAT_TIMEOUT_REGISTER)
                stream_port = device.read_register(GEV_STREAM_CHANNEL_PORT_0)

                port = fix_port(port)
                stream_port = fix_port(stream_port)

                print(f"Camera is controlled by: {ipaddress.ip_address(address)}")
                print(f"Control port: {port}")
                print(f"Stream port: {stream_port}")
                print(f"Camera heartbeat timeout: {heartbeat}")
                print()


            print()
            for camera in cameras:
                print(f"id: {id(camera)}")
            print()
                
            # Example: Start acquisition
            # camera.start_acquisition()

            # Close the camera connection
            import time
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass

            for i in range(n_devices):
                camera = cameras[i]
                stream = streams[i]
                camera.stop_acquisition()
                device = camera.get_device()

                cameras[i] = None
                streams[i] = None

                address = device.read_register(GEV_PRIMARY_APPLICATION_IP_ADDRESS_REGISTER)
                port = device.read_register(GEV_PRIMARY_APPLICATION_PORT_REGISTER)
                heartbeat = device.read_register(GEV_HEARTBEAT_TIMEOUT_REGISTER)
                stream_port = device.read_register(GEV_STREAM_CHANNEL_PORT_0)

                port = fix_port(port)
                stream_port = fix_port(stream_port)

                print(f"Camera is controlled by: {ipaddress.ip_address(address)}")
                print(f"Control port: {port}")
                print(f"Stream port: {stream_port}")
                print(f"Camera heartbeat timeout: {heartbeat}")
                print()
                for camera in cameras:
                    print(f"id: {id(camera)}")
                print()

                try: 
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    pass
                       





        else:
            print("No camera found.")
    except Exception as e:
        print(f"Error in main function: {e}")

if __name__ == "__main__":
    main()
