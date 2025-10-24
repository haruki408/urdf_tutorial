from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch.substitutions import Command

def generate_launch_description():
    pkg = FindPackageShare('urdf_tutorial')
    xacro_rel = LaunchConfiguration('xacro_rel', default='xacro/model_toggle.xacro')
    xacro_path = PathJoinSubstitution([pkg, xacro_rel])

    return LaunchDescription([
        DeclareLaunchArgument('xacro_rel', default_value='xacro/model_toggle.xacro',
                              description='urdf_tutorial share からの相対パス'),
        # まずは use_alt=false で起動（初期モデル）
        Node(package='robot_state_publisher',
             executable='robot_state_publisher',
             name='robot_state_publisher',
             parameters=[{'robot_description': Command(['xacro ', xacro_path, ' use_alt:=false'])}]),
        Node(package='joint_state_publisher_gui',
             executable='joint_state_publisher_gui'),
        Node(package='rviz2', executable='rviz2', output='screen'),
        # /modelchange を受けて robot_description を差し替える
        Node(package='urdf_tutorial',
             executable='model_switcher.py',
             name='model_switcher',
             output='screen',
             parameters=[{'xacro_path': xacro_path,
                          'rsp_node_name': 'robot_state_publisher'}]),
    ])
