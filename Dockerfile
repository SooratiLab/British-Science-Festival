FROM ros:humble-ros-base

ENV DEBIAN_FRONTEND=noninteractive

# Jetson boards often have a stale RTC clock; this prevents apt from rejecting repo signatures
RUN echo 'Acquire::Check-Valid-Until "false";' > /etc/apt/apt.conf.d/99no-check-valid-until

RUN apt-get update && apt-get install -y \
	git cmake python3-colcon-common-extensions \
	ros-humble-rmw-cyclonedds-cpp \
	ros-humble-pcl-ros \
	ros-humble-rtabmap-ros \
	ros-humble-nav2-bringup \
	ros-humble-navigation2 \
	ros-humble-tf2-ros \
	ros-humble-tf2-tools \
	ros-humble-foxglove-bridge \
	python3-pip \
	python3-gi python3-gi-cairo \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    gir1.2-gstreamer-1.0 \
    gir1.2-gst-plugins-base-1.0 \
	&& rm -rf /var/lib/apt/lists/* \
	&& pip install requests

WORKDIR /tmp
RUN git clone https://github.com/Livox-SDK/Livox-SDK2.git && \
	cd Livox-SDK2 && mkdir build && cd build && \
	cmake .. && make -j$(nproc) && make install && \
	rm -rf /tmp/Livox-SDK2

WORKDIR /ros2_ws/src
RUN git clone https://github.com/Livox-SDK/livox_ros_driver2.git && \
	cd livox_ros_driver2 && \
	git checkout 6b9356cadf77084619ba406e6a0eb41163b08039 && \
	cp -f package_ROS2.xml package.xml && \
	cp -rf launch_ROS2/ launch/
WORKDIR /ros2_ws
RUN /bin/bash -c "source /opt/ros/humble/setup.bash && \
	colcon build --packages-select livox_ros_driver2 \
	--cmake-args -DCMAKE_BUILD_TYPE=Release -DROS_EDITION=ROS2 -DHUMBLE_ROS=humble"

WORKDIR /ros2_ws/src
RUN git clone https://github.com/hku-mars/FAST_LIO.git --branch ROS2
WORKDIR /ros2_ws/src/FAST_LIO
RUN git submodule update --init --recursive
WORKDIR /ros2_ws
RUN /bin/bash -c "source /opt/ros/humble/setup.bash && \
	source /ros2_ws/install/setup.bash && \
	colcon build --packages-select fast_lio --cmake-args -DCMAKE_BUILD_TYPE=Release"

RUN mkdir -p /ros2_ws/config /ros2_ws/launch

# Build CycloneDDS 0.10.2 from source (ros apt packages don't include cmake config needed by cyclonedds Python wheel)
WORKDIR /tmp
RUN git clone --depth 1 --branch 0.10.2 https://github.com/eclipse-cyclonedds/cyclonedds.git && \
	cd cyclonedds && mkdir build && cd build && \
	cmake .. -DCMAKE_INSTALL_PREFIX=/usr/local -DENABLE_SHM=OFF && \
	make -j$(nproc) && make install && \
	ldconfig && \
	rm -rf /tmp/cyclonedds

# Unitree SDK2 Python: cloned to /opt so it stays available after build
RUN git clone https://github.com/unitreerobotics/unitree_sdk2_python.git /opt/unitree_sdk2_python && \
	CYCLONEDDS_HOME=/usr/local pip install -e /opt/unitree_sdk2_python

# go2_slam_nodes: custom ROS2 package (odom_2d_filter, robot_driver)
COPY ros2_ws/src /ros2_ws/src
RUN /bin/bash -c "source /opt/ros/humble/setup.bash && \
	source /ros2_ws/install/setup.bash && \
	cd /ros2_ws && colcon build --packages-select go2_slam_nodes --symlink-install \
	--cmake-args -DCMAKE_BUILD_TYPE=Release"

RUN echo '#!/bin/bash\nsource /opt/ros/humble/setup.bash\nsource /ros2_ws/install/setup.bash\nexec "$@"' > /entrypoint.sh \
	&& chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]

