import click
import requests

from mosaic.utils.click import Group, Command

@click.group(name="node", cls=Group)
def node():
    """manage the mosaic nodes"""


@node.command(cls=Command)
def create():
    """create a new mosaic node"""
    pass


@node.command(cls=Command)
def list():
    """list all the mosaic nodes"""
    pass


@node.command(cls=Command)
def topology():
    """show the topology of the mosaic nodes"""
    pass


@node.command(cls=Command)
def delete():
    """delete a mosaic node"""
    pass


@node.command(cls=Command)
def show():
    """show details of a mosaic node"""
    pass


@node.command(cls=Command)
def config():
    """configure the mosaic node"""
    pass


@node.command(cls=Command)
def start():
    """start the mosaic node"""
    pass


@node.command(cls=Command)
def stop():
    """stop the mosaic node"""
    pass


@node.command(cls=Command)
def chat():
    """chat with the mosaic node"""
    pass


@node.command(cls=Command)
def program():
    """program the mosaic node"""
    pass