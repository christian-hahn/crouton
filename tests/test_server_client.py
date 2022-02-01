"""Tests for Server & client object.

This module contains unit-tests for the Server & client object.
"""

from crouton import Server, Client
import unittest
from threading import Thread


HOST = 'localhost'
PORT = 5002


class ServerClientTestCase(unittest.TestCase):

    def setUp(self):
        self._server = Server()
        kwargs = {'host': HOST, 'port': PORT}
        self._server_thread = Thread(target=self._server.run, kwargs=kwargs)
        self._server_thread.start()
        self._server._wait_for()
        self._client = Client(host=HOST, port=PORT)

    def tearDown(self):
        # Tell server to shutdown. Just for unit-testing.
        self._server._shutdown()
        del self._client
        # Connect once more to get the server to shutdown. This is just a
        # hack for unit-test flow, since server is blocking on accept().
        cli = Client(host=HOST, port=PORT)
        del cli
        self._server_thread.join()

    def test_list(self):
        self._server.register_type(list)
        obj = self._client.factory(list)
        cases = (
            1.1,
            '1.1',
            1,
            ['test', 1],
            {'key': 'value', 1: 1.1},
            b'some_bytes',
            'a_str',
        )
        for item in cases:
            obj.append(item)
            self.assertEqual(obj[-1], item)
            self.assertTrue(item in obj)
            self.assertTrue(len(obj))
        for method in (str, repr, format, bool):
            method(obj)
        self.assertFalse('abc' in obj)

    def test_dict(self):
        self._server.register_type(list)
        obj = self._client.factory('list')
        print(len(obj))
        obj.append('field1')

    def test_obj(self):
        self._server.register_type(TestObject)
        obj = self._client.factory('TestObject', 'first arg', kwarg1='a keyword arg')
        print(obj.arg1)
        with obj as obj1:
            print(obj1)


class TestObject:

    def __init__(self, arg1, kwarg1=None):
        self.arg1 = arg1
        self.kwarg1 = kwarg1

    def __enter__(self):
        print('in __enter__()')
        return self

    def __exit__(self, type, value, traceback):
        print('in __exit__()')


if __name__ == '__main__':
    unittest.main()
