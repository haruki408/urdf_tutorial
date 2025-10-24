from launch import LaunchDescription
from launch.substitutions import Command, FindExecutable, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare

def generate_launch_description():
    packages_name = "ms_rviz_urdf"
    xacro_file_name = "4wheel_model.xacro"
    rviz_file_name = "moonshot.rviz"

    # Get URDF via xacro
    robot_description_content = Command(
        [
            PathJoinSubstitution([FindExecutable(name="xacro")]),
            " ",
            PathJoinSubstitution(
                [FindPackageShare(packages_name), "xacro", xacro_file_name]
            ),
        ]
    )
    # xacroコマンドの構築
    robot_description = {"robot_description": ParameterValue(robot_description_content, value_type=str)}
    rviz_config_file = PathJoinSubstitution(
        [FindPackageShare(packages_name), "rviz", rviz_file_name]
    )

    robot_state_pub_node = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        output="both",
        namespace="rviz",
        name="robot_state_publisher_rviz",
        remappings=[('/joint_states', '/target/joint_states')],
        parameters=[robot_description, {"frame_prefix": "rviz/"}],
       # remappings=[('/joint_states', '/rviz/joint_states')],
    )
    # joint_state_pub_gui_node = Node(
    #     package="joint_state_publisher_gui",
    #     executable="joint_state_publisher_gui",
    #     output="screen",
    # )
    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2_wheeldemo",
       # namespace="wheeldemo",
        output="log",
        arguments=["-d", rviz_config_file],
    )
    alljoint2jointstate = Node(
        package="ms_rviz_urdf",
        executable="all_joint_converter",
        namespace="rviz",
        name="all_joint_state_converter",
    )
    static_transfromer=Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='static_transform_publisher_',
            output='screen',
            namespace='rviz',
            arguments=['0', '0', '0', '0', '0', '0', 'body_n_1/target_odom_frame', 'rviz/body_n_1_link']
    )
    nodes = [
        rviz_node,
        robot_state_pub_node,
        #static_transfromer,
        alljoint2jointstate,
       # joint_state_pub_gui_node
        ]

    return LaunchDescription(nodes)
