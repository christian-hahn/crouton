#!/usr/bin/env python

from crouton import Server

# Example user object
class MyObject:

    def a_method(self, an_arg):
        return an_arg + ' world'

# Create server, defaults to '0.0.0.0', 5000
server = Server()

# Register some types
server.register_type(MyObject)
server.register_type(int)
server.register_type(float)
server.register_type(dict)
server.register_type(list)

# Start the server request-loop
server.run()
