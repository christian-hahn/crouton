[![](docs/banner.jpg)](https://github.com/christian-hahn/crouton)

## Transparent Remote Objects [![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/christian-hahn/crouton/blob/master/LICENSE)

**crouton** */ˈkruːtɒn/* is a pure Python library to facilitate the remote instantiation, manipulation and transparent use of one Python interpreter's Objects from another interpreter.  It implements a server-client model, where the Server can register Types and Instances to be accessible from a remote Client. The transport layer is implemented via TCP sockets.

**crouton** does not require any changes to be made to the Objects or Types being exposed.  To demonstrate this, below are examples that expose Python built-in types.

crouton requires Python 3.

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

```

### Client

```python
from crouton import Client

# Create client, defaults to 'localhost', 5000
client = Client()

# Create an instance of MyObject on the remote server
obj = client.factory('MyObject')
ret = obj.a_method('hello')
print(ret) # Prints "hello world"

# Create a list on the remote server
obj = client.factory(list)

# Perform some operations on the remote object
for item in (1.1, '1.1', 1, [], {}):
    obj.append(item)
print(obj)  # Prints "[1.1, '1.1', 1, [], {}]"
```

## License
crouton is covered under the MIT licensed.
