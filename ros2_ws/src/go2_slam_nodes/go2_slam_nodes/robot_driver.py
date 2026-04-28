#!/usr/bin/env python3
"""
robot_driver.py

ROS2 node that bridges Nav2 /cmd_vel directly to the Unitree Go2
via the Unitree SDK2 SportClient. Replaces the cmd_vel_relay +
cmd_vel_bridge split that required a separate host-side process.

Requires --network=host so eth0 is visible inside the container.
"""
import time
import socket
import threading

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.go2.sport.sport_client import SportClient

# --- safety limits ---
MAX_LINEAR_VEL = 0.5
MAX_LATERAL_VEL = 0.2
MAX_YAW_VEL = 0.8
CMD_TIMEOUT = 0.5       # seconds before auto-stop if no cmd_vel arrives
ACTION_UDP_PORT = 9878  # UDP port for robot action commands (sit, stand, etc.)


def clamp(value, min_val, max_val):
    return max(min_val, min(value, max_val))


class RobotDriver(Node):
    def __init__(self, sport_client: SportClient):
        super().__init__('robot_driver')
        self.sport_client = sport_client
        self.lock = threading.Lock()
        self.action_in_progress = False
        self.last_cmd_time = time.time()
        self.is_moving = False

        self.create_subscription(Twist, '/cmd_vel', self._cmd_vel_callback, 10)

        # watchdog timer: stops the robot if /cmd_vel goes silent
        self.create_timer(0.1, self._watchdog)

        # action listener runs in a background thread to avoid blocking the ROS2 executor
        threading.Thread(target=self._action_listener, daemon=True).start()

        self.get_logger().info(
            f'Robot driver ready | '
            f'limits: linear={MAX_LINEAR_VEL} m/s, '
            f'lateral={MAX_LATERAL_VEL} m/s, '
            f'yaw={MAX_YAW_VEL} rad/s | '
            f'timeout={CMD_TIMEOUT}s'
        )

    def _cmd_vel_callback(self, msg: Twist):
        vx = clamp(msg.linear.x, -MAX_LINEAR_VEL, MAX_LINEAR_VEL)
        vy = clamp(msg.linear.y, -MAX_LATERAL_VEL, MAX_LATERAL_VEL)
        vyaw = clamp(msg.angular.z, -MAX_YAW_VEL, MAX_YAW_VEL)

        with self.lock:
            if self.action_in_progress:
                return
            self.sport_client.Move(vx, vy, vyaw)
            self.last_cmd_time = time.time()
            self.is_moving = True

    def _watchdog(self):
        with self.lock:
            if (self.is_moving
                    and not self.action_in_progress
                    and time.time() - self.last_cmd_time > CMD_TIMEOUT):
                self.sport_client.StopMove()
                self.is_moving = False
                self.get_logger().info('Auto-stop: no cmd_vel received')

    def _action_listener(self):
        # receives short string commands (sit, stand, hello, ...) over UDP
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', ACTION_UDP_PORT))
        sock.settimeout(1.0)
        self.get_logger().info(f'Action listener started on port {ACTION_UDP_PORT}')

        while True:
            try:
                data, addr = sock.recvfrom(256)
                action = data.decode('utf-8').strip()
                self.get_logger().info(f'[ACTION] received: {action} from {addr}')
                self._execute_action(action)
            except socket.timeout:
                pass
            except Exception as e:
                self.get_logger().error(f'[ACTION] listener error: {e}')

    def _execute_action(self, action: str):
        with self.lock:
            self.action_in_progress = True
        try:
            if action == 'sit':
                self.sport_client.StandDown()
            elif action == 'stand':
                self.sport_client.RecoveryStand()
                time.sleep(0.5)
                self.sport_client.SpeedLevel(1)
            elif action == 'hello':
                self.sport_client.Hello()
            elif action == 'wiggle':
                self.sport_client.WiggleHips()
            elif action == 'nod':
                self.sport_client.Pose(True)
                for _ in range(2):
                    time.sleep(0.3)
                    self.sport_client.Euler(0.0, 0.3, 0.0)
                    time.sleep(0.3)
                    self.sport_client.Euler(0.0, 0.0, 0.0)
                self.sport_client.Pose(False)
            else:
                self.get_logger().warn(f'[ACTION] unknown: {action}')
        except Exception as e:
            self.get_logger().error(f'[ACTION] error executing {action}: {e}')
        finally:
            with self.lock:
                self.action_in_progress = False


def main():
    # Unitree SDK must be initialized before rclpy so its DDS context
    # is set up on eth0 independently of ROS2's CycloneDDS instance
    ChannelFactoryInitialize(0, 'eth0')

    sport_client = SportClient()
    sport_client.SetTimeout(10.0)
    sport_client.Init()
    print('SportClient initialized')

    sport_client.RecoveryStand()
    time.sleep(1.0)
    sport_client.SpeedLevel(1)
    time.sleep(1.0)

    rclpy.init()
    node = RobotDriver(sport_client)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
