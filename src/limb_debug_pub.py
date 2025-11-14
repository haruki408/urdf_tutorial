#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import math, time
import rclpy
from rclpy.node import Node

from std_msgs.msg import Header
from ms_module_msgs.msg import AllJointState, JointState as MsJointState  # JointID等はデフォルトでOK

class LimbDebugPub(Node):
    """
    指定した limb の 4 関節のうち joint_1 を正弦波で動かし、残りは 0。
    /{limb}/joint/out/all_joint_state を publish する。
    """
    def __init__(self):
        super().__init__('limb_debug_pub')
        self.declare_parameter('limb_name', 'limb_n_12')
        self.declare_parameter('hz', 30.0)
        self.declare_parameter('amp', 0.5)      # 振幅[rad]
        self.declare_parameter('omega', 1.0)    # 角速度[rad/s]

        self.limb = self.get_parameter('limb_name').get_parameter_value().string_value
        self.hz = float(self.get_parameter('hz').value)
        self.amp = float(self.get_parameter('amp').value)
        self.omega = float(self.get_parameter('omega').value)

        topic = f'/{self.limb}/joint/out/all_joint_state'
        self.pub = self.create_publisher(AllJointState, topic, 10)
        self.t0 = time.time()

        period = 1.0 / max(1e-3, self.hz)
        self.timer = self.create_timer(period, self._on_timer)
        self.get_logger().info(f'Publish → {topic} (amp={self.amp}, omega={self.omega})')

    def _on_timer(self):
        t = time.time() - self.t0
        pos1 = self.amp * math.sin(self.omega * t)

        msg = AllJointState()
        # 4関節分つくる（bridge は position だけ使う）
        js1 = MsJointState(position=pos1, velocity=0.0, effort=0.0, is_healthy=True)
        js2 = MsJointState(position=pos1, velocity=0.0, effort=0.0, is_healthy=True)
        js3 = MsJointState(position=pos1, velocity=0.0, effort=0.0, is_healthy=True)
        js4 = MsJointState(position=0.0, velocity=0.0, effort=0.0, is_healthy=True)
        # （headerやjoint_idはデフォルトでOK。必要なら js1.header = Header(...) を設定）

        msg.joint_state_list = [js1, js2, js3, js4]
        self.pub.publish(msg)

def main():
    rclpy.init()
    node = LimbDebugPub()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
