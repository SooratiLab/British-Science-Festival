# Unitree Go2 SLAM & Waypoint Navigation

LiDAR-based SLAM and autonomous waypoint navigation for the Unitree Go2 quadruped robot, using a Livox MID360 LiDAR on a Jetson Orin NX. The entire stack runs inside Docker with no host ROS2 installation required.

## Hardware

| Component | Details |
|-----------|---------|
| Robot | Unitree Go2 |
| LiDAR | Livox MID360 |
| Compute | NVIDIA Jetson Orin NX (aarch64, Ubuntu 22.04) |

## Software Stack

| Role | Package |
|------|---------|
| LiDAR driver | [livox_ros_driver2](https://github.com/Livox-SDK/livox_ros_driver2) |
| LiDAR odometry | [FAST-LIO](https://github.com/hku-mars/FAST_LIO) |
| SLAM | [RTABMap](http://wiki.ros.org/rtabmap_ros) |
| Navigation | [Nav2](https://nav2.ros.org) |
| Robot control | Unitree SDK2 Python |
| Visualization | Foxglove Studio (port 8765) |
| ROS2 distro | Humble (via `ros:humble-ros-base` Docker image) |

## Architecture

```
Livox MID360
    │ /livox/lidar (PointCloud2)
    ▼
livox_ros_driver2
    │ /cloud_registered (PointCloud2)
    ▼
FAST-LIO  ──────────────────────────────── TF: camera_init → body
    │ /Odometry (3D)
    ▼
odom_2d_filter
    │ /Odometry_2d (2D, z/roll/pitch zeroed)
    ▼
RTABMap  ──────────────────────────────── /map (OccupancyGrid)
    │                                      TF: map → camera_init
    ▼
Nav2 (planner + controller + waypoint_follower)
    │ /cmd_vel
    ▼
robot_driver  ──── subprocess ──── unitree_bridge.py
                   (JSON over stdin)       │
                                      Unitree SDK2
                                           │ DDS (eth0, domain 0)
                                           ▼
                                       Go2 robot
```

**DDS isolation:** ROS2 runs on domain 1 with CycloneDDS restricted to loopback (`cyclonedds_internal.xml`). The Unitree SDK runs in a separate subprocess (`unitree_bridge.py`) on domain 0 over `eth0`, avoiding library conflicts between the two CycloneDDS instances.

## Network Setup

Connect the Jetson to the Go2's built-in WiFi access point. The default subnet is `192.168.123.x`.

| Device | IP |
|--------|----|
| Jetson (eth0) | `192.168.123.18` |
| Livox MID360 | `192.168.123.20` |

Update `config/MID360_config.json` if your Jetson IP is different (`host_net_info` fields).

## Quick Start

### 1. Build the Docker image

```bash
docker build -t go2-slam .
```

This takes ~20 minutes on first build (compiles Livox-SDK2, FAST-LIO, CycloneDDS, and the Unitree Python SDK).

### 2. Mapping mode — build a map

Drive the robot around the environment to build a map. The map is saved to `./map/rtabmap.db`.

```bash
./run_mapping.sh
```

Visualize in Foxglove Studio by connecting to `ws://<jetson-ip>:8765`.

When mapping is complete, stop the container with `Ctrl+C`. The map is persisted to `./map/rtabmap.db` via a Docker volume mount.

### 3. Localization & waypoint navigation mode

Load the saved map and navigate autonomously through a sequence of waypoints.

```bash
./run_localization.sh
```

**Workflow in Foxglove Studio:**

1. Open Foxglove and connect to `ws://<jetson-ip>:8765`
2. Use **Publish Pose** to click waypoints on the map — each click adds a numbered waypoint marker
3. When all waypoints are set, call the `/start_mission` service:

```bash
# Inside the running container
ros2 service call /start_mission std_srvs/srv/Trigger {}
```

The robot navigates through the waypoints in order.

**Other services:**

```bash
# Remove the last added waypoint
ros2 service call /undo_waypoint std_srvs/srv/Trigger {}

# Clear all waypoints (also stops an in-progress mission)
ros2 service call /clear_waypoints std_srvs/srv/Trigger {}
```

## Configuration

| File | Purpose |
|------|---------|
| `config/MID360_config.json` | LiDAR IP and port configuration |
| `config/mid360.yaml` | FAST-LIO parameters (extrinsics, filter settings) |
| `config/nav2_params.yaml` | Nav2 planner, controller, costmap settings |
| `config/cyclonedds_internal.xml` | CycloneDDS loopback config for ROS2 domain isolation |

### Tuning navigation

Key parameters in `config/nav2_params.yaml`:

```yaml
controller_server:
  ros__parameters:
    FollowPath:
      desired_linear_vel: 0.5      # m/s — reduce if robot oscillates
      lookahead_dist: 1.2          # m
      rotate_to_heading_min_angle: 0.3  # rad — min angle to rotate in place

general_goal_checker:
  xy_goal_tolerance: 0.3           # m
  yaw_goal_tolerance: 0.5          # rad
```

### Velocity limits

In `ros2_ws/src/go2_slam_nodes/go2_slam_nodes/robot_driver.py`:

```python
MAX_LINEAR_VEL  = 0.5   # m/s forward/backward
MAX_LATERAL_VEL = 0.2   # m/s sideways
MAX_YAW_VEL     = 0.8   # rad/s rotation
```

## Custom ROS2 Nodes (`go2_slam_nodes`)

| Node | Description |
|------|-------------|
| `robot_driver` | Subscribes to `/cmd_vel`, forwards to `unitree_bridge.py` subprocess via JSON over stdin |
| `unitree_bridge` | Standalone subprocess owning the Unitree SDK DDS context; receives JSON commands and calls `SportClient` |
| `odom_2d_filter` | Converts FAST-LIO's 3D `/Odometry` to a 2D `/Odometry_2d` (zeroes z, roll, pitch) for Nav2 |
| `waypoint_manager` | Collects waypoints from `/goal_pose`, visualizes them as markers, executes via Nav2 `FollowWaypoints` on `/start_mission` |

The source is volume-mounted into the container at runtime (`--symlink-install`), so editing Python files in `ros2_ws/src/go2_slam_nodes/` takes effect immediately on node restart without rebuilding the image.

## Troubleshooting

**Robot not moving**

Check that `robot_driver` is running and the bridge subprocess started:
```bash
docker exec -it <container> bash -c "
  source /opt/ros/humble/setup.bash && source /ros2_ws/install/setup.bash &&
  ROS_DOMAIN_ID=1 CYCLONEDDS_URI=/ros2_ws/config/cyclonedds_internal.xml \
  ros2 node list"
# /robot_driver should appear
```

**No LiDAR topics**

Verify the MID360 IP in `config/MID360_config.json` matches your network. The LiDAR should be pingable at `192.168.123.20`.

**`/start_mission` returns `Nav2 follow_waypoints server not available`**

Nav2 lifecycle nodes haven't finished activating. Wait ~10 seconds after launch for the lifecycle manager to bring up all nodes, then retry.

**Map not loading in localization mode**

Ensure `./map/rtabmap.db` exists (created during a mapping session). The file is mounted into the container at `/ros2_ws/map/rtabmap.db`.
