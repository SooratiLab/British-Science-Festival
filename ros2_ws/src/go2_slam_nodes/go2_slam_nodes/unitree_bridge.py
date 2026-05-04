#!/usr/bin/env python3
"""
unitree_bridge.py

Standalone subprocess that owns the Unitree SDK DDS context.
Communicates with robot_driver via stdin/stdout JSON lines.
Running separately avoids CycloneDDS conflicts with rclpy.
"""
import sys
import json
import time

from unitree_sdk2py.core.channel import ChannelFactoryInitialize
from unitree_sdk2py.go2.sport.sport_client import SportClient


def main():
    ChannelFactoryInitialize(0, 'eth0')

    sport_client = SportClient()
    sport_client.SetTimeout(10.0)
    sport_client.Init()

    sport_client.RecoveryStand()
    time.sleep(1.0)
    sport_client.SpeedLevel(1)
    time.sleep(1.0)

    print('READY', flush=True)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            cmd = json.loads(line)
            action = cmd.get('action')
            if action == 'move':
                sport_client.Move(cmd['vx'], cmd['vy'], cmd['vyaw'])
            elif action == 'stop':
                sport_client.StopMove()
            elif action == 'stand':
                sport_client.RecoveryStand()
                time.sleep(0.5)
                sport_client.SpeedLevel(1)
            elif action == 'sit':
                sport_client.StandDown()
            elif action == 'hello':
                sport_client.Hello()
            elif action == 'wiggle':
                sport_client.WiggleHips()
        except Exception as e:
            print(f'ERROR: {e}', flush=True)


if __name__ == '__main__':
    main()
