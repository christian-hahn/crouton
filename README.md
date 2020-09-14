# crouton [![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/christian-hahn/crouton/blob/master/LICENSE)

## Transparent Remote Objects

crouton is a pure Python library to facilitate the remote instantiation, manipulation and transparent use of one Python interpreter's Objects from another interpreter.  It implements a server-client model, where the Server can register Types and Instances to be accessible from a remote Client. The transport layer is implemented via TCP sockets.

crouton does not require any changes to be made to the Objects or Types being exposed.  To demonstrate this, below are examples that expose Python built-in types.

crouton is Python 2/3 compatible.

## Installation

Using `setup.py`:
```text
git clone https://github.com/christian-hahn/crouton.git
cd crouton
sudo python setup.py install
```

## Example

### Server

```python
from crouton import Server

# Create server, defaults to '0.0.0.0', 5000
server = Server()

# Register some types: clients can instantiate objects of
# these register types
server.register(int)
server.register(float)
server.register(dict)
server.register(list)
server.register(your_own_type_here)

# Start the server request-loop
server.run()
```

### Client

```python
from crouton import Client

# Create client, defaults to 'localhost', 5000
client = Client()

# Create a list on the remote server
obj = client.factory(list)

# Perform some operations on the remote list
# as if it were a local object
for item in (1.1, '1.1', 1, [], {}):
    obj.append(item)
print(obj)
```

## License
crouton is covered under the MIT licensed.
