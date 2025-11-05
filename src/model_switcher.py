#!/usr/bin/env python3
import os
import subprocess

import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from std_msgs.msg import Bool, String
from rcl_interfaces.srv import SetParameters
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy


class ModelSwitcher(Node):
    """
    /wheel_attach (Bool) を受けて xacro を再展開し、
    robot_state_publisher の robot_description を非ブロッキングで更新。
    xacro 側は:
      <xacro:arg name="attach_wheel" default="false"/>
      <xacro:arg name="wheel_mount_frame" default="..."/>
    を想定。
    """

    def __init__(self):
        super().__init__('model_switcher')

        # --- params ---
        self.declare_parameter('xacro_path', '')
        self.declare_parameter('rsp_node_name', 'robot_state_publisher')
        self.declare_parameter('publish_topic_robot_description', True)
        self.declare_parameter('wheel_mount_frame', 'limb_n_14_link_1')  # ←必要に応じて上書き

        self.xacro_path = self.get_parameter('xacro_path').get_parameter_value().string_value
        self.rsp_name   = self.get_parameter('rsp_node_name').get_parameter_value().string_value
        self.pub_topic  = bool(self.get_parameter('publish_topic_robot_description').value)
        self.mount_frame = self.get_parameter('wheel_mount_frame').get_parameter_value().string_value

        if not self.xacro_path or not os.path.exists(self.xacro_path):
            self.get_logger().error(f'xacro_path が不正です: {self.xacro_path}')

        service_name = f'{self.rsp_name}/set_parameters'.replace('//', '/')
        self.cli = self.create_client(SetParameters, service_name)

        self.desc_pub = None
        if self.pub_topic:
            self.desc_pub = self.create_publisher(
                String, '/robot_description',
                QoSProfile(depth=1,
                           reliability=ReliabilityPolicy.RELIABLE,
                           durability=DurabilityPolicy.TRANSIENT_LOCAL)
            )

        # attach_wheel の現在値
        self.attach_wheel = True  # デフォルト値
        # ★ /wheel_attach を購読（true=付ける / false=外す）
        self.sub_attach = self.create_subscription(Bool, '/wheel_attach', self.on_attach, 10)

        # 初期適用
        self.wait_elapsed = 0.0
        self.wait_timer = self.create_timer(0.3, self._try_init_once)
        self.get_logger().info(f'waiting for service: {service_name}')

    def _try_init_once(self):
        if self.cli.service_is_ready() or self.cli.wait_for_service(timeout_sec=0.3):
            self.wait_timer.cancel()
            self.get_logger().info(f'service ready: {self.cli.srv_name}')
            self._apply_xacro()
            return
        self.wait_elapsed += 0.3
        if self.wait_elapsed >= 10.0:
            self.wait_timer.cancel()
            names = [n.name for n in self.get_service_names_and_types() if n.name.endswith('set_parameters')]
            self.get_logger().error(f'サービスが見つかりません: {self.cli.srv_name} candidates={names}')

    def on_attach(self, msg: Bool):
        val = bool(msg.data)
        if val == self.attach_wheel:
            self.get_logger().info(f'attach_wheel は既に {val}')
            return
        self.attach_wheel = val
        if not (self.cli.service_is_ready() or self.cli.wait_for_service(timeout_sec=0.1)):
            self.get_logger().warn(f'service not ready: {self.cli.srv_name}')
            return
        self._apply_xacro()

    def _apply_xacro(self):
        try:
            cmd = [
                'xacro', self.xacro_path,
                f'attach_wheel:={"true" if self.attach_wheel else "false"}',
                f'wheel_mount_frame:={self.mount_frame}',
            ]
            urdf_xml = subprocess.check_output(cmd).decode('utf-8')

            # パラメータ更新（非ブロッキング）
            param_msg = Parameter(
                name='robot_description',
                type_=Parameter.Type.STRING,
                value=urdf_xml
            ).to_parameter_msg()
            req = SetParameters.Request()
            req.parameters = [param_msg]
            future = self.cli.call_async(req)

            def _on_done(fut):
                try:
                    res = fut.result()
                    if res is None:
                        self.get_logger().error('set_parameters 応答 None（タイムアウト/通信失敗）')
                        return
                    if any(r.successful for r in res.results):
                        self.get_logger().info(f'robot_description を更新 attach_wheel={self.attach_wheel}, mount={self.mount_frame}')
                    else:
                        self.get_logger().error('robot_description の更新が失敗ステータスでした')
                except Exception as e:
                    self.get_logger().error(f'set_parameters 応答処理エラー: {e}')

            future.add_done_callback(_on_done)

            if self.desc_pub is not None:
                self.desc_pub.publish(String(data=urdf_xml))

        except subprocess.CalledProcessError as e:
            self.get_logger().error(f'xacro 実行エラー（returncode={e.returncode}）: {e.output}')
        except Exception as e:
            self.get_logger().error(f'xacro適用エラー: {e}')


def main():
    rclpy.init()
    node = ModelSwitcher()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
