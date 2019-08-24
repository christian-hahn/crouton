import socket
from threading import Lock
import msgpack
try:
    import msgpack_numpy
    msgpack_numpy.patch()
except ImportError:
    # msgpack_numpy is optional
    pass


class Client(object):

    def __init__(self, host='localhost', port=5000):
        self._lock = Lock()
        self._ref_count = 0
        self._eol = False
        self._sock = None
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
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.connect((host, port))

    def __del__(self):
        self._eol = True
        with self._lock:
            if not self._ref_count:
                self._close_socket()

    def _close_socket(self):
        """Close socket if open."""
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def _open(self, provider, *args, **kwargs):
        """Make open request.

        Args:
            provider (str): provider name
            *args: tuple of positional arguments
            **kwargs: dict of keyword arguments

        Returns:
            Proxy: new Proxy object
        """
        return self._request({
            'action': 'open',
            'provider': provider,
            'args': args,
            'kwargs': kwargs,
        })

    def _close(self, instance):
        """Make close request.

        Args:
            instance (str): object ID

        Returns:
            None: None object
        """
        return self._request({
            'action': 'close',
            'instance': instance,
        })

    def _execute(self, instance, method, *args, **kwargs):
        """Make execute request.

        Args:
            instance (str): object ID
            method (str): method name
            *args: tuple of positional arguments
            **kwargs: dict of keyword arguments

        Returns:
            object: returned object
        """
        return self._request({
            'action': 'execute',
            'method': method,
            'instance': instance,
            'args': args,
            'kwargs': kwargs,
        })

    def _receive(self):
        """Receive a response.

        Returns:
            dict: response
        """
        while True:
            chunk = self._sock.recv(1048576)
            if not chunk:
                return None
            self._unpacker.feed(chunk)
            for response in self._unpacker:
                return response

    def _request(self, obj):
        """Make a request.

        Args:
            obj (dict): request

        Returns:
            object: returned value

        Raises:
            RemoteError: On remote request error.
            TypeError: On invalid response.
        """
        with self._lock:
            self._sock.sendall(self._packer.pack(obj))
            obj = self._receive()
        ret_type = obj['type']
        if ret_type == 'value':
            return obj['data']
        elif ret_type == 'reference':
            ret_data = obj['data']
            self._ref_count += 1
            return Proxy(self, ret_data['instance'], ret_data['ownership'])
        elif ret_type == 'error':
            raise RemoteError(obj['message'])
        raise TypeError('Invalid response.')

    def _release(self):
        """Release a client. To be called by Proxy finalizer."""
        with self._lock:
            self._ref_count -= 1
            if self._eol and not self._ref_count:
                self._close_socket()

    def factory(self, provider, *args, **kwargs):
        provider = provider.__name__ if isinstance(provider, type) else provider
        return self._open(provider, *args, **kwargs)


class RemoteError(Exception):
    pass


class Proxy(object):

    def __init__(self, client, instance, ownership):
        super(Proxy, self).__setattr__('_cli', client)
        super(Proxy, self).__setattr__('_inst', instance)
        super(Proxy, self).__setattr__('_ownership', ownership)

    ### BASIC ###

    def __del__(self):
        if self._ownership:
            self._cli._close(self._inst)
        self._cli._release()

    def __repr__(self):
        return self._cli._execute(self._inst, '__repr__')

    def __str__(self):
        return self._cli._execute(self._inst, '__str__')

    def __bytes__(self):
        return self._cli._execute(self._inst, '__bytes__')

    def __format__(self, format_spec):
        return self._cli._execute(self._inst, '__format__', format_spec)

    def __lt__(self, other):
        return self._cli._execute(self._inst, '__lt__', other)

    def __le__(self, other):
        return self._cli._execute(self._inst, '__le__', other)

    def __eq__(self, other):
        return self._cli._execute(self._inst, '__eq__', other)

    def __ne__(self, other):
        return self._cli._execute(self._inst, '__ne__', other)

    def __gt__(self, other):
        return self._cli._execute(self._inst, '__gt__', other)

    def __ge__(self, other):
        return self._cli._execute(self._inst, '__ge__', other)

    def __hash__(self):
        return self._cli._execute(self._inst, '__hash__')

    def __bool__(self):
        return self._cli._execute(self._inst, '__bool__')

    ### ATTRIBUTE ACCESS ###

    def __getattr__(self, name):
        return self._cli._execute(self._inst, '__getattr__', name)

    def __setattr__(self, name, value):
        self._cli._execute(self._inst, '__setattr__', name, value)

    def __delattr__(self, name):
        self._cli._execute(self._inst, '__delattr__', name)

    def __dir__(self):
        return self._cli._execute(self._inst, '__dir__')

    ### CALLABLE ###

    def __call__(self, *args, **kwargs):
        return self._cli._execute(self._inst, '__call__', *args, **kwargs)

    ### CONTAINER ###

    def __len__(self):
        return self._cli._execute(self._inst, '__len__')

    def __length_hint__(self):
        return self._cli._execute(self._inst, '__length_hint__')

    def __getitem__(self, key):
        return self._cli._execute(self._inst, '__getitem__', key)

    def __missing__(self, key):
        return self._cli._execute(self._inst, '__missing__', key)

    def __setitem__(self, key, value):
        return self._cli._execute(self._inst, '__setitem__', key, value)

    def __delitem__(self, key):
        return self._cli._execute(self._inst, '__delitem__', key)

    def __iter__(self):
        return self._cli._execute(self._inst, '__iter__')

    def __reversed__(self):
        return self._cli._execute(self._inst, '__reversed__')

    def __contains__(self, item):
        return self._cli._execute(self._inst, '__contains__', item)
