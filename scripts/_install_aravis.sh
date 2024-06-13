#!/bin/bash

# Install meson


# Install dependencies
echo Installing dependencies
apt install -y \
        libxml2-dev libglib2.0-dev cmake libusb-1.0-0-dev gobject-introspection \
        libgtk-3-dev gtk-doc-tools  xsltproc libgstreamer1.0-dev \
        libgstreamer-plugins-base1.0-dev libgstreamer-plugins-good1.0-dev \
        libgirepository1.0-dev gettext


# Install aravis SDK
echo Installing Aravis SDK

git clone https://github.com/AravisProject/aravis.git
cd aravis

meson setup build
cd build
ninja
ninja install




echo ""; echo ""; echo  "export GST_PLUGIN_PATH=$GST_PLUGIN_PATH:/usr/local/lib/aarch64-linux-gnu/gstreamer-1.0/" >>  ~/.bashrc



ldconfig
source ~/.bashrc