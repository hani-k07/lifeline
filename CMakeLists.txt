cmake_minimum_required(VERSION 3.10)
project(dsa_engine)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)

# Add current directory to include path so #include "json.hpp" works
include_directories(${CMAKE_CURRENT_SOURCE_DIR})

add_executable(dsa_engine dsa_engine.cpp)
