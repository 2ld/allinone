### 脚本介绍

allinone共分为两个脚本，一个是`allinone.py`，另一个是`operate.py`。`allinone.py`负责创建allinone虚机，主要供fuel部署时使，不对cloud进行公开，`operate.py`负责启停allinone虚机，主要供cloud使用，管理虚机。`operate.py`脚本执行时，必须输入参数，`--start-vm`或者`--stopv-vm`，二者对应的操作分别是启动和关闭，同时启动虚机时，会设置该虚机为开机（宿主机）自启动，关闭虚拟机时，会关闭该虚机的开机自启动。

### 日志文件

日志文件的位置：`/var/log/allinone.log`

### 错误码

code  |  message
--- | --- 
1000 | This operation was successful
1001 | Sorry, libvirt failed to open a connection to the hypervisor software
1002 | The specified vm is not present
1003 | Libvirt failed to start vm
1004 | Libvirt faild to stop vm
1005 | The vm is already running
