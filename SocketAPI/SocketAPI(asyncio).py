from ctypes import c_long, py_object, pythonapi
from json import dumps, loads
from threading import Thread
from asyncio import start_server as asyncio_start_server, open_connection as asyncio_open_connection, run as asyncio_run, sleep as asyncio_sleep
from socket import SO_REUSEADDR, SOL_SOCKET

from mcdreforged.api.event import LiteralEvent

PLUGIN_METADATA = {
    'id': 'socket_api',
    'version': '2.0.0-pre1',
    'name': 'SocketAPI',
    'description': '在多个MCDR之间使用Socket通信的API库',
    'author': 'noeru_desu',
    'link': 'https://github.com/noeru-desu/MCDReforgedPlugins/tree/main/SocketAPI'
}


socket_api_instances = {}
thread_instances = {}
socket_api_instance_id = 0
thread_instance_id = 0
JSON_SEPARATORS = (',', ':')
STREAM_SEPARATOR = b"\xFF\xFF"
ON_CONNECTED_EVENT = LiteralEvent('{}.on_connected'.format(PLUGIN_METADATA['id']))
ON_DISCONNECTED_EVENT = LiteralEvent('{}.on_disconnected'.format(PLUGIN_METADATA['id']))
mcdr_server = None


def on_load(server, prev_module):
    global mcdr_server, socket_api_instances, thread_instances, socket_api_instance_id, thread_instance_id
    mcdr_server = server
    if prev_module is not None:
        socket_api_instances = prev_module.socket_api_instances
        thread_instances = prev_module.thread_instances
        socket_api_instance_id = prev_module.socket_api_instance_id
        thread_instance_id = prev_module.thread_instance_id


def _storage_socket_api_instance(socket_api) -> int:
    global socket_api_instance_id
    socket_api_instance_id += 1
    if len(socket_api_instances) >= 20:
        del socket_api_instances[list(socket_api_instances.keys())[0]]
    socket_api_instances[socket_api_instance_id] = socket_api
    return socket_api_instance_id


def _storage_thread_instance(thread) -> int:
    global thread_instance_id
    thread_instance_id += 1
    thread_instances[thread_instance_id] = thread
    return thread_instance_id


def _del_thread_instance(instance_id):
    del thread_instances[instance_id]


def get_socket_api_instance(socket_api_instance_id):
    return socket_api_instances[socket_api_instance_id] if socket_api_instance_id in socket_api_instances else None


def get_thread_instance(thread_instance_id):
    return thread_instances[thread_instance_id] if thread_instance_id in thread_instances else None


class SocketError(Exception):
    pass


class EventRegisteredError(SocketError):
    pass


class ConnectionFailedError(SocketError):
    pass


class _asyncioThread(Thread):
    def __init__(self, method, error_callback):
        super().__init__()
        self.__instance_id = _storage_thread_instance(self)
        self.setDaemon(True)
        self.__method = method
        self.__error_callback = error_callback
        self.__started = False
        self.start()

    @property
    def instance_id(self):
        return self.__instance_id

    def run(self):
        self.__started = True
        try:
            asyncio_run(self.__method())
        except Exception as e:
            asyncio_run(self.__error_callback(e))
        _del_thread_instance(self.instance_id)
        self.__started = False

    def kill(self):
        if not self.__started:
            return
        res = pythonapi.PyThreadState_SetAsyncExc(c_long(self.ident), py_object(SystemExit))
        if res != 1 and res != 0:
            pythonapi.PyThreadState_SetAsyncExc(self.ident, None)
        _del_thread_instance(self.instance_id)
        self.__started = False


async def _send(writer, data):
    writer.write(data + STREAM_SEPARATOR)
    await writer.drain()


async def _recv(reader):
    recv = await reader.readuntil(STREAM_SEPARATOR)
    return loads(recv.removesuffix(STREAM_SEPARATOR))


class SocketServer:
    def __init__(self, server_name='SocketServer', dispatch_event_on_executor_thread=True):
        self.__instance_id = _storage_socket_api_instance(self)
        self.__server = None
        self.__mcdr_server = mcdr_server
        self.__name = server_name
        self.__on_executor_thread = dispatch_event_on_executor_thread
        self.__events = {}
        self.__conns = {}

    @property
    def instance_id(self):
        return self.__instance_id

    @property
    def name(self):
        return self.__name

    def start(self, host='0.0.0.0', port=7000):
        if self.__server is not None:
            raise SocketError('Socket has been started.')
        self.host = host
        self.port = port
        if self.__server is None:
            self.__server_thread = _asyncioThread(self.__run_asyncio, self.__thread_error)

    def register_event(self, event_name):
        if event_name in ['on_connected', 'on_disconnected']:
            raise EventRegisteredError(f'Event {event_name} is an internal event.')
        elif event_name in self.__events:
            raise EventRegisteredError(f'Event {event_name} has been registered')
        self.__events[event_name] = LiteralEvent('{}.{}'.format(PLUGIN_METADATA['id'], event_name))
        return list(self.__events.keys())

    def send_to(self, target_clients: str or list, event, data, source='server_name', signal=None):
        self.__check_status()
        if not self.__conns:
            raise SocketError('Not connected to the client.')
        asyncio_run(self._async_send_to(target_clients, event, data, source, signal))

    def send_to_all(self, event, data, source='server_name', signal=None):
        self.__check_status()
        if not self.__conns:
            raise SocketError('Not connected to the client.')
        asyncio_run(self._async_send_to_all(event, data, source, signal))

    def close(self, target_client):
        self.__check_status()
        if target_client not in self.__conns:
            raise SocketError('No connection from client ' + target_client)
        asyncio_run(self._async_close(target_client))

    def close_all(self):
        self.__check_status()
        asyncio_run(self._async_close_all())

    def exit(self):
        asyncio_run(self._async_exit())

    async def _async_send_to(self, target_clients, event, data, source='server_name', signal=None):
        self.__check_status()
        if not self.__conns:
            raise SocketError('Not connected to the client.')
        if not isinstance(target_clients, list):
            target_clients = [target_clients]
        source = source if not source == 'server_name' else self.__name
        if signal is not None:
            json = {'source': source, 'signal': signal, 'event': event, 'data': data}
        else:
            json = {'source': source, 'event': event, 'data': data}
        byt = dumps(json, separators=JSON_SEPARATORS).encode('utf-8')
        errors = []
        try:
            for n in target_clients:
                if n not in self.__conns:
                    continue
                r, w = self.__conns[n]
                await _send(w, byt)
        except Exception as e:
            errors.append(e)
        return errors if errors else None

    async def _async_send_to_all(self, event, data, source='server_name', signal=None):
        self.__check_status()
        if not self.__conns:
            raise SocketError('Not connected to the client.')
        source = source if not source == 'server_name' else self.__name
        if signal is not None:
            json = {'source': source, 'signal': signal, 'event': event, 'data': data}
        else:
            json = {'source': source, 'event': event, 'data': data}
        byt = dumps(json, separators=JSON_SEPARATORS).encode('utf-8')
        errors = []
        for r, w in self.__conns.values():
            try:
                await _send(w, byt)
            except Exception as e:
                errors.append(e)
        return errors if errors else None

    async def _async_close(self, target_client):
        self.__check_status()
        if target_client not in self.__conns:
            raise SocketError('No connection from client ' + target_client)
        await self._async_send_to(target_client, None, None, signal='close')
        await self.__close(self.__conns[target_client][1])
        del self.__conns[target_client]
        self.__mcdr_server.dispatch_event(ON_DISCONNECTED_EVENT, (target_client,))

    async def _async_close_all(self):
        self.__check_status()
        try:
            await self._async_send_to_all(None, None, signal='close')
        except SocketError:
            pass
        for n, c in self.__conns.items():
            await self.__close(c[1])
            self.__mcdr_server.dispatch_event(ON_DISCONNECTED_EVENT, (n,))
        self.__conns.clear()

    async def _async_exit(self):
        self.__check_status()
        if not self.__server.is_serving():
            self.__server_thread.kill()
            return
        await self._async_close_all()
        await self.__close(self.__server)
        self.__server_thread.kill()

    async def __run_asyncio(self):
        self.__server_thread.setName(f'{self.__name}[asyncio thread]')
        self.__server = await asyncio_start_server(self.__connection, self.host, self.port)
        self.__server.sockets[0].setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        addr = self.__server.sockets[0].getsockname()
        self.__mcdr_server.logger.info(f'已在{addr[0]}:{addr[1]}上启动Socket服务端[{self.name}]')
        async with self.__server:
            await self.__server.serve_forever()

    async def __connection(self, reader, writer):
        client_name = await self.__on_connected(reader, writer)
        while True:
            try:
                recv_json = await _recv(reader)
            except Exception:
                await self.close(client_name)
                break
            target_clients = await self.__format_target_clients_list(client_name, recv_json)
            await self.__forward(client_name, target_clients, recv_json)

    async def __on_connected(self, reader, writer):
        client_flags = await _recv(reader)
        client_name = client_flags['name']
        self.__conns[client_name] = (reader, writer)
        addr = writer.get_extra_info('peername')
        self.__mcdr_server.logger.info(f'客户端{client_name}[{addr[0]}:{addr[1]}]已建立连接')
        self.__mcdr_server.dispatch_event(ON_CONNECTED_EVENT, (client_name, addr))
        return client_name

    def __check_status(self):
        if self.__server is None:
            raise SocketError('Socket is not started.')

    async def __format_target_clients_list(self, client_name, recv_json):
        target_clients = recv_json['target_clients']
        if target_clients == '##all##':
            target_clients = list(self.__conns.keys())
            target_clients.append(self.__name)
        if client_name in target_clients:
            target_clients.remove(client_name)
        if self.__name in target_clients or '#SocketServer' in target_clients:
            await self.__check_signal(client_name, recv_json)
            self.__dispatch_event(recv_json)
            target_clients.remove(self.__name)
        return target_clients

    async def __check_signal(self, name, data):
        if 'signal' in data:
            signal = data['signal']
            if signal == 'client_close':
                await self.__close(self.__conns[name][1])
                del self.__conns[name]

    def __dispatch_event(self, data):
        if data['event'] in self.__events:
            self.__mcdr_server.dispatch_event(self.__events[data['event']], (data['data'],), on_executor_thread=self.__on_executor_thread)

    async def __forward(self, name, target_clients, data):
        if not target_clients:
            return
        if 'signal' in data:
            await self._async_send_to(target_clients, data['event'], data['data'], name, data['signal'])
        else:
            await self._async_send_to(target_clients, data['event'], data['data'], name)

    async def __close(self, writer):
        writer.close()
        await writer.wait_closed()

    async def __thread_error(self, error):
        self.__mcdr_server.logger.error(f'线程：{self.__server_thread.name}出现错误：{str(error)}')
        if self.__server is not None:
            await self.__close(self.__server)


class SocketClient:
    def __init__(self, client_name: str, dispatch_event_on_executor_thread=True):
        self.__instance_id = _storage_socket_api_instance(self)
        self.host = None
        self.__mcdr_server = mcdr_server
        self.__name = client_name
        self.__on_executor_thread = dispatch_event_on_executor_thread
        self.__events = {}
        self.__connected = False
        self.__client_thread = None

    @property
    def instance_id(self):
        return self.__instance_id

    @property
    def name(self):
        return self.__name

    def connect(self, host='localhost', port=7000, bufsize=1024, reconnection_times=3, reconnection_interval=3):
        if self.__connected:
            raise SocketError('Already connected to the server.')
        elif self.__client_thread is not None:
            raise SocketError('Trying to connect to the server.')
        self.host = host
        self.port = port
        self.bufsize = bufsize
        self.__reconnection_times = reconnection_times if reconnection_times >= 0 else 0
        self.__reconnection_interval = reconnection_interval if reconnection_times >= 0 else 0
        self.__client_thread = _asyncioThread(self.__connect, self.__thread_error)

    def register_event(self, event_name):
        if event_name in ['on_connected', 'on_disconnected']:
            raise EventRegisteredError(f'Event {event_name} is an internal event.')
        elif event_name in self.__events:
            raise EventRegisteredError(f'Event {event_name} has been registered')
        self.__events[event_name] = LiteralEvent('{}.{}'.format(PLUGIN_METADATA['id'], event_name))

    def send_to(self, target_clients: str or list, event, data, signal=None):
        if not self.__connected:
            raise SocketError('Not connected to the server.')
        asyncio_run(self._async_send_to(target_clients, event, data, signal))

    def send_to_all(self, event, data, signal=None):
        if not self.__connected:
            raise SocketError('Not connected to the server.')
        asyncio_run(self._async_send_to_all(event, data, signal))

    def reconnect(self):
        if self.host is None:
            raise SocketError('Need to call connect() first.')
        asyncio_run(self._async_reconnect())

    def exit(self):
        asyncio_run(self._async_exit())

    async def _async_send_to(self, target_clients: str or list, event, data, signal=None):
        if not self.__connected:
            raise SocketError('Not connected to the server.')
        if not isinstance(target_clients, list):
            target_clients = [target_clients]
        if signal is not None:
            json = {'target_clients': target_clients, 'event': event, 'data': data, 'signal': signal}
        else:
            json = {'target_clients': target_clients, 'event': event, 'data': data}
        byt = dumps(json, separators=JSON_SEPARATORS).encode('utf-8')
        await _send(self.__writer, byt)

    async def _async_send_to_all(self, event, data, signal=None):
        if not self.__connected:
            raise SocketError('Not connected to the server.')
        if signal is not None:
            json = {'target_clients': '##all##', 'event': event, 'data': data, 'signal': signal}
        else:
            json = {'target_clients': '##all##', 'event': event, 'data': data}
        byt = dumps(json, separators=JSON_SEPARATORS).encode('utf-8')
        await _send(self.__writer, byt)

    async def _async_reconnect(self):
        await self._async_exit()
        self.__client_thread = _asyncioThread(self.__connect, self.__thread_error)

    async def _async_exit(self):
        if not self.__connected:
            if self.__client_thread is not None:
                self.__client_thread.kill()
            return
        self.__connected = False
        try:
            await self._async_send_to(['#SocketServer'], None, None, 'client_close')
        except SocketError:
            pass
        await self.__close()
        if self.__client_thread is not None:
            self.__client_thread.kill()
        self.__mcdr_server.dispatch_event(ON_DISCONNECTED_EVENT, ())    

    async def __connect(self):
        self.__client_thread.setName(f'{self.__name}[asyncio thread]')
        retry_times = 0
        while retry_times <= self.__reconnection_times:
            self.__client_thread.setName(f'{self.__name}[Connecting]')
            try:
                self.__reader, self.__writer = await asyncio_open_connection(self.host, self.port)
            except Exception as e:
                self.__mcdr_server.logger.info('连接失败：' + str(e))
                await asyncio_sleep(self.__reconnection_interval)
                retry_times += 1
                continue
            else:
                break
        if retry_times > self.__reconnection_times:
            raise ConnectionFailedError('Connection failure times exceed the upper limit.')
        self.__writer.get_extra_info('socket').setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        await self.__on_connected()
        await self.__connection()

    async def __connection(self):
        while True:
            try:
                recv_json = await _recv(self.__reader)
            except Exception:
                break
            if 'signal' in recv_json:
                if recv_json['signal'] == 'close':
                    break
            self.__dispatch_event(recv_json)

    async def __on_connected(self):
        self.__connected = True
        await _send(self.__writer, dumps({'name': self.__name}, separators=JSON_SEPARATORS).encode('utf-8'))
        self.__mcdr_server.logger.info(f'{self.name}已与服务端建立连接')
        self.__mcdr_server.dispatch_event(ON_CONNECTED_EVENT, ())

    def __dispatch_event(self, data):
        if data['event'] in self.__events:
            self.__mcdr_server.dispatch_event(self.__events[data['event']], (data['data'],), on_executor_thread=self.__on_executor_thread)

    async def __close(self):
        self.__writer.close()
        await self.__writer.wait_closed()

    async def __thread_error(self, error):
        if isinstance(error, ConnectionFailedError):
            return
        self.__mcdr_server.logger.error(f'线程：{self.__client_thread.name}出现错误：{str(error)}')
        self.__client_thread = None
        await self._async_exit()
