from ctypes import c_long, py_object, pythonapi
from json import dumps, loads
from socket import AF_INET, SO_REUSEADDR, SOCK_STREAM, SOL_SOCKET, socket
from threading import Thread
# from threading import enumerate as threading_enumerate
from time import sleep

from mcdreforged.api.event import LiteralEvent
from mcdreforged.api.types import ServerInterface

PLUGIN_METADATA = {
    'id': 'socket_api',
    'version': '1.0.0',
    'name': 'SocketAPI',
    'description': '在多个MCDR之间使用Socket通信的API库',
    'author': 'noeru_desu',
    'link': 'https://github.com/noeru-desu/MCDReforgedPlugins/tree/main/SocketAPI'
}


separators = (',', ':')
socket_api_instances = {}
thread_instances = {}
socket_api_instance_id = 0
thread_instance_id = 0


def on_load(server, prev_module):
    global socket_api_instances, thread_instances, socket_api_instance_id, thread_instance_id
    if prev_module is not None:
        socket_api_instances = prev_module.socket_api_instances
        thread_instances = prev_module.thread_instances
        socket_api_instance_id = prev_module.socket_api_instance_id
        thread_instance_id = prev_module.thread_instance_id


def _storage_socket_api_instances(socket_api, instance_id=None) -> int:
    global socket_api_instance_id
    if instance_id is None:
        socket_api_instance_id += 1
        socket_api_instances[socket_api_instance_id] = socket_api
        return socket_api_instance_id
    else:
        socket_api_instances[instance_id] = socket_api
        return instance_id


def _storage_thread_instances(thread) -> int:
    global thread_instance_id
    thread_instance_id += 1
    thread_instances[thread_instance_id] = thread
    return thread_instance_id


def _del_socket_api_instances(instance_id):
    del socket_api_instances[instance_id]


def _del_thread_instances(instance_id):
    del thread_instances[instance_id]


def get_socket_api_instances() -> dict:
    return socket_api_instances


def get_thread_instances() -> dict:
    return thread_instances


class SocketError(Exception):
    pass


class EventRegisteredError(SocketError):
    pass


class ConnectionFailedError(SocketError):
    pass


class _SocketThread(Thread):
    def __init__(self, method, error_callback):
        super().__init__()
        self.__instance_id = _storage_thread_instances(self)
        self.setDaemon(True)
        self.__method = method
        self.__error_callback = error_callback
        self.__started = False

    @property
    def instance_id(self):
        return self.__instance_id

    def run(self):
        self.__started = True
        try:
            self.__method(self)
        except Exception as e:
            self.__error_callback(self, e)
        _del_thread_instances(self.instance_id)
        self.__started = False

    def kill(self):
        if not self.__started:
            return
        res = pythonapi.PyThreadState_SetAsyncExc(c_long(self.ident), py_object(SystemExit))
        if res == 0:
            raise ValueError("invalid thread id: " + str(self.ident))
        elif res != 1:
            pythonapi.PyThreadState_SetAsyncExc(self.ident, None)
            raise SystemError("PyThreadState_SetAsyncExc failed")
        _del_thread_instances(self.instance_id)
        self.__started = False


class SocketServer:
    def __init__(self, mcdr_server: ServerInterface, server_name='SocketServer', dispatch_event_on_executor_thread=True):
        self.__instance_id = _storage_socket_api_instances(self)
        self.__socket = None
        self.__mcdr_server = mcdr_server
        self.__name = server_name
        self.__on_executor_thread = dispatch_event_on_executor_thread
        self.__threads = []
        self.__conns = {}
        self.__clients = {}
        self.__tid = {}
        self.__events = {}
        self.__exit = False
        self.__listening = False
        self.__ON_CONNECTED_EVENT = LiteralEvent('{}.on_connected'.format(PLUGIN_METADATA['id']))

    @property
    def instance_id(self):
        return self.__instance_id

    @property
    def name(self):
        return self.__name

    @property
    def socket(self):
        return self.__socket

    def start(self, host='localhost', port=7000, bufsize=1024, max_thread=1):
        if self.__listening:
            raise SocketError('Socket has been started.')
        if self.__socket is None:
            self.__socket = socket(AF_INET, SOCK_STREAM)
            self.__socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
            self.__socket.bind((host, port))
        if self.__exit:
            self.__exit = False
            _storage_socket_api_instances(self, self.instance_id)
        self.__socket.listen(5)
        self.__listening = True
        self.bufsize = bufsize
        self.host = host
        self.port = port
        self.__max_thread = max_thread if max_thread > 0 else 1
        _SocketThread(self.__server, self.__thread_error).start()

    def __server(self, thread: Thread):
        self.__threads.append(thread)
        new_thread = True
        while True:
            thread.setName(f'{self.__name}-{str(len(self.__threads) + 1)}[Waiting to connect]')
            conn, addr = self.__socket.accept()
            client_flags = loads(conn.recv(self.bufsize))
            client_name = client_flags['name']
            self.__conns[client_name] = conn
            self.__clients[thread.ident] = client_name
            self.__tid[client_name] = thread.ident
            thread.setName(f'{self.__name}-{str(len(self.__threads))}[Connected to {client_name}]')
            self.__mcdr_server.dispatch_event(self.__ON_CONNECTED_EVENT, (addr, client_name), on_executor_thread=self.__on_executor_thread)
            if len(self.__threads) < self.__max_thread and new_thread and not self.__exit:
                new_thread = False
                _SocketThread(self.__server, self.__thread_error).start()
            while True:
                try:
                    recv = conn.recv(self.bufsize)
                except Exception:
                    self.close(client_name)
                    break
                recv_json = loads(recv)
                if recv_json['target_clients'] == '##all##':
                    recv_json['target_clients'] = list(self.__conns.keys())
                    recv_json['target_clients'].append(self.__name)
                if self.__name in recv_json['target_clients'] or 'SocketServer' in recv_json['target_clients']:
                    self.__dispatch_event(recv_json)
                    self.__check_signal(thread.ident, client_flags['name'], recv_json)
                    recv_json['target_clients'].remove(self.__name)
                recv_json['target_clients'].remove(client_flags['name'])
                self.__forward(client_flags['name'], recv_json)

    def register_event(self, event_name):
        if event_name in self.__events:
            raise EventRegisteredError(f'Event {event_name} has been registered')
        self.__events[event_name] = LiteralEvent('{}.{}'.format(PLUGIN_METADATA['id'], event_name))
        return list(self.__events.keys())

    def __check_signal(self, tid, name, data):
        if 'signal' in data:
            signal = data['signal']
            if signal == 'client_close':
                self.__conns[name].shutdown(2)
                self.__conns[name].close()
                del self.__conns[name]
                del self.__clients[tid]

    def __dispatch_event(self, data):
        if data['event'] in self.__events:
            self.__mcdr_server.dispatch_event(self.__events[data['event']], (data['data'],), on_executor_thread=self.__on_executor_thread)

    def __forward(self, name, data):
        if not data['target_clients']:
            return
        if 'signal' in data:
            self.send_to(data['target_clients'], data['event'], data['data'], name, data['signal'])
        else:
            self.send_to(data['target_clients'], data['event'], data['data'], name)

    def close(self, target_client):
        self.__check_status()
        if target_client not in self.__conns:
            raise SocketError('No connection from client ' + target_client)
        self.send_to(target_client, None, None, signal='close')
        self.__conns[target_client].shutdown(2)
        self.__conns[target_client].close()
        del self.__conns[target_client]
        del self.__clients[self.__tid[target_client]]
        del self.__tid[target_client]

    def close_all(self):
        self.__check_status()
        self.send_to_all(None, None, signal='close')
        for c in self.__conns.values():
            c.shutdown(2)
            c.close()
        self.__conns.clear()
        self.__clients.clear()
        self.__tid.clear()

    def send_to(self, target_clients, event, data, source='server_name', signal=None):
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
        byt = dumps(json, separators=separators).encode('utf-8')
        errors = []
        try:
            for c in self.__conns:
                c.send(byt)
        except Exception as e:
            errors.append(e)
        return errors if errors else None

    def send_to_all(self, event, data, source='server_name', signal=None):
        self.__check_status()
        if not self.__conns:
            raise SocketError('Not connected to the client.')
        source = source if not source == 'server_name' else self.__name
        if signal is not None:
            json = {'source': source, 'signal': signal, 'event': event, 'data': data}
        else:
            json = {'source': source, 'event': event, 'data': data}
        data = dumps(json, separators=separators).encode('utf-8')
        errors = []
        for c in self.__conns.values():
            try:
                c.send(data)
            except Exception as e:
                errors.append(e)
        return errors if errors else None

    def exit(self):
        self.__check_status()
        self.__listening = False
        self.close_all()
        try:
            for t in self.__threads:
                t.kill()
        except ValueError:
            pass
        if self.__conns:
            self.__socket.shutdown(2)
        self.__socket.close()
        self.__exit = True
        _del_socket_api_instances(self.instance_id)

    def __thread_error(self, thread: _SocketThread, error):
        self.__mcdr_server.logger.error(f'线程：{thread.name}出现错误：{str(error)}')
        self.__threads.remove(thread)
        if thread.ident in self.__clients:
            try:
                self.close(self.__clients[thread.ident])
            except SocketError:
                pass

    def __check_status(self):
        if self.__exit:
            raise SocketError('Socket has been closed.')
        elif self.__socket is None:
            raise SocketError('Socket is not started.')

    """
    def _debug_exit_all(self):
        thread_list = threading_enumerate()
        for t in thread_list:
            if t.name.startswith(self.__name):
                self.__mcdr_server.logger.debug(t.name)
                t.kill()
        for c in self.__conns.values():
            c.shutdown(2)
            c.close()
        if self.__conns:
            self.__socket.shutdown(2)
        self.__socket.close()
    """


class SocketClient:
    def __init__(self, mcdr_server: ServerInterface, client_name: str, dispatch_event_on_executor_thread=True):
        self.__instance_id = _storage_socket_api_instances(self)
        self.__socket = socket(AF_INET, SOCK_STREAM)
        self.__socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
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

    @property
    def socket(self):
        return self.__socket

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
        self.__client_thread = _SocketThread(self.__client, self.__thread_error)
        self.__client_thread.start()

    def __client(self, thread: Thread):
        retry_times = 0
        break_while = False
        while retry_times <= self.__reconnection_times:
            thread.setName(f'{self.__name}[Connecting]')
            try:
                self.__socket.connect((self.host, self.port))
            except Exception as e:
                self.__mcdr_server.logger.info('连接失败：' + str(e))
                sleep(self.__reconnection_interval)
                retry_times += 1
                continue
            else:
                retry_times = 0
            self.__connected = True
            self.__client_thread.setName(self.__name + '[Connected to server]')
            self.__socket.send(dumps({'name': self.__name}, separators=separators).encode('utf-8'))
            while True:
                try:
                    recv = self.__socket.recv(self.bufsize)
                except Exception:
                    break_while = True
                    break
                recv_json = loads(recv)
                if 'signal' in recv_json:
                    if recv_json['signal'] == 'close':
                        break
                self.__dispatch_event(recv_json)
            if break_while:
                break_while = False
                break
        self.__client_thread = None
        if retry_times > self.__reconnection_times:
            raise ConnectionFailedError('Connection failure times exceed the upper limit.')

    def register_event(self, event_name):
        if event_name in self.__events:
            raise EventRegisteredError(f'Event {event_name} has been registered')
        self.__events[event_name] = LiteralEvent('{}.{}'.format(PLUGIN_METADATA['id'], event_name))

    def __dispatch_event(self, data):
        if data['event'] in self.__events:
            self.__mcdr_server.dispatch_event(self.__events[data['event']], (data['data'],), on_executor_thread=self.__on_executor_thread)

    def send_to(self, target_clients: str or list, event, data, signal=None):
        if not self.__connected:
            raise SocketError('Not connected to the server.')
        if not isinstance(target_clients, list):
            target_clients = [target_clients]
        try:
            if signal is not None:
                self.__socket.send(dumps({'target_clients': target_clients, 'event': event, 'data': data, 'signal': signal}, separators=separators).encode('utf-8'))
            else:
                self.__socket.send(dumps({'target_clients': target_clients, 'event': event, 'data': data}, separators=separators).encode('utf-8'))
        except Exception as e:
            return e

    def send_to_all(self, event, data, signal=None):
        if not self.__connected:
            raise SocketError('Not connected to the server.')
        try:
            if signal is not None:
                self.__socket.send(dumps({'target_clients': '##all##', 'event': event, 'data': data, 'signal': signal}, separators=separators).encode('utf-8'))
            else:
                self.__socket.send(dumps({'target_clients': '##all##', 'event': event, 'data': data}, separators=separators).encode('utf-8'))
        except Exception as e:
            return e

    def __close(self, del_instances=False):
        if self.__connected:
            self.send_to(['SocketServer'], None, None, 'client_close')
            self.__connected = False
        self.__socket.shutdown(2)
        if del_instances:
            self.__socket.close()
            _del_socket_api_instances(self.instance_id)

    def reconnect(self):
        if self.host is None:
            raise SocketError('Need to call connect() first.')
        self.__close()
        self.__client_thread = _SocketThread(self.__client, self.__thread_error, None)
        self.__client_thread.start()

    def exit(self):
        self.__close(True)
        if self.__client_thread is None:
            return
        try:
            self.__client_thread.kill()
        except Exception as e:
            self.__mcdr_server.logger.error(str(e))

    def __thread_error(self, thread: Thread, error):
        self.__client_thread = None
        if error is ConnectionFailedError:
            return
        self.__mcdr_server.logger.error(f'线程：{thread.name}出现错误：{str(error)}')
        if self.__connected:
            self.__close()
