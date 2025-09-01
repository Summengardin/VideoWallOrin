# Build example:
# docker buildx build -t vwvisioncontrollerinfer:7.0 .
# docker buildx build --build-arg DEEPSTREAM_VERSION=7.1 --build-arg BUILD_YOLO=false --build-arg BUILD_ARAVIS=true --build-arg BUILD_TISCAMERA=true --build-arg ARCH=aarch64 -t vwvisioncontrollerinfer:7.1 .

# Available Build Options:
# ----------------------
# 1. DEEPSTREAM_VERSION (default: 7.0)
#    - 7.0: Uses CUDA 12.2 and Python Apps 1.1.11
#    - 7.1: Uses CUDA 12.6 and Python Apps 1.2.0
#
# 2. CUDA_VERSION (default: 12.2)
#    - 12.2: Used with Deepstream 7.0
#    - 12.6: Used with Deepstream 7.1
#
# 3. PYTHON_APPS_VERSION (default: 1.1.11)
#    - 1.1.11: Used with Deepstream 7.0
#    - 1.2.0: Used with Deepstream 7.1
#
# 4. ARCH (default: x86_64)
#    - x86_64: For x86_64 architecture
#    - aarch64: For ARM64 architecture
#
# 5. BUILD_ARAVIS (default: false)
#    - true: Installs Aravis camera support
#    - false: Skips Aravis installation
#
# 6. BUILD_TISCAMERA (default: false)
#    - true: Installs TISCAMERA support
#    - false: Skips TISCAMERA installation
#
# 7. BUILD_YOLO (default: true)
#    - true: Installs and builds YOLO inference components
#    - false: Skips YOLO installation
#
#
#
# Example Build Commands:
# ----------------------
# 1. Basic build with Deepstream 7.0:
#    docker buildx build -t vwvisioncontrollerinfer:7.0 .
#
# 2. Deepstream 7.1 with all components for ARM64:
#    docker buildx build \
#      --build-arg DEEPSTREAM_VERSION=7.1 \
#      --build-arg BUILD_YOLO=true \
#      --build-arg BUILD_ARAVIS=true \
#      --build-arg BUILD_TISCAMERA=true \
#      --build-arg ARCH=aarch64 \
#      -t vwvisioncontrollerinfer:7.1 .
#
# 3. Deepstream 7.0 with only YOLO:
#    docker buildx build \
#      --build-arg BUILD_ARAVIS=false \
#      --build-arg BUILD_TISCAMERA=false \
#      -t vwvisioncontrollerinfer:7.0-yolo .
#
# 4. Deepstream 7.1 with only camera support:
#    docker buildx build \
#      --build-arg DEEPSTREAM_VERSION=7.1 \
#      --build-arg BUILD_YOLO=false \
#      --build-arg BUILD_ARAVIS=true \
#      --build-arg BUILD_TISCAMERA=true \
#      -t vwvisioncontrollerinfer:7.1-cameras .

# Default arguments
ARG DEEPSTREAM_VERSION=7.0
ARG CUDA_VERSION=12.2
ARG PYTHON_APPS_VERSION=1.1.11
ARG ARCH=x86_64
ARG BUILD_ARAVIS=false
ARG BUILD_TISCAMERA=false
ARG BUILD_YOLO=true

# Base image
FROM nvcr.io/nvidia/deepstream:${DEEPSTREAM_VERSION}-triton-multiarch

# Need to re-declare arguments after "FROM"
ARG DEEPSTREAM_VERSION
ARG CUDA_VERSION
ARG PYTHON_APPS_VERSION
ARG ARCH
ARG BUILD_ARAVIS
ARG BUILD_TISCAMERA
ARG BUILD_YOLO

SHELL ["/bin/bash", "-c"]

RUN if [[ "${DEEPSTREAM_VERSION}" == "7.0" ]]; then \
      if [[ ${CUDA_VERSION} != 12.2* ]] || [[ "${PYTHON_APPS_VERSION}" != "1.1.11" ]]; then \
        echo "Not correct config" && \
        echo "For Deepstream 7.0, expected CUDA_VERSION=12.2 and PYTHON_APPS_VERSION=1.1.11" && \
        echo "But got CUDA_VERSION='${CUDA_VERSION}', PYTHON_APPS_VERSION='${PYTHON_APPS_VERSION}'" && \
        exit 1; \
      fi; \
    elif [[ "${DEEPSTREAM_VERSION}" == "7.1" ]]; then \
      if [[ ${CUDA_VERSION} != 12.6* ]] || [[ "${PYTHON_APPS_VERSION}" != "1.2.0" ]]; then \
        echo "Not correct config" && \
        echo "For Deepstream 7.1, expected CUDA_VERSION=12.6 and PYTHON_APPS_VERSION=1.2.0" && \
        echo "But got CUDA_VERSION='${CUDA_VERSION}', PYTHON_APPS_VERSION='${PYTHON_APPS_VERSION}'" && \
        exit 1; \
      fi; \
    else \
      echo "Unsupported Deepstream version: ${DEEPSTREAM_VERSION}" && exit 1; \
    fi


ARG DEBIAN_FRONTEND="noninteractive"

# Common package installation
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Tools
    ffmpeg \
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
RUN /opt/nvidia/deepstream/deepstream/user_deepstream_python_apps_install.sh -v ${PYTHON_APPS_VERSION}
# RUN /opt/nvidia/deepstream/deepstream/user_deepstream_python_apps_install.sh -v


# Install YOLO - Setup directories and clone repositories
RUN if [ "$BUILD_YOLO" = "true" ] ; then \
    mkdir -p /app && cd /app && \
    git clone https://github.com/ultralytics/ultralytics && \
    git clone https://github.com/marcoslucianops/DeepStream-Yolo.git ; \
    fi

# Install YOLO - Install Python dependencies
RUN if [ "$BUILD_YOLO" = "true" ] ; then \
    cd /app/ultralytics && \
    PIP_CACHE_DIR=/tmp/pipcache pip install -e ".[export]" onnxslim && \
    rm -rf /tmp/pipcache ; \
    fi

# Install YOLO - Export model
RUN if [ "$BUILD_YOLO" = "true" ] ; then \
    # Fix export_yoloV8.py for weights_only=False. Needed for torch>=2.6
    sed -i "s/torch.load(weights, map_location='cpu')/torch.load(weights, map_location='cpu', weights_only=False)/" /app/DeepStream-Yolo/utils/export_yoloV8.py && \ 
    cp /app/DeepStream-Yolo/utils/export_yoloV8.py /app/ultralytics && \
    cd /app/ultralytics && \
    wget https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11s.pt && \
    python3 export_yoloV8.py -w yolo11s.pt && \
    cp yolo11s.pt.onnx labels.txt /app/DeepStream-Yolo && \
    mv /app/DeepStream-Yolo/yolo11s.pt.onnx /app/DeepStream-Yolo/yolo11l.pt.onnx ; \
    fi

# Install YOLO - Cleanup and build
RUN if [ "$BUILD_YOLO" = "true" ] ; then \
    rm -rf /app/ultralytics && \
    export CUDA_VER=${CUDA_VERSION} && \
    cd /app/DeepStream-Yolo && \
    make -C nvdsinfer_custom_impl_Yolo clean && \
    make -C nvdsinfer_custom_impl_Yolo ; \
    fi



# Optional: Install Aravis
ARG BUILD_ARAVIS
RUN if [ "$BUILD_ARAVIS" = "true" ] ; then \
    mkdir -p /tmp/aravis && cd /tmp/aravis && \
    git clone https://github.com/AravisProject/aravis.git && \
    meson setup build -Dviewer=enabled -Dintrospection=enabled && \
    ninja -C build && \
    ninja -C build install && \
    cd .. && rm -rf aravis ; \
    fi

# Optional: Install TISCAMERA
ARG BUILD_TISCAMERA
RUN if [ "$BUILD_TISCAMERA" = "true" ] ; then \
    apt-get update && apt-get install -y sudo libzip-dev && \
    pip3 install sphinx && \
    git clone https://github.com/TheImagingSource/tiscamera.git && \
    cd tiscamera && \
    git checkout v-tiscamera-1.1.0 && ./scripts/dependency-manager install && \
    mkdir build && cd build && cmake .. \
    -DTCAM_BUILD_ARAVIS=OFF \
    -DTCAM_BUILD_TOOLS=OFF \
    -DTCAM_BUILD_LIBUSB=OFF \
    -DTCAM_BUILD_DOCUMENTATION=OFF\
    -DTCAM_BUILD_V4L2=OFF \
    -DTCAM_ARAVIS_USB_VISION=OFF\
    -DTCAM_DOWNLOAD_MESON=OFF\
    && make && make install \
    && cd ../.. && rm -rf tiscamera ; \
    fi

# Set environment variables
ENV GST_PLUGIN_PATH="/usr/local/lib/${ARCH}-linux-gnu/gstreamer-1.0:${GST_PLUGIN_PATH:-}"
ENV LD_LIBRARY_PATH="/usr/local/lib/${ARCH}-linux-gnu:$LD_LIBRARY_PATH"
ENV USE_NEW_NVSTREAMMUX="yes"

# Install Python requirements
COPY requirements.txt /app/
RUN pip3 install --no-cache-dir -r /app/requirements.txt

# Copy application files
COPY /VisionController/config/infer/ /app/DeepStream-Yolo/
COPY /VisionController /app/VisionController
COPY /VisionController/data/fonts/ /usr/share/fonts/truetype/

# Install Vapix Python
COPY /vapix-python /app/vapix-python
RUN pip3 install --no-cache-dir -e /app/vapix-python

# Install Visca Python
# COPY /VISCA-IP_controller /app/VISCA-IP-controller
# RUN pip3 install --no-cache-dir -e /app/VISCA-IP-controller


# Set default environment variables
ENV Z3_URI1=rtsp://10.1.3.71/stream-1.sdp 
ENV Z3_URI2=rtsp://10.1.3.72/stream-1.sdp 
ENV Z3_URI3=rtsp://10.1.3.73/stream-1.sdp 
ENV AXIS_URI=rtsp://root:root@10.1.3.70/axis-media/media.amp?streamprofile=stream-1 