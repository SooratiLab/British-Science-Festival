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

        # -- 5. RTABMap (localization mode, loads saved database)
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
                'Grid/RangeMax': '5.0',
                'Grid/MinClusterSize': '20',
                'Grid/MinGroundHeight': '-0.6',
                'Grid/MaxGroundHeight': '0.3',
                'Grid/RayTracing': 'true',
                'Grid/MaxObstacleHeight': '2.0',
                'Grid/NormalsSegmentation': 'false',

                'RGBD/StartAtOrigin': 'true',
                'Icp/VoxelSize': '0.1',
                'Icp/MaxCorrespondenceDistance': '1.0',

                'database_path': '/ros2_ws/map/rtabmap.db',
                'Mem/IncrementalMemory': 'false',
                'Mem/InitWMWithAllNodes': 'true',

                'map_always_update': False,
                'map_empty_ray_tracing': True,
            }],
            remappings=[
                ('scan_cloud', '/cloud_registered'),
                ('odom', '/Odometry_2d'),
            ],
        ),

        # -- 6. Nav2 (individual nodes so bt_navigator's /goal_pose subscription
        #    can be remapped — otherwise bt_navigator auto-navigates the moment
        #    any node (waypoint_manager, Foxglove) publishes to /goal_pose)
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
        Node(
            package='nav2_map_server',
            executable='map_server',
            name='keepout_mask_server',
            output='screen',
            parameters=[{
                'yaml_filename': '/ros2_ws/config/keepout_mask.yaml',
                'topic_name': '/keepout_mask',
                'frame_id': 'map'
            }]
        ),
        Node(
            package='nav2_map_server',
            executable='costmap_filter_info_server',
            name='costmap_filter_info_server',
            output='screen',
            parameters=['/ros2_ws/config/keepout_filter_params.yaml']
        ),

        # -- 7. waypoint manager (click-to-add via /goal_pose, /start_mission service)
        Node(
            package='go2_slam_nodes',
            executable='waypoint_manager',
            name='waypoint_manager',
            output='screen',
        ),

        # -- 8. Foxglove Bridge (WebSocket on port 8765)
        Node(
            package='foxglove_bridge',
            executable='foxglove_bridge',
            name='foxglove_bridge',
            output='screen',
        ),
    ])
