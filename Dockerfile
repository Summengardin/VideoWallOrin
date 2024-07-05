FROM nvcr.io/nvidia/deepstream:7.0-triton-multiarch



ARG DEBIAN_FRONTEND="noninteractive"

RUN apt-get update && apt-get install -y --no-install-recommends \
    net-tools \
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
    && rm -rf /var/lib/apt/lists/*




# Install Deepstream-Python-Apps
# WORKDIR /opt/nvidia/deepstream/deepstream/sources/

# RUN git clone https://github.com/NVIDIA-AI-IOT/deepstream_python_apps \
#     && cd deepstream_python_apps \
#     && git submodule update --init
# RUN apt-get update && apt-get install -y apt-transport-https ca-certificates -y \
#     && update-ca-certificates \
#     && rm -rf /var/lib/apt/lists/*

# WORKDIR /opt/nvidia/deepstream/deepstream/sources/deepstream_python_apps/3rdparty/gstreamer/subprojects/gst-python/
# RUN meson setup build \
#     && cd build \
#     && ninja \
#     && ninja install

# WORKDIR /opt/nvidia/deepstream/deepstream/sources/deepstream_python_apps/bindings/build

# # RUN cmake .. \
# #     && make -j$(nproc) \
# #     && pip3 install ./pyds-1.1.11-py3-none*.whl




# WORKDIR /tmp

# # Install ARAVIS
# RUN git clone https://github.com/AravisProject/aravis.git && \
#     cd aravis && \
#     meson setup build -Dviewer=enabled -Dintrospection=enabled && \
#     ninja -C build && \
#     ninja -C build install && \
#     cd .. && rm -rf aravis


# # Install TISCAMERA
# WORKDIR /tisinstall
# # tiscamera trenger sudo... Se: tiscamera/scripts/dependency-manager
# RUN apt-get update && apt-get install sudo libzip-dev -y && pip3 install sphinx
# RUN git clone https://github.com/TheImagingSource/tiscamera.git && \
#     cd tiscamera && \
#     git checkout v-tiscamera-1.1.0 && ./scripts/dependency-manager install && \
#     mkdir build && cd build && cmake .. \
#     -DTCAM_BUILD_ARAVIS=ON \
#     -DTCAM_BUILD_TOOLS=ON \
#     -DTCAM_BUILD_LIBUSB=OFF \
#     -DTCAM_BUILD_V4L2=OFF \
#     && make && make install \
#     && cd ../.. && rm -rf tiscamera


# # Install Deepstream-Yolo
# WORKDIR /app
# ENV CUDA_VER=12.2
# RUN git clone https://github.com/marcoslucianops/DeepStream-Yolo.git
# WORKDIR /app/DeepStream-Yolo
# RUN make -C nvdsinfer_custom_impl_Yolo clean \
#     && make -C nvdsinfer_custom_impl_Yolo



# # ENV GST_PLUGIN_PATH="/usr/local/lib/x86_64-linux-gnu/gstreamer-1.0:$GST_PLUGIN_PATH"
# # ENV LD_LIBRARY_PATH="/usr/local/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"
# ENV USE_NEW_NVSTREAMMUX="yes"

# WORKDIR /app

# COPY add_delete_sources_showcase.py /app
# COPY add_remove_with_GUI.py /app
# COPY lib /app/lib
