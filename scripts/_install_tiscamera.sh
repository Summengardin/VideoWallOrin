#!/bin/bash
# sudo apt install -y git cmake

mkdir tis-install
cd tis-install

# mkdir tiscamera
# cd tiscamera

# wget https://s1-dl.theimagingsource.com/api/2.5/packages/software/sdk/tiscamera/f47b5b18-a6c1-552d-b952-dd912ad94952/tiscamera_1.1.0.4139_amd64_ubuntu_1804.deb
# sudo apt install -y ./tiscamera*.deb


# tiscamera
# git clone https://github.com/TheImagingSource/tiscamera.git
# cd tiscamera
# git checkout v-tiscamera-1.1.0


# ./scripts/dependency-manager install -y
# mkdir build
# cd build

# cmake .. \
#     -DTCAM_ARAVIS_USB_VISION=OFF \
#     -DTCAM_BUILD_ARAVIS=OFF \
#     -DTCAM_BUILD_TOOLS=ON \
#     -DTCAM_BUILD_LIBUSB=OFF \
#     -DTCAM_BUILD_V4L2=OFF \
#     -DTCAM_DOWNLOAD_MESON=OFF \

# make
# make install



# tcam-properties
# echo "Installing tcam-properties"
# cd ../..
# git clone https://github.com/TheImagingSource/tiscamera-tcamprop.git

# cd tiscamera-tcamprop
# mkdir build
# cd build
# cmake ..
# make
# make package
# sudo apt install ./tiscamera-tcamprop*.deb


# Alternate way
echo "Installing tiscamera"
mkdir tiscamera
cd tiscamera

wget https://s1-dl.theimagingsource.com/api/2.5/packages/software/sdk/tiscameraarm6464/0f58ab44-a87b-54df-98e6-1242c41d4ac1/tiscamera_1.1.0.4139_arm64_ubuntu_1804.deb
apt install -y ./tiscamera*.deb


# Install tcamdutils
echo "Installing tcamdutils"
cd ../..

mkdir tcamdutils
cd tcamdutils


# X86_64
# wget https://s1-dl.theimagingsource.com/api/2.5/packages/software/gstreamer/tiscameradutilsamd64/f286591a-43c8-52ae-a41a-9b8b6e928c52/tiscamera-dutils_1.0.0_amd64.deb
# apt install -y ./tiscamera-dutils*.deb


# ARM/aarch64/Jetson - CPU
# wget https://s1-dl.theimagingsource.com/api/2.5/packages/software/gstreamer/tiscameradutilsarm64/5a2eb71d-2a78-564b-b5cb-bf7019fbb777/tcamdutils_1.0.0.560_arm64.deb
# apt install -y ./tcamdutils*.deb

# ARM/aarch64/Jetson - CUDA
wget https://s1-dl.theimagingsource.com/api/2.5/packages/software/gstreamer/tcamdutilscudaarm64/a8eeb123-b803-5672-addf-c1d76abed8a0/tcamdutils-cuda_1.2.0.397_arm64.deb
apt install -y ./tcamdutils-cuda*.deb