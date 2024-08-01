cmake_minimum_required(VERSION 3.10)
project(CameraFeed)

# Specify C++ standard
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED True)

# Find the GStreamer package
find_package(PkgConfig REQUIRED)
pkg_check_modules(GST REQUIRED gstreamer-1.0)
pkg_check_modules(GST_APP REQUIRED gstreamer-app-1.0)

# Include GStreamer headers
include_directories(${GST_INCLUDE_DIRS})
include_directories(${GST_APP_INCLUDE_DIRS})

# Add the executable
add_executable(CameraFeed main.cpp)

# Link GStreamer libraries
target_link_libraries(CameraFeed ${GST_LIBRARIES})
target_link_libraries(CameraFeed ${GST_APP_LIBRARIES})
