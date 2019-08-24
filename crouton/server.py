from threading import Event
import traceback
import logging
import socket
import msgpack
try:
    import msgpack_numpy
    msgpack_numpy.patch()
except ImportError:
    # msgpack_numpy is optional
    pass


# Setup logging
log = logging.getLogger('server')
log.setLevel(logging.INFO)
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
stream_handler.setFormatter(logging.Formatter(log_format))
log.addHandler(stream_handler)


"""
## Request format
{
    'action': str, {open | close | excute},
     <'provider': str>,
     <'instance': str>,
     <'method': str>,
    'args': (),
    'kwargs': {},
}

## Response format
{
    'type': str, {value | reference | error}
    <'value': object>,
    <'instance': str>,
    <'message': str>,
}
"""

def method_handler(method):
    def handler(self, *args, **kwargs):
        return getattr(self, method)(*args, **kwargs)
    return handler


def bool_handler(self):
    return bool(self)


METHODS = {
    '__repr__': method_handler('__repr__'),
    '__str__': method_handler('__str__'),
    '__bytes__': method_handler('__bytes__'),
    '__format__': method_handler('__format__'),
    '__lt__': method_handler('__lt__'),
    '__le__': method_handler('__le__'),
    '__eq__': method_handler('__eq__'),
    '__ne__': method_handler('__ne__'),
    '__gt__': method_handler('__gt__'),
    '__ge__': method_handler('__ge__'),
    '__hash__': method_handler('__hash__'),
    '__bool__': bool_handler,
    '__getattr__': method_handler('__getattribute__'),
    '__setattr__': method_handler('__setattr__'),
    '__delattr__': method_handler('__delattr__'),
    '__dir__': method_handler('__dir__'),
    '__call__': method_handler('__call__'),
    '__len__': method_handler('__len__'),
    '__length_hint__': method_handler('__length_hint__'),
    '__getitem__': method_handler('__getitem__'),
    '__missing__': method_handler('__missing__'),
    '__setitem__': method_handler('__setitem__'),
    '__delitem__': method_handler('__delitem__'),
    '__iter__': method_handler('__iter__'),
    '__reversed__': method_handler('__reversed__'),
    '__contains__': method_handler('__contains__'),
}


class Server(object):

    def __init__(self, host='0.0.0.0', port=5000):
        self._types = {}
        self._instances = {}
        self._host = host
        self._port = port
        self._running = Event()

    def _open(self, request):
        log.debug('open(request = {})'.format(request))
        provider = request['provider']
        if provider not in self._types:
            raise TypeError('Unknown type \'{}\'.'.format(provider))
        obj = self._types[provider](*request['args'], **request['kwargs'])
        instance = str(id(obj))
        response = self._packer.pack({
            'type': 'reference',
            'data': {
                'instance': instance,
                'ownership': True,
            },
        })
        self._instances[instance] = obj
        return response

    def _close(self, request):
        log.debug('close(request = {})'.format(request))
        instance = request['instance']
        if instance not in self._instances:
            return KeyError('Instance \'{}\' does not exist.'.format(instance))
        del self._instances[instance]
        response = self._packer.pack({
            'type': 'value',
            'data': None,
        })
        return response

    def _execute(self, request):
        log.debug('execute(request = {})'.format(request))
        instance = request['instance']
        if instance not in self._instances:
            return KeyError('Instance \'{}\' does not exist.'.format(instance))
        method = request['method']
        if method not in METHODS:
            return KeyError('Method \'{}\' is not supported.'.format(method))
        obj = METHODS[method](self._instances[instance],
            *request['args'], **request['kwargs'])
        try:
            response = self._packer.pack({
                'type': 'value',
                'data': obj,
            })
        except TypeError:
            instance = str(id(obj))
            response = self._packer.pack({
                'type': 'reference',
                'data': {
                    'instance': instance,
                    'ownership': True,
                },
            })
            self._instances[instance] = obj
        return response

    def _receive(self):
        while True:
            chunk = self._sock.recv(1048576)
            if not chunk:
                return None
            self._unpacker.feed(chunk)
            for request in self._unpacker:
                return request

    def wait_for(self):
        """Wait for server to start listening."""
        self._running.wait()

    def shutdown(self):
        """Shutdown server."""
        self._running.clear()

    def run(self):
        """Start the server. This blocking method runs the server request-reply loop."""
        listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen_sock.bind((self._host, self._port))
        listen_sock.listen(5)

        self._running.set()

        try:
            while self._running.is_set():
                (self._sock, conn_info) = listen_sock.accept()
                log.info('Accepted connection from: \'{}:{}\''.format(*conn_info))

                self._packer = msgpack.Packer(use_bin_type=True)
                # 'encoding' and 'unicode_errors' options are deprecated. There is new 'raw' option.
                # It is True by default for backward compatibility, but it is changed to False in
                # near future. You can use raw=False instead of encoding='utf-8'.
                # For backwards compatibility, set 'max_buffer_size' explicitly.
                try:
                    self._unpacker = msgpack.Unpacker(use_list=True, raw=False,
                                                      max_buffer_size=2**31-1)
                except TypeError:
                    self._unpacker = msgpack.Unpacker(use_list=True, encoding='utf-8',
                                                      max_buffer_size=2**31-1)

                try:
                    while True:
                        # Receive a request
                        request = self._receive()
                        if request is None:
                            break
                        try:
                            action = request['action']
                            if action == 'open':
                                response = self._open(request)
                            elif action == 'close':
                                response = self._close(request)
                            elif action == 'execute':
                                response = self._execute(request)
                            else:
                                raise ValueError('Invalid request action: \'{}\''
                                    .format(action))
                        except Exception:
                            response = self._packer.pack({
                                'type': 'error',
                                'message': traceback.format_exc(),
                            })
                        finally:
                            self._sock.sendall(response)
                finally:
                    try:
                        self._sock.close()
                    finally:
                        self._sock = None
                    log.info('Closed connection from: \'{}:{}\''.format(*conn_info))
        finally:
            try:
                listen_sock.close()
            finally:
                listen_sock = None
            log.info('Server shutdown.')

    def register(self, provider, name=None):
        """Register a named instance of an object OR a type.

        Args:
            provider (type): type or object to register
            name (str, optional): name under wich to register
        """
        if type(provider) is type:
            if name is None:
                name = provider.__name__
            elif not isinstance(name, basestring):
                raise TypeError('name must be string.')
            elif name in self._types:
                raise KeyError('A type by that name already exists.')
            self._types[name] = provider
            log.info('Registered type {} as \'{}\'.'.format(provider, name))
        else:
            if name is None:
                raise ValueError('Must provide a name when registering a' \
                    ' named instance.')
            elif not isinstance(name, basestring):
                raise TypeError('name must be string.')
            elif name in self._instances:
                raise KeyError('An instance by that name already exists.')
            self._instances[name] = provider
            log.info('Registered instance \'{}\'.'.format(provider))
