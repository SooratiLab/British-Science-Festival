#!/bin/bash
# Localization and waypoint navigation mode: uses saved RTABMap database

docker run -it --rm \
  --network=host \
  -e RMW_IMPLEMENTATION=rmw_cyclonedds_cpp \
  -v "$(pwd)/config:/ros2_ws/config" \
  -v "$(pwd)/launch:/ros2_ws/launch" \
  go2-slam \
  ros2 launch /ros2_ws/launch/slam_localization.launch.py
