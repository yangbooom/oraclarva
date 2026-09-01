cmake_minimum_required(VERSION 3.22.1)
project(oraclarva_android LANGUAGES CXX)

set(ORACLARVA_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../../../..")

add_library(
    oraclarva_android
    SHARED
    android_bridge.cpp
    "${ORACLARVA_ROOT}/native/lif_core.cpp"
    "${ORACLARVA_ROOT}/native/spatial_controller.cpp"
    "${ORACLARVA_ROOT}/native/repeat_core.cpp"
    "${ORACLARVA_ROOT}/native/mobile_core.cpp"
)

target_compile_features(oraclarva_android PRIVATE cxx_std_17)
target_compile_definitions(oraclarva_android PRIVATE ORACLARVA_MOBILE_BUILD)
target_compile_options(
    oraclarva_android
    PRIVATE
    -O3
    -Wall
    -Wextra
    -Werror
    -fvisibility=hidden
    -fvisibility-inlines-hidden
)
target_include_directories(
    oraclarva_android
    PRIVATE
    "${ORACLARVA_ROOT}/native"
)

if(ANDROID)
    find_library(log_library log)
    target_link_libraries(oraclarva_android PRIVATE "${log_library}")
endif()
