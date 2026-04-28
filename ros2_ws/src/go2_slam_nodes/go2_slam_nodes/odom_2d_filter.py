#!/usr/bin/env python3
import math
import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry


class Odom2DFilter(Node):
    def __init__(self):
        super().__init__('odom_2d_filter')
        self.sub = self.create_subscription(
            Odometry, '/Odometry', self.callback, 10)
        self.pub = self.create_publisher(
            Odometry, '/Odometry_2d', 10)
        self.get_logger().info('Odom 2D filter started')

    def callback(self, msg):
        msg.pose.pose.position.z = 0.0

        q = msg.pose.pose.orientation
        siny = 2.0 * (q.w * q.z + q.x * q.y)
        cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        yaw = math.atan2(siny, cosy)

        msg.pose.pose.orientation.x = 0.0
        msg.pose.pose.orientation.y = 0.0
        msg.pose.pose.orientation.z = math.sin(yaw / 2.0)
        msg.pose.pose.orientation.w = math.cos(yaw / 2.0)

        self.pub.publish(msg)


def main():
    rclpy.init()
    rclpy.spin(Odom2DFilter())


if __name__ == '__main__':
    main()
