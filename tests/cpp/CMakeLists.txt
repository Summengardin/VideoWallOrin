cmake_minimum_required(VERSION 3.22)
project(FrameGrabber)

# Set the C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)

# Find required packages
find_package(PkgConfig REQUIRED)
pkg_check_modules(GST REQUIRED gstreamer-1.0 gstreamer-app-1.0)
pkg_check_modules(ARAVIS REQUIRED aravis-0.8)

# Include directories for the packages
include_directories(${GST_INCLUDE_DIRS})
include_directories(${ARAVIS_INCLUDE_DIRS})

# Link directories for the packages
link_directories(${GST_LIBRARY_DIRS})
link_directories(${ARAVIS_LIBRARY_DIRS})

# Add the source file
# add_library(frame_grabber SHARED frame_grabber.cpp)
add_executable(frame_grabber gst_aravis_grab.cpp)

# Link the libraries
target_link_libraries(frame_grabber ${GST_LIBRARIES} ${ARAVIS_LIBRARIES})
