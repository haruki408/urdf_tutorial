# 文件名: urdf_tutorial/launch/display_dynamic_real.launch.py

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import (
    LaunchConfiguration,
    PathJoinSubstitution,
    Command,
    FindExecutable,
)
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    # パッケージパス
    pkg = FindPackageShare('urdf_tutorial')

    # Xacro の相対パス（必要なら引数で差し替え）
    xacro_rel = LaunchConfiguration('xacro_rel', default='xacro/palette.xacro')
    xacro_path = PathJoinSubstitution([pkg, xacro_rel])

    # RViz の設定
    rviz_config = PathJoinSubstitution([pkg, 'rviz', 'urdf.rviz'])

    # ===== 引数（初期状態と取付け先） =====
    attach_wheel       = LaunchConfiguration('attach_wheel')
    attach_gripper     = LaunchConfiguration('attach_gripper')
    wheel_mount_frame  = LaunchConfiguration('wheel_mount_frame')
    gripper_mount_frame= LaunchConfiguration('gripper_mount_frame')

    # xacro を実行して URDF 文字列を生成（ParameterValueで明示的にstrとして渡す）
    robot_description = ParameterValue(
        Command([
            FindExecutable(name='xacro'),
            ' ', xacro_path, ' ',
            'attach_wheel:=', attach_wheel, ' ',
            'wheel_mount_frame:=', wheel_mount_frame, ' ',
            'attach_gripper:=', attach_gripper, ' ',
            'gripper_mount_frame:=', gripper_mount_frame,
        ]),
        value_type=str
    )

    return LaunchDescription([
        # ===== Launch 引数 =====
        DeclareLaunchArgument(
            'xacro_rel',
            default_value='xacro/palette.xacro',
            description='urdf_tutorial/share からの相対パス'
        ),
        DeclareLaunchArgument(
            'attach_wheel',
            default_value='false',
            description='初期状態で wheel を取り付けるか（true/false）'
        ),
        DeclareLaunchArgument(
            'wheel_mount_frame',
            default_value='palette_link_10',
            description='wheel の取付ベースフレーム名'
        ),
        DeclareLaunchArgument(
            'attach_gripper',
            default_value='false',
            description='初期状態で gripper を取り付けるか（true/false）'
        ),
        DeclareLaunchArgument(
            'gripper_mount_frame',
            default_value='body_n_2_limb_n_2_limb_end_effector',
            description='gripper の取付ベースフレーム名'
        ),

        # ===== robot_state_publisher =====
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{'robot_description': robot_description}],
        ),

        # ===== 実機 AllJointState → /joint_states ブリッジ =====
        Node(
            package='urdf_tutorial',
            executable='joint_state_bridge.py',
            name='joint_state_bridge',
            output='screen',
            parameters=[{
                # CSV 文字列で渡す（Humble の STRING_ARRAY 回避）
                'limb_names': 'limb_n_12,limb_n_13,limb_n_14,body_n_2_limb_n_2',
                'topic_template': '/{limb}/joint/out/all_joint_state',
                'publish_rate_hz': 30.0,
                # 'qos_reliability': 'reliable',  # 必要なら best_effort に変更可
            }],
        ),

        # ===== /wheel_attach /gripper_attach で URDF を動的切替 =====
        Node(
            package='urdf_tutorial',
            executable='model_switcher.py',
            name='model_switcher',
            output='screen',
            parameters=[{
                'xacro_path': xacro_path,                   # Substitution のままでOK
                'rsp_node_name': 'robot_state_publisher',
                'publish_topic_robot_description': True,

                # 初期状態（launch引数と一致させる）
                'attach_wheel_init': attach_wheel,
                'attach_gripper_init': attach_gripper,

                # 取付けフレーム（launch引数と一致させる）
                'wheel_mount_frame': wheel_mount_frame,
                'gripper_mount_frame': gripper_mount_frame,
            }],
        ),

        # ===== RViz =====
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz',
            output='screen',
            arguments=['-d', rviz_config],
        ),

        # joint_state_publisher_gui は使わない（実機の角度を bridge が出す）
    ])
