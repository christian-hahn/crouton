from setuptools import setup, find_packages

setup(
    name='crouton',
    version='1.0',
    description='Transparent Remote Objects',
    author='Christian Hahn',
    author_email='christianhahn09@gmail.com',
    packages=find_packages(),
    install_requires=[
        'msgpack',
    ],
    long_description='crouton is a pure Python library to facilitate the remote'
                     ' instantiation, manipulation and transparent use of one '
                     'Python interpreter\'s Objects from another interpreter.',
    license='MIT',
)
