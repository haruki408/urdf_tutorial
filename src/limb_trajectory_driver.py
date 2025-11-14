#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import math, time
from typing import List
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

from std_msgs.msg import Float64MultiArray
from ms_module_msgs.msg import AllJointState, JointState as MsJointState, JointID

class LimbTrajectoryDriver(Node):
    """
    <namespace>/goal (Float64MultiArray, 長さ4 [rad]) を受け取り、
    <namespace>/joint/out/all_joint_state (ms_module_msgs/AllJointState) を hz で出す。
    速度 [rad/s] でリミット追従（台形ではなく単純な線形追従）。
    """
    def __init__(self):
        super().__init__('limb_trajectory_driver')

        self.declare_parameter('limb_name', 'limb_n_12')   # ログ用
        self.declare_parameter('hz', 30.0)
        self.declare_parameter('speed', 0.6)               # 1関節の最大追従速度 [rad/s]
        self.limb_name = self.get_parameter('limb_name').get_parameter_value().string_value
        self.hz = float(self.get_parameter('hz').value)
        self.speed = float(self.get_parameter('speed').value)

        qos = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=10,
                         reliability=ReliabilityPolicy.RELIABLE)

        # 入出力トピック（※名前空間に乗る）
        self.pub = self.create_publisher(AllJointState, 'joint/out/all_joint_state', qos)
        self.sub = self.create_subscription(Float64MultiArray, 'goal', self.on_goal, qos)

        # 内部状態
        self.curr = [0.0, 0.0, 0.0, 0.0]
        self.goal = [0.0, 0.0, 0.0, 0.0]

        self.dt = 1.0 / max(1e-3, self.hz)
        self.timer = self.create_timer(self.dt, self.on_tick)
        self.get_logger().info(f'LimbTrajectoryDriver up: ns={self.get_namespace()} limb={self.limb_name} hz={self.hz} speed={self.speed}')

    def on_goal(self, msg: Float64MultiArray):
        data = list(msg.data)
        if len(data) != 4:
            self.get_logger().warn(f'goal size {len(data)} != 4, ignored')
            return
        self.goal = data
        self.get_logger().info(f'goal set -> {self.goal}')

    def on_tick(self):
        # 単純な速度制限付き追従
        max_step = self.speed * self.dt
        new = []
        for c, g in zip(self.curr, self.goal):
            diff = g - c
            if abs(diff) <= max_step:
                new.append(g)
            else:
                new.append(c + math.copysign(max_step, diff))
        self.curr = new

        # AllJointState に変換して publish
        out = AllJointState()
        out.joint_state_list = []
        for i, pos in enumerate(self.curr, start=1):
            js = MsJointState()
            js.joint_id = JointID()  # id を使わないなら空でOK
            js.position = float(pos)
            js.velocity = 0.0
            js.effort = 0.0
            js.is_healthy = True
            js.error_str = ""
            out.joint_state_list.append(js)

        self.pub.publish(out)

def main():
    rclpy.init()
    rclpy.spin(LimbTrajectoryDriver())
    rclpy.shutdown()

if __name__ == '__main__':
    main()
