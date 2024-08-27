cmake_minimum_required(VERSION 3.10)

# Set your project name
project(AravisPipeline)

# Set the C++ standard to C++20
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED True)

# Find the required packages
find_package(PkgConfig REQUIRED)
pkg_check_modules(GST REQUIRED gstreamer-1.0)
pkg_check_modules(GLIB REQUIRED glib-2.0)

# Include directories
include_directories(${GST_INCLUDE_DIRS})
include_directories(${GLIB_INCLUDE_DIRS})

# Link directories
link_directories(${GST_LIBRARY_DIRS})
link_directories(${GLIB_LIBRARY_DIRS})

# Add the executable
add_executable(aravis_pipeline src/aravis_pipeline.cpp)

# Link the libraries
target_link_libraries(aravis_pipeline ${GST_LIBRARIES} ${GLIB_LIBRARIES})
