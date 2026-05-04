#!/usr/bin/env python3
"""
robot_driver.py

ROS2 node that bridges Nav2 /cmd_vel to the Unitree Go2.
The Unitree SDK runs in a subprocess (unitree_bridge.py) to avoid
CycloneDDS library conflicts with rclpy in the same process.
"""
import json
import os
import socket
import subprocess
import sys
import threading
import time

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

MAX_LINEAR_VEL  = 0.5
MAX_LATERAL_VEL = 0.2
MAX_YAW_VEL     = 0.8
CMD_TIMEOUT     = 0.5
ACTION_UDP_PORT = 9878


def clamp(value, min_val, max_val):
    return max(min_val, min(value, max_val))


class RobotDriver(Node):
    def __init__(self, bridge: subprocess.Popen):
        super().__init__('robot_driver')
        self.bridge = bridge
        self.lock = threading.Lock()
        self.last_cmd_time = time.time()
        self.is_moving = False

        self.create_subscription(Twist, '/cmd_vel', self._cmd_vel_callback, 10)
        self.create_timer(0.1, self._watchdog)
        threading.Thread(target=self._action_listener, daemon=True).start()

        self.get_logger().info(
            f'Robot driver ready | '
            f'limits: linear={MAX_LINEAR_VEL} m/s, '
            f'lateral={MAX_LATERAL_VEL} m/s, '
            f'yaw={MAX_YAW_VEL} rad/s'
        )

    def _send(self, cmd: dict):
        try:
            line = json.dumps(cmd) + '\n'
            self.bridge.stdin.write(line)
            self.bridge.stdin.flush()
        except Exception as e:
            self.get_logger().error(f'Bridge write error: {e}')

    def _cmd_vel_callback(self, msg: Twist):
        vx   = clamp(msg.linear.x,  -MAX_LINEAR_VEL,  MAX_LINEAR_VEL)
        vy   = clamp(msg.linear.y,  -MAX_LATERAL_VEL, MAX_LATERAL_VEL)
        vyaw = clamp(msg.angular.z, -MAX_YAW_VEL,     MAX_YAW_VEL)

        with self.lock:
            self._send({'action': 'move', 'vx': vx, 'vy': vy, 'vyaw': vyaw})
            self.last_cmd_time = time.time()
            self.is_moving = True

    def _watchdog(self):
        with self.lock:
            if self.is_moving and time.time() - self.last_cmd_time > CMD_TIMEOUT:
                self._send({'action': 'stop'})
                self.is_moving = False
                self.get_logger().info('Auto-stop: no cmd_vel received')

    def _action_listener(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('0.0.0.0', ACTION_UDP_PORT))
        sock.settimeout(1.0)
        self.get_logger().info(f'Action listener on UDP port {ACTION_UDP_PORT}')

        while True:
            try:
                data, addr = sock.recvfrom(256)
                action = data.decode('utf-8').strip()
                self.get_logger().info(f'[ACTION] {action} from {addr}')
                self._send({'action': action})
            except socket.timeout:
                pass
            except Exception as e:
                self.get_logger().error(f'[ACTION] error: {e}')


def main():
    bridge_script = os.path.join(
        os.path.dirname(__file__), 'unitree_bridge.py'
    )
    # Isolate bridge subprocess from ROS DDS environment:
    # - Remove CYCLONEDDS_URI so Unitree SDK can use eth0 freely
    # - Put /usr/local/lib first so our CycloneDDS (no Iceoryx) is loaded
    #   before ROS's version (which has Iceoryx compiled in)
    bridge_env = os.environ.copy()
    # Disable SHM so CycloneDDS never creates iox_pub — prevents the assertion
    # (wr->m_iox_pub == NULL) == (d->a.iox_chunk == NULL) even when iceoryx
    # libraries are present on the system.  No loopback restriction here so the
    # bridge can reach the robot over eth0.
    bridge_env['CYCLONEDDS_URI'] = (
        '<CycloneDDS><Domain>'
        '<SharedMemory><Enable>false</Enable></SharedMemory>'
        '</Domain></CycloneDDS>'
    )
    existing_ld = bridge_env.get('LD_LIBRARY_PATH', '')
    bridge_env['LD_LIBRARY_PATH'] = f'/usr/local/lib:{existing_ld}' if existing_ld else '/usr/local/lib'

    bridge = subprocess.Popen(
        [sys.executable, bridge_script],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        text=True,
        env=bridge_env,
    )

    # Wait for the bridge to finish SDK init
    for line in bridge.stdout:
        line = line.strip()
        if line == 'READY':
            print('Unitree bridge ready')
            break
        print(f'[bridge] {line}')

    if bridge.poll() is not None:
        print(f'ERROR: Unitree bridge exited early (code {bridge.returncode})', file=sys.stderr)
        sys.exit(1)

    rclpy.init()
    node = RobotDriver(bridge)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
        bridge.stdin.close()
        bridge.terminate()


if __name__ == '__main__':
    main()
