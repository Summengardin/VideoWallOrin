from zeep import Client
from requests.auth import HTTPDigestAuth

# Replace with your device's details
onvif_wsdl_url = 'http://10.1.3.78:2000/onvif/device_service'
username = 'admin'
password = 'admin'

# Create a zeep client with authentication
client = Client(wsdl=onvif_wsdl_url)
client.transport.session.auth = HTTPDigestAuth(username, password)

# Function to get imaging settings
def get_imaging_settings():
    try:
        imaging_service = client.bind('Imaging', 'ImagingBinding')
        profiles = client.service.GetProfiles()
        for profile in profiles:
            imaging_settings = imaging_service.GetImagingSettings({'VideoSourceToken': profile.VideoSourceConfiguration.SourceToken})
            print(f"Imaging Settings for Profile {profile.token}:")
            print(imaging_settings)
            print("\n")
    except Exception as e:
        print(f"Error getting imaging settings: {e}")

# Function to get service capabilities
def get_service_capabilities():
    try:
        device_service = client.bind('Device', 'DeviceBinding')
        capabilities = device_service.GetServiceCapabilities()
        print("Service Capabilities:")
        print(capabilities)
    except Exception as e:
        print(f"Error getting service capabilities: {e}")

if __name__ == "__main__":
    print("Fetching Imaging Settings...")
    get_imaging_settings()

    print("Fetching Service Capabilities...")
    get_service_capabilities()
