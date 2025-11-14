cmake_minimum_required(VERSION 3.5)
project(urdf_tutorial)

find_package(ament_cmake REQUIRED)

install(
  DIRECTORY images launch meshes rviz urdf xacro stl src config
  DESTINATION share/${PROJECT_NAME}
)

install(PROGRAMS src/model_switcher.py
  src/joint_state_keeper.py
  src/joint_state_bridge.py
  src/limb_debug_pub.py
  src/limb_trajectory_driver.py
  src/limb_goal_publisher.py
  src/limb_sequence_player.py
  DESTINATION lib/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
