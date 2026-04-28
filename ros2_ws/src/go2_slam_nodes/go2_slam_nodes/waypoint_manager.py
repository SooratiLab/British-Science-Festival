#!/usr/bin/env python3
"""
waypoint_manager.py

Collects waypoints by subscribing to /goal_pose (Foxglove "Publish Pose"
button), visualizes them as numbered markers on the map, and navigates
through them via Nav2 FollowWaypoints on /start_mission service call.

Services:
  /undo_waypoint   (std_srvs/Trigger) - remove last added waypoint
  /clear_waypoints (std_srvs/Trigger) - remove all waypoints
  /start_mission   (std_srvs/Trigger) - navigate through all waypoints in order

Publishes:
  /waypoint_markers (visualization_msgs/MarkerArray) - numbered markers on map
"""
from copy import deepcopy

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from geometry_msgs.msg import PoseStamped
from visualization_msgs.msg import Marker, MarkerArray
from std_srvs.srv import Trigger
from nav2_msgs.action import FollowWaypoints


class WaypointManager(Node):
    def __init__(self):
        super().__init__('waypoint_manager')
        self.waypoints: list[PoseStamped] = []
        self.mission_running = False

        self.create_subscription(PoseStamped, '/goal_pose', self._on_goal_pose, 10)

        self.marker_pub = self.create_publisher(MarkerArray, '/waypoint_markers', 10)

        self.create_service(Trigger, 'undo_waypoint', self._undo_waypoint)
        self.create_service(Trigger, 'clear_waypoints', self._clear_waypoints)
        self.create_service(Trigger, 'start_mission', self._start_mission)

        self.nav_client = ActionClient(self, FollowWaypoints, 'follow_waypoints')

        # republish markers periodically so they stay visible in Foxglove
        self.create_timer(1.0, self._publish_markers)

        self.get_logger().info(
            'Waypoint manager ready\n'
            '  click on the map in Foxglove to add waypoints\n'
            '  ros2 service call /undo_waypoint   std_srvs/srv/Trigger\n'
            '  ros2 service call /clear_waypoints  std_srvs/srv/Trigger\n'
            '  ros2 service call /start_mission    std_srvs/srv/Trigger'
        )

    # --- waypoint collection ---

    def _on_goal_pose(self, msg: PoseStamped):
        if self.mission_running:
            self.get_logger().warn(
                'Mission in progress — waypoint not added. '
                'Call /clear_waypoints to reset after mission.'
            )
            return
        self.waypoints.append(msg)
        n = len(self.waypoints)
        self.get_logger().info(
            f'Waypoint [{n}] added: '
            f'x={msg.pose.position.x:.2f}, y={msg.pose.position.y:.2f}'
        )
        self._publish_markers()

    # --- services ---

    def _undo_waypoint(self, request, response):
        if not self.waypoints:
            response.success = False
            response.message = 'No waypoints to undo'
            return response
        self.waypoints.pop()
        self._publish_markers()
        n = len(self.waypoints)
        self.get_logger().info(f'Last waypoint removed ({n} remaining)')
        response.success = True
        response.message = f'{n} waypoint(s) remaining'
        return response

    def _clear_waypoints(self, request, response):
        self.waypoints.clear()
        self.mission_running = False
        self._publish_markers()
        self.get_logger().info('All waypoints cleared')
        response.success = True
        response.message = 'All waypoints cleared'
        return response

    def _start_mission(self, request, response):
        if not self.waypoints:
            response.success = False
            response.message = 'No waypoints set'
            return response
        if self.mission_running:
            response.success = False
            response.message = 'Mission already running'
            return response
        if not self.nav_client.wait_for_server(timeout_sec=3.0):
            response.success = False
            response.message = 'Nav2 follow_waypoints server not available'
            return response

        goal = FollowWaypoints.Goal()
        goal.poses = self.waypoints

        self.mission_running = True
        self.get_logger().info(f'Mission started: {len(self.waypoints)} waypoints')

        future = self.nav_client.send_goal_async(
            goal, feedback_callback=self._on_feedback
        )
        future.add_done_callback(self._on_goal_response)

        response.success = True
        response.message = f'Mission started with {len(self.waypoints)} waypoints'
        return response

    # --- Nav2 action callbacks ---

    def _on_feedback(self, feedback_msg):
        current = feedback_msg.feedback.current_waypoint
        total = len(self.waypoints)
        self.get_logger().info(f'Navigating to waypoint [{current + 1}/{total}]')

    def _on_goal_response(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().warn('Mission goal rejected by Nav2')
            self.mission_running = False
            return
        goal_handle.get_result_async().add_done_callback(self._on_result)

    def _on_result(self, future):
        missed = future.result().result.missed_waypoints
        if missed:
            self.get_logger().warn(f'Mission complete. Missed waypoints: {list(missed)}')
        else:
            self.get_logger().info('Mission complete. All waypoints reached.')
        self.mission_running = False

    # --- marker visualization ---

    def _publish_markers(self):
        marker_array = MarkerArray()

        # clear all previous markers
        clear = Marker()
        clear.action = Marker.DELETEALL
        clear.ns = ''
        marker_array.markers.append(clear)

        now = self.get_clock().now().to_msg()

        for i, wp in enumerate(self.waypoints):
            frame = wp.header.frame_id or 'map'

            # sphere at waypoint position
            sphere = Marker()
            sphere.header.frame_id = frame
            sphere.header.stamp = now
            sphere.ns = 'waypoints'
            sphere.id = i * 2
            sphere.type = Marker.SPHERE
            sphere.action = Marker.ADD
            sphere.pose = wp.pose
            sphere.scale.x = sphere.scale.y = sphere.scale.z = 0.3
            sphere.color.r = 0.0
            sphere.color.g = 0.8
            sphere.color.b = 0.2
            sphere.color.a = 1.0
            marker_array.markers.append(sphere)

            # number label above the sphere
            text = Marker()
            text.header.frame_id = frame
            text.header.stamp = now
            text.ns = 'waypoints'
            text.id = i * 2 + 1
            text.type = Marker.TEXT_VIEW_FACING
            text.action = Marker.ADD
            text.pose = deepcopy(wp.pose)
            text.pose.position.z += 0.5
            text.scale.z = 0.4
            text.color.r = text.color.g = text.color.b = text.color.a = 1.0
            text.text = str(i + 1)
            marker_array.markers.append(text)

        self.marker_pub.publish(marker_array)


def main():
    rclpy.init()
    node = WaypointManager()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
