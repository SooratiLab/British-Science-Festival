from launch import LaunchDescription
from launch.actions import SetEnvironmentVariable
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([

        # ROS2 uses domain 1; Unitree SDK uses domain 0 on eth0 — keeps them isolated
        SetEnvironmentVariable('ROS_DOMAIN_ID', '1'),
        # restrict CycloneDDS to loopback to isolate from Go2 DDS network
        SetEnvironmentVariable(
            'CYCLONEDDS_URI',
            '/ros2_ws/config/cyclonedds_internal.xml'
        ),

        # -- 1. Livox MID360 driver
        Node(
            package='livox_ros_driver2',
            executable='livox_ros_driver2_node',
            name='livox_lidar_publisher',
            output='screen',
            parameters=[{
                'xfer_format': 1,
                'multi_topic': 0,
                'data_src': 0,
                'publish_freq': 10.0,
                'output_data_type': 0,
                'frame_id': 'livox_frame',
                'user_config_path': '/ros2_ws/config/MID360_config.json',
                'cmdline_input_bd_code': 'livox0000000001',
            }]
        ),

        # -- 2. FAST-LIO (LiDAR odometry)
        Node(
            package='fast_lio',
            executable='fastlio_mapping',
            name='fast_lio',
            output='screen',
            parameters=['/ros2_ws/config/mid360.yaml'],
        ),

        # -- 3. odometry 2D filter (/Odometry -> /Odometry_2d)
        Node(
            package='go2_slam_nodes',
            executable='odom_2d_filter',
            name='odom_2d_filter',
            output='screen',
        ),

        # -- 4. robot driver (/cmd_vel -> Unitree SDK -> Go2)
        Node(
            package='go2_slam_nodes',
            executable='robot_driver',
            name='robot_driver',
            output='screen',
        ),

        # -- 5. RTABMap (SLAM / mapping mode)
        Node(
            package='rtabmap_slam',
            executable='rtabmap',
            name='rtabmap',
            output='screen',
            parameters=[{
                'frame_id': 'body',
                'odom_frame_id': 'camera_init',
                'map_frame_id': 'map',

                'subscribe_depth': False,
                'subscribe_rgb': False,
                'subscribe_scan_cloud': True,
                'approx_sync': True,
                'wait_for_transform': 2.0,
                'queue_size': 50,
                'topic_queue_size': 50,
                'sync_queue_size': 50,

                'Rtabmap/DetectionRate': '1.0',

                'Reg/Strategy': '1',
                'Reg/Force3DoF': 'true',
                'Grid/Sensor': '0',
                'Grid/CellSize': '0.05',
                'Grid/RangeMax': '8.0',
                'Grid/MinClusterSize': '20',
                'Grid/MinGroundHeight': '-0.3',
                'Grid/MaxGroundHeight': '0.1',
                'Grid/MaxObstacleHeight': '2.0',
                'Grid/NormalsSegmentation': 'false',
                'Grid/RayTracing': 'true',

                'RGBD/StartAtOrigin': 'true',
                'Icp/VoxelSize': '0.1',
                'Icp/MaxCorrespondenceDistance': '1.0',

                'map_always_update': True,
                'map_empty_ray_tracing': True,
                'database_path': '/ros2_ws/map/rtabmap.db',
            }],
            remappings=[
                ('scan_cloud', '/cloud_registered'),
                ('odom', '/Odometry_2d'),
            ],
        ),

        # -- 6. Nav2
        Node(
            package='nav2_controller',
            executable='controller_server',
            output='screen',
            parameters=['/ros2_ws/config/nav2_params.yaml'],
        ),
        Node(
            package='nav2_smoother',
            executable='smoother_server',
            output='screen',
            parameters=['/ros2_ws/config/nav2_params.yaml'],
        ),
        Node(
            package='nav2_planner',
            executable='planner_server',
            output='screen',
            parameters=['/ros2_ws/config/nav2_params.yaml'],
        ),
        Node(
            package='nav2_behaviors',
            executable='behavior_server',
            output='screen',
            parameters=['/ros2_ws/config/nav2_params.yaml'],
        ),
        Node(
            package='nav2_bt_navigator',
            executable='bt_navigator',
            output='screen',
            parameters=['/ros2_ws/config/nav2_params.yaml'],
            remappings=[('goal_pose', '_goal_pose_disabled')],
        ),
        Node(
            package='nav2_waypoint_follower',
            executable='waypoint_follower',
            output='screen',
            parameters=['/ros2_ws/config/nav2_params.yaml'],
        ),
        Node(
            package='nav2_velocity_smoother',
            executable='velocity_smoother',
            output='screen',
            parameters=['/ros2_ws/config/nav2_params.yaml'],
            remappings=[('cmd_vel', 'cmd_vel_nav'), ('cmd_vel_smoothed', 'cmd_vel')],
        ),
        Node(
            package='nav2_lifecycle_manager',
            executable='lifecycle_manager',
            name='lifecycle_manager',
            output='screen',
            parameters=['/ros2_ws/config/nav2_params.yaml'],
        ),

        # -- 7. Foxglove Bridge (WebSocket on port 8765)
        Node(
            package='foxglove_bridge',
            executable='foxglove_bridge',
            name='foxglove_bridge',
            output='screen',
        ),
    ])
