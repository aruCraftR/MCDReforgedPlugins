### 注意：此插件处于测试阶段，可能会出现一些问题。如果出现问题，请使用issues报告

## 依赖

### MCDReforged
- 版本>=1.0.0

## 导入API

1.将此API作为插件放到plugins文件夹

2.在需要使用此API的插件中使用`server.get_plugin_instance('socket_api')`获取插件实例

## API

### `SocketServer`与`SocketClient`的区别

`SocketServer`会转发`SocketClient`的信息到指定的其他`SocketClient`(就是个中转站)

`SocketServer`会在连接每个`SocketClient`时都使用单独的线程

`SocketClient`也会在连接时使用单独的线程，但只与服务端进行连接，所以最多只会使用1条线程

### `SocketServer`

#### `SocketServer(mcdr_server: ServerInterface, server_name='SocketServer', dispatch_event_on_executor_thread=True)`

`mcdr_server`: MCDR的ServerInterface实例

`server_name`: SocketServer名称

`dispatch_event_on_executor_thread`: 是否在任务执行者线程上调用事件

#### `start(host='localhost', port=7000, bufsize=1024, max_thread=1)`

`host`: Socket的host

`port`: Socket监听的端口

`bufsize`: socket.recv()方法的bufsize参数，用于限制最大接受的包大小，无特殊情况无需更改

`max_thread`: 最大的连接线程数量，请按照需要连接的客户端数量设置，超出的客户端连接将会进入等待队列

#### `register_event(event_name)`

`event_name`: 需要注册的MCDR事件名称，监听事件时请监听`socket_api.[注册的事件名]`

如果事件已被注册，将会抛出`EventRegisteredError`

触发事件时会传入ServerInterface及对方发送的信息

`my_event(server: ServerInterface, data)`

#### `send_to(target_clients, event, data, source='server_name', signal=None)`

`target_clients`: 要发送到的目标客户端名称，可以传入str或list

`event`: 要在目标客户端上触发的事件名称

`data`: 要传递的消息，可以是str/list/dict

`source`: 来自的客户端/服务器名称，不传此参时自动补全为服务器名称，主要由API内部使用，可直接忽略

`signal`: 要发送的信号，由API内部使用，可直接忽略

#### `send_to_all(event, data, source='server_name', signal=None)`

将信息发送到所有连接的客户端，除`target_clients`外，参数与`send_to()`相同

#### `close(target_client)`

`target_client`: 断开与此客户端的连接

#### `close_all()`

断开与所有客户端的连接

#### `exit()`

关闭socket监听，自动断开所有客户端连接，关闭所有连接线程

插件卸载时请务必调用此方法，否则端口无法释放

### `SocketClient`

#### `SocketClient(mcdr_server: ServerInterface, client_name: str, dispatch_event_on_executor_thread=True)`

实例化与`SocketServer`相同

#### `connect(host='localhost', port=7000, bufsize=1024, reconnection_times=3, reconnection_interval=3)`

`host`: 要连接的服务端地址

`port`: 要连接的服务端所监听的端口

`bufsize`: 同`SocketServer`的`start`中的`bufsize`

`reconnection_times`: 在连接失败时最大的重试次数，如果达到次数仍未连接成功，将会在连接线程中抛出`ConnectionFailedError`

`reconnection_interval`: 每次重试连接的间隔，单位为秒，可传入int或float

#### `register_event(event_name)`

同`SocketServer`的`register_event`

#### `send_to(target_clients, event, data, signal=None)`

除`source`外，同`SocketServer`的`send_to`

#### `send_to_all(event, data, signal=None)`

除`source`外，同`SocketServer`的`send_to_all`

#### `reconnect()`

根据`connect()`的参数重新连接服务端，如果实例化后没有调用过`connect()`，则抛出`SocketError`

#### `exit()`

断开与服务端的连接，关闭连接线程

插件卸载时请务必调用此方法，否则端口无法释放

### API内置方法

下文中`SocketServer`与`SocketClient`统称`SocketAPI`

#### `get_socket_api_instances()`

返回一个字典，格式为{socket_api_instance_id: SocketAPI}

其中socket_api_instance_id是SocketAPI实例的instance_id属性

典型用途：没有调用SocketAPI的exit()就丢失了SocketAPI实例(比如插件重载)，导致端口无法释放，可使用此方法重新获取到SocketAPI实例

#### `get_thread_instances()`

返回一个字典，格式为{thread_instance_id: _SocketThread}

其中socket_thread_id是_SocketThread实例的instance_id属性

主要用于Debug

_SocketThread与普通threading.Thread区别在于有一个kill()方法，可以强制结束自己
