FROM nvcr.io/nvidia/deepstream:7.1-triton-multiarch

ARG DEBIAN_FRONTEND="noninteractive"

RUN apt-get update && apt-get install -y --no-install-recommends \
    # Networking tools
    net-tools \
    iputils-ping \
    kmod \
    \
    # GStreamer and plugins
    gstreamer1.0-qt5 \
    gstreamer1.0-gl \
    gstreamer1.0-x \
    gstreamer1.0-gtk3 \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    libgstreamer-plugins-good1.0-dev \
    libgstreamer-plugins-bad1.0-dev \
    \
    # Development tools
    build-essential \
    cmake \
    g++ \
    git \
    meson \
    libtool \
    m4 \
    autoconf \
    automake \
    gettext \
    \
    # Python and bindings
    python3 \
    python3-dev \
    python3-pip \
    python3.10-dev \
    python3-gi \
    python3-gst-1.0 \
    python-gi-dev \
    \
    # GLib and GObject introspection
    libglib2.0-dev \
    libglib2.0-dev-bin \
    libgirepository1.0-dev \
    gobject-introspection \
    \
    # XML/XSL and GTK/Qt docs
    libxml2-dev \
    xsltproc \
    gtk-doc-tools \
    \
    # GTK/Qt and Cairo
    libgtk-3-dev \
    qtbase5-dev \
    qtdeclarative5-dev \
    libcairo2-dev \
    \
    # USB
    libusb-1.0-0-dev \
    \
    && rm -rf /var/lib/apt/lists/*


# Deepstream Additional Installs
RUN /opt/nvidia/deepstream/deepstream/user_additional_install.sh


# RUN ls -l /opt/nvidia/deepstream/deepstream/lib/libnvbufsurface.so \
#     && echo "nvbufsurface-library found, proceeding with CMake" \
#     || (echo "nvbufsurface-library not found, aborting" && exit 1)

# Install Deepstream-Python-Apps

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


# Visca IP Controller
COPY /VISCA-IP-Controller /tmp/VISCA-IP-Controller
WORKDIR /tmp/VISCA-IP-Controller
RUN pip3 install .


# # Install Deepstream-Yolo
# WORKDIR /app
# ENV CUDA_VER=12.6
# RUN git clone https://github.com/marcoslucianops/DeepStream-Yolo.git
# WORKDIR /app/DeepStream-Yolo
# RUN make -C nvdsinfer_custom_impl_Yolo clean \
#     && make -C nvdsinfer_custom_impl_Yolo



ENV GST_PLUGIN_PATH="/usr/local/lib/x86_64-linux-gnu/gstreamer-1.0:${GST_PLUGIN_PATH:-}"
ENV LD_LIBRARY_PATH="/usr/local/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"
# ENV GST_PLUGIN_PATH="/usr/local/lib/aarch64-linux-gnu/gstreamer-1.0"
# ENV LD_LIBRARY_PATH="/usr/local/lib/aarch64-linux-gnu:$LD_LIBRARY_PATH"
ENV USE_NEW_NVSTREAMMUX="yes"

WORKDIR /app

COPY requirements.txt /app/

# RUN pip3 install -r requirements.txt

COPY /VisionController /app/VisionController 
