import sys
if sys.prefix == '/usr':
    sys.real_prefix = sys.prefix
    sys.prefix = sys.exec_prefix = '/home/kchan/AAPI/farm_simulation/farm_ws/install/farm_rover_sim'
