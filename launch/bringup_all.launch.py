from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, Command, FindExecutable
from launch_ros.actions import Node, PushRosNamespace
from launch_ros.substitutions import FindPackageShare
from launch_ros.parameter_descriptions import ParameterValue

def limb_group(ns, limb_name, hz, speed):
    return GroupAction([
        PushRosNamespace(ns),
        Node(
            package='urdf_tutorial', executable='limb_trajectory_driver.py',
            name='limb_driver', output='screen',
            parameters=[{'limb_name': limb_name, 'hz': hz, 'speed': speed}]
        ),
    ])

def generate_launch_description():
    pkg = FindPackageShare('urdf_tutorial')
    xacro_rel = LaunchConfiguration('xacro_rel', default='xacro/palette.xacro')
    xacro_path = PathJoinSubstitution([pkg, xacro_rel])
    rviz_config = PathJoinSubstitution([pkg, 'rviz', 'urdf.rviz'])

    robot_description = ParameterValue(
        Command([FindExecutable(name='xacro'), ' ', xacro_path, ' ', 'attach_wheel:=true']),
        value_type=str
    )

    # 共通パラメータ
    hz = LaunchConfiguration('hz', default='30.0')
    speed = LaunchConfiguration('speed', default='0.6')

    return LaunchDescription([
        DeclareLaunchArgument('xacro_rel', default_value='xacro/palette.xacro'),
        DeclareLaunchArgument('hz', default_value='30.0'),
        DeclareLaunchArgument('speed', default_value='0.6'),

        # RSP
        Node(package='robot_state_publisher', executable='robot_state_publisher',
             name='robot_state_publisher', parameters=[{'robot_description': robot_description}]),

        # Bridge（URDFの4関節名と一致する /<ns>/joint/out/all_joint_state を購読）
        Node(package='urdf_tutorial', executable='joint_state_bridge.py',
             name='joint_state_bridge', output='screen',
             parameters=[{
                 'limb_names': 'limb_n_12,limb_n_13,limb_n_14,body_n_2_limb_n_2',
                 'topic_template': '/{limb}/joint/out/all_joint_state',
                 'publish_rate_hz': 30.0,
                 'qos_reliability': 'reliable',
             }]),

        # モデル切替
        Node(package='urdf_tutorial', executable='model_switcher.py',
             name='model_switcher', output='screen',
             parameters=[{'xacro_path': xacro_path, 'rsp_node_name': 'robot_state_publisher'}]),

        # RViz
        Node(package='rviz2', executable='rviz2', name='rviz',
             arguments=['-d', rviz_config], output='screen'),

        # 各 limb のドライバ（名前空間 = URDF の limb 名）
        limb_group('limb_n_12', 'limb_n_12', hz, speed),
        limb_group('limb_n_13', 'limb_n_13', hz, speed),
        limb_group('limb_n_14', 'limb_n_14', hz, speed),
        limb_group('body_n_2_limb_n_2', 'body_n_2_limb_n_2', hz, speed),
    ])
