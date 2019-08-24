#!/usr/bin/env python

from crouton import Server

# Create server, defaults to 'localhost', 5000
server = Server()

# Register some types
server.register(int)
server.register(float)
server.register(dict)
server.register(list)

# Start the server request-loop
server.run()
