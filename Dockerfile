FROM nvcr.io/nvidia/deepstream:7.1-triton-multiarch

ARG DEBIAN_FRONTEND="noninteractive"

RUN apt-get update && apt-get install -y --no-install-recommends \
    net-tools \
    kmod \
    iputils-ping \
    libxml2-dev \
    gobject-introspection \
    libgirepository1.0-dev \
    libgstreamer-plugins-good1.0-dev \
    libgstreamer-plugins-bad1.0-dev \
    libcairo2-dev \
    libgirepository1.0-dev \
    libusb-1.0-0-dev \
    gtk-doc-tools \
    xsltproc \
    gstreamer1.0-qt5 \
    gstreamer1.0-gl \
    libgstreamer-plugins-bad1.0-dev \
    gstreamer1.0-x \
    gstreamer1.0-gtk3 \
    qtbase5-dev \
    qtdeclarative5-dev \
    libgtk-3-dev \
    python3-gi python3-dev python3-gst-1.0 python-gi-dev git meson \
    python3 python3-pip python3.10-dev cmake g++ build-essential libglib2.0-dev \
    libglib2.0-dev-bin libgstreamer1.0-dev libtool m4 autoconf automake libgirepository1.0-dev libcairo2-dev \
    libxml2-dev libglib2.0-dev cmake libusb-1.0-0-dev gobject-introspection \
    libgtk-3-dev gtk-doc-tools  xsltproc libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev libgstreamer-plugins-good1.0-dev \
    libgirepository1.0-dev gettext \
    && rm -rf /var/lib/apt/lists/*



RUN ls -l /opt/nvidia/deepstream/deepstream/lib/libnvbufsurface.so \
    && echo "nvbufsurface-library found, proceeding with CMake" \
    || (echo "nvbufsurface-library not found, aborting" && exit 1)

# Install Deepstream-Python-Apps
RUN /opt/nvidia/deepstream/deepstream/user_additional_install.sh
# WORKDIR /opt/nvidia/deepstream/deepstream/sources/

# RUN git clone https://github.com/NVIDIA-AI-IOT/deepstream_python_apps \
#     && cd deepstream_python_apps \
#     && git submodule update --init \
#     && apt-get update && apt-get install -y apt-transport-https ca-certificates -y \
#     && update-ca-certificates \
#     && cd 3rdparty/gstreamer/subprojects/gst-python/ \
#     && meson setup build \
#     && cd build \
#     && ninja \
#     && ninja install \
#     && cd /opt/nvidia/deepstream/deepstream/sources/deepstream_python_apps/bindings \ 
#     && mkdir build 
#     # && cd build \
#     # && cmake .. -DPIP_PLATFORM=linux_aarch64 \
#     # && make -j$(nproc) \
#     # && pip3 install ./pyds-*.whl



COPY /VISCA-IP-Controller /tmp/VISCA-IP-Controller

WORKDIR /tmp/VISCA-IP-Controller

RUN pip3 install .


# # Install Deepstream-Yolo
# WORKDIR /app
# ENV CUDA_VER=12.2
# RUN git clone https://github.com/marcoslucianops/DeepStream-Yolo.git
# WORKDIR /app/DeepStream-Yolo
# RUN make -C nvdsinfer_custom_impl_Yolo clean \
#     && make -C nvdsinfer_custom_impl_Yolo



# ENV GST_PLUGIN_PATH="/usr/local/lib/x86_64-linux-gnu/gstreamer-1.0:$GST_PLUGIN_PATH"
ENV GST_PLUGIN_PATH="/usr/local/lib/aarch64-linux-gnu/gstreamer-1.0"
ENV LD_LIBRARY_PATH="/usr/local/lib/aarch64-linux-gnu:$LD_LIBRARY_PATH"
ENV USE_NEW_NVSTREAMMUX="yes"

WORKDIR /app

COPY requirements.txt /app/

# RUN pip3 install -r requirements.txt

COPY /VisionController /app/VisionController 
