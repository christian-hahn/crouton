import socket
from threading import Lock
import msgpack
try:
    import msgpack_numpy
    msgpack_numpy.patch()
except ImportError:
    # msgpack_numpy is optional
    pass


class Client:

    def __init__(self, host='localhost', port=5000):
        """Client object.

        Args:
            host (str, optional): host, default 'localhost'
            port (int, optional): TCP port number, default 5000
        """
        self._lock = Lock()
        self._socket = None
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
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.connect((host, port))

    def __del__(self):
        with self._lock:
            self._close_socket()

    def _close_socket(self):
        """Close socket if open."""
        if not self._socket is None:
            try:
                self._socket.close()
            finally:
                self._socket = None

    @property
    def is_open(self):
        """Is socket open?

        Returns:
            bool: is open
        """
        return not self._socket is None

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
            chunk = self._socket.recv(1048576)
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
            self._socket.sendall(self._packer.pack(obj))
            obj = self._receive()
        ret_type = obj['type']
        if ret_type == 'value':
            return obj['value']
        elif ret_type == 'reference':
            value = obj['value']
            return Proxy(self, value)
        elif ret_type == 'error':
            raise RemoteError(obj['value'])
        raise TypeError('Invalid response.')

    def factory(self, provider, *args, **kwargs):
        provider = provider.__name__ if isinstance(provider, type) else provider
        return self._open(provider, *args, **kwargs)


class RemoteError(Exception):
    pass


class Proxy:

    def __init__(self, client, instance):
        super(Proxy, self).__setattr__('_cli', client)
        super(Proxy, self).__setattr__('_execute', client._execute)
        super(Proxy, self).__setattr__('_inst', instance)

    ## Basic

    def __del__(self):
        if self._cli.is_open:
            self._cli._close(self._inst)

    def __repr__(self):
        return self._execute(self._inst, '__repr__')

    def __str__(self):
        return self._execute(self._inst, '__str__')

    def __bytes__(self):
        return self._execute(self._inst, '__bytes__')

    def __format__(self, format_spec):
        return self._execute(self._inst, '__format__', format_spec)

    def __lt__(self, other):
        return self._execute(self._inst, '__lt__', other)

    def __le__(self, other):
        return self._execute(self._inst, '__le__', other)

    def __eq__(self, other):
        return self._execute(self._inst, '__eq__', other)

    def __ne__(self, other):
        return self._execute(self._inst, '__ne__', other)

    def __gt__(self, other):
        return self._execute(self._inst, '__gt__', other)

    def __ge__(self, other):
        return self._execute(self._inst, '__ge__', other)

    def __hash__(self):
        return self._execute(self._inst, '__hash__')

    def __bool__(self):
        return self._execute(self._inst, '__bool__')

    ## Attribute access

    def __getattr__(self, name):
        return self._execute(self._inst, '__getattr__', name)

    def __setattr__(self, name, value):
        self._execute(self._inst, '__setattr__', name, value)

    def __delattr__(self, name):
        self._execute(self._inst, '__delattr__', name)

    def __dir__(self):
        return self._execute(self._inst, '__dir__')

    ## Callable

    def __call__(self, *args, **kwargs):
        return self._execute(self._inst, '__call__', *args, **kwargs)

    ## Container

    def __len__(self):
        return self._execute(self._inst, '__len__')

    def __length_hint__(self):
        return self._execute(self._inst, '__length_hint__')

    def __getitem__(self, key):
        return self._execute(self._inst, '__getitem__', key)

    def __missing__(self, key):
        return self._execute(self._inst, '__missing__', key)

    def __setitem__(self, key, value):
        return self._execute(self._inst, '__setitem__', key, value)

    def __delitem__(self, key):
        return self._execute(self._inst, '__delitem__', key)

    def __iter__(self):
        return self._execute(self._inst, '__iter__')

    def __reversed__(self):
        return self._execute(self._inst, '__reversed__')

    def __contains__(self, item):
        return self._execute(self._inst, '__contains__', item)

    ## Context managers

    def __enter__(self):
        return self._execute(self._inst, '__enter__')

    def __exit__(self, type_, value, traceback):
        return self._execute(self._inst, '__exit__', type_, value, traceback)

    ## Numeric

    def __add__(self, other):
        return self._execute(self._inst, '__add__', other)

    def __sub__(self, other):
        return self._execute(self._inst, '__sub__', other)

    def __mul__(self, other):
        return self._execute(self._inst, '__mul__', other)

    def __matmul__(self, other):
        return self._execute(self._inst, '__matmul__', other)

    def __truediv__(self, other):
        return self._execute(self._inst, '__truediv__', other)

    def __floordiv__(self, other):
        return self._execute(self._inst, '__floordiv__', other)

    def __mod__(self, other):
        return self._execute(self._inst, '__mod__', other)

    def __divmod__(self, other):
        return self._execute(self._inst, '__divmod__', other)

    def __pow__(self, other, *args, **kwargs):
        return self._execute(self._inst, '__pow__', other, *args, **kwargs)

    def __lshift__(self, other):
        return self._execute(self._inst, '__lshift__', other)

    def __rshift__(self, other):
        return self._execute(self._inst, '__rshift__', other)

    def __and__(self, other):
        return self._execute(self._inst, '__and__', other)

    def __xor__(self, other):
        return self._execute(self._inst, '__xor__', other)

    def __or__(self, other):
        return self._execute(self._inst, '__or__', other)

    def __radd__(self, other):
        return self._execute(self._inst, '__radd__', other)

    def __rsub__(self, other):
        return self._execute(self._inst, '__rsub__', other)

    def __rmul__(self, other):
        return self._execute(self._inst, '__rmul__', other)

    def __rmatmul__(self, other):
        return self._execute(self._inst, '__rmatmul__', other)

    def __rtruediv__(self, other):
        return self._execute(self._inst, '__rtruediv__', other)

    def __rfloordiv__(self, other):
        return self._execute(self._inst, '__rfloordiv__', other)

    def __rmod__(self, other):
        return self._execute(self._inst, '__rmod__', other)

    def __rdivmod__(self, other):
        return self._execute(self._inst, '__rdivmod__', other)

    def __rpow__(self, other, *args, **kwargs):
        return self._execute(self._inst, '__rpow__', other, *args, **kwargs)

    def __rlshift__(self, other):
        return self._execute(self._inst, '__rlshift__', other)

    def __rrshift__(self, other):
        return self._execute(self._inst, '__rrshift__', other)

    def __rand__(self, other):
        return self._execute(self._inst, '__rand__', other)

    def __rxor__(self, other):
        return self._execute(self._inst, '__rxor__', other)

    def __ror__(self, other):
        return self._execute(self._inst, '__ror__', other)
