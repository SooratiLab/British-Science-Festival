#!/bin/bash
# SLAM mapping mode: builds map while driving the robot

docker run -it --rm \
  --network=host \
  -e RMW_IMPLEMENTATION=rmw_cyclonedds_cpp \
  -v "$(pwd)/config:/ros2_ws/config" \
  -v "$(pwd)/launch:/ros2_ws/launch" \
  go2-slam \
  ros2 launch /ros2_ws/launch/slam_mapping.launch.py
