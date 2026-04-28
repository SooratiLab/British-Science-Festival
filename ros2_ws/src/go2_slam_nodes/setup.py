from setuptools import find_packages, setup

package_name = 'go2_slam_nodes'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    entry_points={
        'console_scripts': [
            'odom_2d_filter = go2_slam_nodes.odom_2d_filter:main',
            'robot_driver = go2_slam_nodes.robot_driver:main',
            'waypoint_manager = go2_slam_nodes.waypoint_manager:main',
        ],
    },
)
