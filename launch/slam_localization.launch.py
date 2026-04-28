from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    return LaunchDescription([

        # restrict CycloneDDS to loopback to isolate from Go2 DDS network
        SetEnvironmentVariable(
            'CYCLONEDDS_URI',
            '/ros2_ws/config/cyclonedds_internal.xml'
        ),

        # -- 1. Livox MID360 driver
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource('/ros2_ws/launch/livox_mid360_launch.py')
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

        # -- 6. Nav2 (rtabmap publishes /map, no separate map server needed)
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                FindPackageShare('nav2_bringup'), '/launch/navigation_launch.py'
            ]),
            launch_arguments={
                'params_file': '/ros2_ws/config/nav2_params.yaml',
                'use_sim_time': 'false',
            }.items(),
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
