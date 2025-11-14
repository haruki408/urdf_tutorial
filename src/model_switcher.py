#!/usr/bin/env python3
import os
import subprocess

import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy

from std_msgs.msg import Bool, String, Empty
from rcl_interfaces.srv import SetParameters


class ModelSwitcher(Node):
    """
    /wheel_attach, /gripper_attach (Bool) を受けて xacro を再展開し、
    robot_state_publisher の robot_description を非ブロッキングで更新するノード。

    xacro 側に以下の引数が定義されている想定：
      <xacro:arg name="attach_wheel" default="false"/>
      <xacro:arg name="wheel_mount_frame" default="..."/>

      <xacro:arg name="attach_gripper" default="false"/>
      <xacro:arg name="gripper_mount_frame" default="..."/>
    """

    def __init__(self):
        super().__init__('model_switcher')

        # ---- Parameters ----
        self.declare_parameter('xacro_path', '')
        self.declare_parameter('rsp_node_name', 'robot_state_publisher')
        self.declare_parameter('publish_topic_robot_description', True)

        # 初期状態（必要なら launch から上書き可能）
        self.declare_parameter('attach_wheel_init', False)
        self.declare_parameter('attach_gripper_init', False)

        # 取り付け先フレーム（必要なら launch から上書き）
        self.declare_parameter('wheel_mount_frame', 'palette_link_10')
        self.declare_parameter('gripper_mount_frame', 'body_n_2_limb_n_2_limb_end_effector')

        # 値取得
        self.xacro_path = self.get_parameter('xacro_path').get_parameter_value().string_value
        self.rsp_name   = self.get_parameter('rsp_node_name').get_parameter_value().string_value
        self.pub_topic  = bool(self.get_parameter('publish_topic_robot_description').value)

        self.wheel_mount_frame   = self.get_parameter('wheel_mount_frame').get_parameter_value().string_value
        self.gripper_mount_frame = self.get_parameter('gripper_mount_frame').get_parameter_value().string_value

        self.attach_wheel   = bool(self.get_parameter('attach_wheel_init').value)
        self.attach_gripper = bool(self.get_parameter('attach_gripper_init').value)

        if not self.xacro_path or not os.path.exists(self.xacro_path):
            self.get_logger().error(f'xacro_path が不正です: {self.xacro_path}')

        # robot_state_publisher の set_parameters クライアント
        service_name = f'{self.rsp_name}/set_parameters'.replace('//', '/')
        self.cli = self.create_client(SetParameters, service_name)

        # robot_description をトピックにも流したい場合
        self.desc_pub = None
        if self.pub_topic:
            self.desc_pub = self.create_publisher(
                String, '/robot_description',
                QoSProfile(depth=1,
                           reliability=ReliabilityPolicy.RELIABLE,
                           durability=DurabilityPolicy.TRANSIENT_LOCAL)
            )

        # モデル切替通知（joint bridge の保険用）
        self.switched_pub = self.create_publisher(Empty, '/model_switched', 1)

        # ---- Subscribers ----
        # wheel の着脱（true=付ける、false=外す）
        self.sub_wheel = self.create_subscription(Bool, '/wheel_attach', self.on_wheel_attach, 10)
        # gripper の着脱（true=付ける、false=外す）
        self.sub_grip  = self.create_subscription(Bool, '/gripper_attach', self.on_gripper_attach, 10)

        # 初期適用（service ready 待ち）
        self.wait_elapsed = 0.0
        self.wait_timer = self.create_timer(0.3, self._try_init_once)
        self.get_logger().info(f'waiting for service: {service_name}')

    # -------- 初期 1 回だけ適用 --------
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

    # -------- コールバック：wheel --------
    def on_wheel_attach(self, msg: Bool):
        val = bool(msg.data)
        if val == self.attach_wheel:
            self.get_logger().info(f'attach_wheel は既に {val}')
            return
        self.attach_wheel = val
        if not (self.cli.service_is_ready() or self.cli.wait_for_service(timeout_sec=0.1)):
            self.get_logger().warn(f'service not ready: {self.cli.srv_name}')
            return
        self._apply_xacro()

    # -------- コールバック：gripper --------
    def on_gripper_attach(self, msg: Bool):
        val = bool(msg.data)
        if val == self.attach_gripper:
            self.get_logger().info(f'attach_gripper は既に {val}')
            return
        self.attach_gripper = val
        if not (self.cli.service_is_ready() or self.cli.wait_for_service(timeout_sec=0.1)):
            self.get_logger().warn(f'service not ready: {self.cli.srv_name}')
            return
        self._apply_xacro()

    # -------- 本体：xacro → robot_description 更新 --------
    def _apply_xacro(self):
        try:
            # xacro を両方のフラグ・取り付けフレーム付きで評価
            cmd = [
                'xacro', self.xacro_path,
                f'attach_wheel:={"true" if self.attach_wheel else "false"}',
                f'wheel_mount_frame:={self.wheel_mount_frame}',
                f'attach_gripper:={"true" if self.attach_gripper else "false"}',
                f'gripper_mount_frame:={self.gripper_mount_frame}',
            ]
            urdf_xml = subprocess.check_output(cmd).decode('utf-8')

            # Param を非ブロッキングで更新
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
                        self.get_logger().info(
                            f'robot_description 更新 OK '
                            f'(wheel={self.attach_wheel}@{self.wheel_mount_frame}, '
                            f'gripper={self.attach_gripper}@{self.gripper_mount_frame})'
                        )
                        # 切替通知
                        self.switched_pub.publish(Empty())
                    else:
                        self.get_logger().error('robot_description の更新が失敗ステータスでした')
                except Exception as e:
                    self.get_logger().error(f'set_parameters 応答処理エラー: {e}')

            future.add_done_callback(_on_done)

            # （任意）トピックにも配信
            if self.desc_pub is not None:
                self.desc_pub.publish(String(data=urdf_xml))

        except subprocess.CalledProcessError as e:
            out = e.output.decode('utf-8', errors='ignore') if isinstance(e.output, (bytes, bytearray)) else str(e.output)
            self.get_logger().error(f'xacro 実行エラー（returncode={e.returncode}）: {out}')
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
