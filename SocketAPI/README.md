### 注意：此插件处于测试阶段，可能会出现一些问题。如果出现问题，请使用issues报告

## 依赖

### MCDReforged
- 版本>=1.0.0

## 导入API

将此API作为插件放到plugins文件夹，在需要使用此API的插件中使用`server.get_plugin_instance('socket_api')`获取插件实例

## API

### `SocketServer`与`SocketClient`的区别

`SocketServer`会转发`SocketClient`的信息到指定的其他`SocketClient`(就是个中转站)

`SocketServer`会在连接每个`SocketClient`时都使用单独的线程

`SocketClient`也会在连接时使用单独的线程，但只与服务端进行连接，所以最多只会使用1条线程

### `SocketServer`

#### `SocketServer(mcdr_server: ServerInterface, server_name='SocketServer', dispatch_event_on_executor_thread=True)`

`mcdr_server`: MCDR的ServerInterface实例

`server_name`: SocketServer的名称

`dispatch_event_on_executor_thread`: 是否在任务执行者线程上调用注册的事件，如果为False，将在连接线程上调用事件

如果不在任务执行者线程上调用事件，有以下几点注意事项

下次信息接收及处理将在事件执行完毕后进行，这意味着你可以更精确地控制SocketServer实例

如果调用的事件出现阻塞情况，将会直接阻塞连接线程，导致连接线程无法及时接收信息或直接略过信息

如果调用的事件代码抛出任意异常，将会直接导致连接线程关闭

综上所述，除非有特殊需求，请不要设置`dispatch_event_on_executor_thread`为False

#### `start(host='localhost', port=7000, bufsize=1024, max_thread=1)`

`host`: Socket的host

`port`: Socket监听的端口

`bufsize`: socket.recv()方法的bufsize参数，用于限制最大接受的包大小，无特殊情况无需更改

`max_thread`: 最大的连接线程数量，请按照需要连接的客户端数量设置，超出的客户端连接将会进入等待队列

#### `register_event(event_name)`

`event_name`: 需要注册的MCDR事件名称，监听事件时请监听`socket_api.[注册的事件名]`

如果事件已被注册或注册了API内置事件，将会抛出`EventRegisteredError`

触发事件时会传入ServerInterface及对方发送的信息

如：`my_event(server: ServerInterface, data)`

#### `send_to(target_clients, event, data, source='server_name', signal=None)`

`target_clients`: 要发送到的目标客户端名称，可以传入str或list

`event`: 要在目标客户端上触发的事件名称

`data`: 要传递的消息，可以是str/list/dict等可被json序列化的类型

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

完全关闭插件时请务必调用此方法，否则端口无法释放

### `SocketClient`

#### `SocketClient(mcdr_server: ServerInterface, client_name: str, dispatch_event_on_executor_thread=True)`

`mcdr_server`: MCDR的ServerInterface实例

`server_name`: SocketClient的名称

`dispatch_event_on_executor_thread`: 是否在任务执行者线程上调用注册的事件，如果为False，将在连接线程上调用事件

如果不在任务执行者线程上调用事件，有以下几点注意事项

下次信息接收及处理将在事件执行完毕后进行，这意味着你可以更精确地控制SocketClient实例

如果调用的事件出现阻塞情况，将会直接阻塞连接线程，导致连接线程无法及时接收信息或直接略过信息

如果调用的事件代码抛出任意异常，将会直接导致连接线程关闭

综上所述，除非有特殊需求，请不要设置`dispatch_event_on_executor_thread`为False

#### `connect(host='localhost', port=7000, bufsize=1024, reconnection_times=3, reconnection_interval=3)`

`host`: 要连接的服务端地址

`port`: 要连接的服务端所监听的端口

`bufsize`: 同`SocketServer`的`start`中的`bufsize`

`reconnection_times`: 在连接失败时最大的重试次数，如果达到次数仍未连接成功，将会在连接线程中抛出`ConnectionFailedError`

`reconnection_interval`: 每次重试连接的间隔，单位为秒，可传入int或float

#### `register_event(event_name)`

`event_name`: 需要注册的MCDR事件名称，监听事件时请监听`socket_api.[注册的事件名]`

如果事件已被注册或注册了API内置事件，将会抛出`EventRegisteredError`

触发事件时会传入ServerInterface及对方发送的信息

如：`my_event(server: ServerInterface, data)`

#### `send_to(target_clients, event, data, signal=None)`

`target_clients`: 要发送到的目标客户端或服务端名称，可以传入str或list

`event`: 要在目标客户端上触发的事件名称

`data`: 要传递的消息，可以是str/list/dict等可被json序列化的类型

`signal`: 要发送的信号，由API内部使用，可直接忽略

#### `send_to_all(event, data, signal=None)`

将信息发送到所有连接的客户端，包括服务端，除`target_clients`外，参数与`send_to()`相同

#### `reconnect()`

根据`connect()`的参数重新连接服务端，如果实例化后没有调用过`connect()`，则抛出`SocketError`

#### `exit()`

断开与服务端的连接，关闭连接线程

完全关闭插件时请务必调用此方法，否则端口无法释放

### API内置事件

所有内置事件不受`dispatch_event_on_executor_thread`参数影响，总在任务执行者线程上触发

#### `socket_api.on_connected`

在连接成功时触发

对于`SocketServer`，会传入`ServerInterface`，成功连接的客户端名称与地址

如：`on_connected(server: ServerInterface, client_name, client_address)`

对于`SocketClient`，仅传入`ServerInterface`

如：`on_connected(server: ServerInterface)`

#### `socket_api.on_disconnected`

在连接断开时触发

对于`SocketServer`，会传入`ServerInterface`与断开连接的客户端名称

如：`on_disconnected(server: ServerInterface, client_name)`

对于`SocketClient`，仅传入`ServerInterface`

如：`on_disconnected(server: ServerInterface)`

### API内置方法

因为`SocketServer`与`SocketClient`共用同一instance_id计数器

所以下文中`SocketServer`与`SocketClient`统称`SocketAPI`

#### `get_socket_api_instance(socket_api_instance_id)`

返回指定的`SocketAPI`实例

其中`socket_api_instance_id`是`SocketAPI`实例的`instance_id`属性

没有调用`exit()`就丢失了`SocketAPI`实例(比如插件重载)，导致端口无法释放，可提前获取`instance_id`并存储来防止此类问题

_一般用于开发期间，正常情况下在`on_load`事件中使用`prev_plugin_module`继承`SocketAPI`实例即可_

#### `get_thread_instance(thread_instance_id)`

返回指定的`_SocketThread`实例

其中`thread_instance_id`是`_SocketThread`实例的`instance_id`属性

主要用于Debug

`_SocketThread`与普通`threading.Thread`的主要区别在于新增一个`kill()`方法，可以强制结束自己
