#!/usr/bin/env python

from crouton import Client

# Create client, defaults to 'localhost', 5000
client = Client()

# Create a list on the remote server
obj = client.factory(list)

# Perform some operations on the remote object
for item in (1.1, '1.1', 1, [], {}):
    obj.append(item)
print(obj)
