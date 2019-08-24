"""Tests for Server object.

This module contains unit-tests for the Server object.
"""

from crouton import Server, Client
import unittest
from threading import Thread


HOST = 'localhost'
PORT = 5002


class ServerClientTestCase(unittest.TestCase):

    def setUp(self):
        self._server = Server(host=HOST, port=PORT)
        self._server_thread = Thread(target=self._server.run)
        self._server_thread.start()
        self._server.wait_for()
        self._client = Client(host=HOST, port=PORT)

    def tearDown(self):
        self._server.shutdown()
        del self._client
        self._server_thread.join()

    def test_list(self):
        self._server.register(list)
        obj = self._client.factory('list')
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

    def test_dict(self):
        self._server.register(list)
        obj = self._client.factory('list')
        obj = self._client.factory(list)
        print(len(obj))
        obj.append('field1')

    def test_obj(self):

        class TestObj(object):
            def __init__(self, arg1, arg2, kwarg1=None):
                self.arg1 = arg1
                self.arg2 = arg2
                self.kwarg1 = kwarg1

        self._server.register(TestObj)
        obj = self._client.factory(TestObj, 'arg1', 'arg2')
        print(obj.arg1)

if __name__ == '__main__':
    unittest.main()
