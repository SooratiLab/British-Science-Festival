#!/bin/bash
# SLAM mapping mode: builds map while driving the robot

mkdir -p "$(pwd)/map"

docker run -it --rm \
  --network=host \
  -e RMW_IMPLEMENTATION=rmw_cyclonedds_cpp \
  -v "$(pwd)/config:/ros2_ws/config" \
  -v "$(pwd)/launch:/ros2_ws/launch" \
  -v "$(pwd)/map:/ros2_ws/map" \
  -v "$(pwd)/ros2_ws/src/go2_slam_nodes:/ros2_ws/src/go2_slam_nodes" \
  go2-slam \
  ros2 launch /ros2_ws/launch/slam_mapping.launch.py
