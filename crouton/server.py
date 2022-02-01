from threading import Event, Thread, Lock
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


class Server:

    def __init__(self):
        self._running = Event()
        self._namespace = Namespace()

    def run(self, host='0.0.0.0', port=5000):
        """Start the server. This blocking method runs the server
        request-reply loop.

        Args:
            host (str, optional): host address to bind to, default '0.0.0.0'
            port (int, optional): host port to bind to, default 5000
        """
        listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen_socket.bind((host, port))
        listen_socket.listen(5)
        log.info('Started listening for connections on {}:{}'.format(host, port))
        self._running.set()
        try:
            while self._running.is_set():
                client_socket, address = listen_socket.accept()
                log.info('Accepted connection from: {}:{}'.format(*address))
                worker = Worker(client_socket, address, self._namespace)
                worker.start()
        finally:
            listen_socket.close()
            log.info('Closed listening socket. Server shutdown.')

    def register(self, instance, name):
        """Register a named instance.

        Args:
            instance (object): instance to register
            name (str): name with which to register
        """
        if not isinstance(name, str):
            raise ValueError('name: Expected a string.')
        with self._namespace:
            if name in self._namespace:
                raise KeyError('An instance by name \'{}\' already exists.'
                    .format(name))
            inst_id = id(instance)
            self._namespace.add(instance, inst_id, self, name)
        log.info('Registered instance {} by name \'{}\'.'.format(inst_id, name))

    def register_type(self, provider, name=None):
        """Register a type.

        Args:
            provider (type): type to register
            name (str, optional): name with which to register
        """
        if name is None:
            # If no name is given, register using name of type.
            name = provider.__name__
        elif not isinstance(name, str):
            raise ValueError('name: Expected a string.')
        with self._namespace:
            if name in self._namespace.types:
                raise KeyError('A type by name \'{}\' already exists.'.format(name))
            self._namespace.types[name] = provider
        log.info('Registered type {} by name \'{}\'.'.format(provider, name))

    def _wait_for(self):
        """Wait for server to start listening. THIS IS FOR UNIT TESTING."""
        self._running.wait()

    def _shutdown(self):
        """Shutdown server. THIS IS FOR UNIT TESTING."""
        self._running.clear()


class Worker(Thread):

    def __init__(self, sock, address, namespace):
        super().__init__()
        self._socket = sock
        self._address = address
        self._namespace = namespace
        self._init_serdes()
        self._inst_ids = set()

    def run(self):
        try:
            while self._dispatch():
                continue
            log.info('Client {}:{} disconnected.'.format(*self._address))
        finally:
            # Close client socket
            self._socket.close()
            # Release all remaining references
            with self._namespace:
                self._namespace.release_all(self._inst_ids, self)

    def _dispatch(self):
        """ Receive a request, delegate and send response.

        Returns:
            bool: False if orderly shutdown occurred
        """
        request = self._receive()
        if request is None:
            return False
        try:
            action = request['action']
            if action == 'execute':
                response = self._action_execute(request)
            elif action == 'open':
                response = self._action_open(request)
            elif action == 'close':
                response = self._action_close(request)
            else:
                raise ValueError('Invalid request action: \'{}\''.format(action))
        except Exception:
            response = self._packer.pack({
                'type': 'error',
                'value': traceback.format_exc(),
            })
        self._socket.sendall(response)
        return True

    def _init_serdes(self):
        self._packer = msgpack.Packer(use_bin_type=True)
        """
        For backwards compatibility, try these kwargs in order, until one succeeds.
        * 'encoding' and 'unicode_errors' options are deprecated. There is new 'raw' option.
          It is True by default for backward compatibility, but it is changed to False in
          near future. You can use raw=False instead of encoding='utf-8'.
        * For backwards compatibility, set 'max_buffer_size' explicitly.
        * For backwards compatibility, set 'strict_map_key' to False explicitly, when possible.
        """
        kwargs_list = (
            {'strict_map_key': False, 'raw': False},
            {'raw': False},
            {'encoding': 'utf-8'},
        )
        for kwargs in kwargs_list:
            try:
                self._unpacker = msgpack.Unpacker(
                    use_list=True, max_buffer_size=2**31-1, **kwargs)
            except TypeError as ex:
                continue
            break
        else:
            raise RuntimeError('Failed to create unpacker.')

    def _action_open(self, request):
        """Open action handler.

        Args:
            request (dict): request

        Returns:
            bytes: response data
        """
        if 'provider' in request:
            # Make and return a new instance
            provider = request['provider']
            with self._namespace:
                types = self._namespace.types
                if not provider in types:
                    raise TypeError('Unknown type \'{}\'.'.format(provider))
                obj = types[provider](*request['args'], **request['kwargs'])
                instance = id(obj)
                response = self._packer.pack({
                    'type': 'reference',
                    'value': instance,
                })
                self._namespace.add(obj, instance, self)
            self._inst_ids.add(instance)
        elif 'instance' in request:
            # Return a named instance
            instance = request['instance']
            with self._namespace:
                if not instance in self._namespace:
                    raise ValueError('Unknown instance: {}'.format(instance))
                response = self._packer.pack({
                    'type': 'reference',
                    'value': instance,
                })
                self._namespace.acquire(instance, self)
            self._inst_ids.add(instance)
        else:
            raise ValueError('Bad open() request. Expected \'instance\' '
                             'or \'provider\'.')
        return response

    def _action_close(self, request):
        """Close action handler.

        Args:
            request (dict): request

        Returns:
            bytes: response data
        """
        instance = request['instance']
        with self._namespace:
            if not instance in self._namespace:
                raise KeyError('Instance {} does not exist.'.format(instance))
            released = self._namespace.release(instance, self)
        if released:
            self._inst_ids.remove(instance)
        response = self._packer.pack({
            'type': 'value',
            'value': None,
        })
        return response

    def _action_execute(self, request):
        """Execute action handler.

        Args:
            request (dict): request

        Returns:
            bytes: response data
        """
        instance = request['instance']
        with self._namespace:
            if instance not in self._namespace:
                raise KeyError('Instance \'{}\' does not exist.'.format(instance))
            method = request['method']
            if method in METHOD_HANDLERS:
                ret = METHOD_HANDLERS[method](self._namespace[instance],
                    *request['args'], **request['kwargs'])
            else:
                ret = getattr(self._namespace[instance], method)(
                    *request['args'], **request['kwargs'])
            try:
                response = self._packer.pack({
                    'type': 'value',
                    'value': ret,
                })
            except TypeError:
                instance = id(ret)
                response = self._packer.pack({
                    'type': 'reference',
                    'value': instance,
                })
                self._namespace.add(ret, instance, self)
                self._inst_ids.add(instance)
        return response

    def _receive(self):
        """Receive and unpack request.

        Returns:
            object: request or None
        """
        while True:
            chunk = self._socket.recv(1048576)
            if not chunk:
                return None
            self._unpacker.feed(chunk)
            try:
                for request in self._unpacker:
                    return request
            except Exception:
                self._init_serdes()
                raise


METHOD_HANDLERS = {
    '__getattr__': getattr,
    '__bool__': bool,
}


class Namespace:

    def __init__(self):
        self.types = {}
        # Instances by [instance id]
        self._instances = {}
        # Instances by [name]
        self._instances_by_name = {}
        # Reference counts by [instance id][owner]
        self._ref_counts = {}
        self._lock = Lock()

    def __getitem__(self, key):
        """Get an instance by id or name.

        Args:
            key (int, str): instance id or name

        Returns:
            object: instance
        """
        return self._instances[key] if isinstance(key, int) else \
            self._instances_by_name[key]

    def __contains__(self, item):
        """Is instance in namespace.

        Args:
            item (int, str): instance id or name

        Returns:
            bool: exists in namespace
        """
        return item in self._instances if isinstance(item, int) else \
            item in self._instances_by_name

    def __enter__(self):
        """On enter, lock namespace."""
        self._lock.acquire()
        return self

    def __exit__(self, type, value, traceback):
        """On exit, unlock namespace."""
        self._lock.release()

    def add(self, instance, inst_id, owner, name=None):
        """Add an instance and acquire reference.

        Args:
            instance (object): instance
            inst_id (int): instance id
            owner (object): owner
        """
        owner = id(owner)
        if inst_id in self._instances:
            ref_counts = self._ref_counts[inst_id]
            if owner in ref_counts:
                ref_counts[owner] += 1
            else:
                ref_counts[owner] = 1
        else:
            self._instances[inst_id] = instance
            self._ref_counts[inst_id] = {owner: 1}
        if not name is None:
            self._instances_by_name[name] = instance

    def acquire(self, inst_id, owner):
        """Acquire a reference to an instance.

        Args:
            inst_id (int): instance id
            owner (object): owner
        """
        owner = id(owner)
        ref_counts = self._ref_counts[inst_id]
        if owner in ref_counts:
            ref_counts[owner] += 1
        else:
            ref_counts[owner] = 1

    def release(self, inst_id, owner):
        """Release a reference to an instance.

        Args:
            inst_id (int): instance id
            owner (object): owner

        Returns:
            bool: owner released in instance
        """
        owner = id(owner)
        ref_counts = self._ref_counts[inst_id]
        ref_counts[owner] -= 1
        if ref_counts[owner] < 1:
            del ref_counts[owner]
            if not ref_counts:
                del self._ref_counts[inst_id]
                del self._instances[inst_id]
            return True
        return False

    def release_all(self, inst_ids, owner):
        """Release all references to a set of instances.

        Args:
            inst_ids (set): instance id
            owner (object): owner
        """
        owner = id(owner)
        for inst_id in inst_ids:
            log.info('release all ({})'.format(inst_id))
            ref_counts = self._ref_counts[inst_id]
            del ref_counts[owner]
            if not ref_counts:
                del self._ref_counts[inst_id]
                del self._instances[inst_id]
