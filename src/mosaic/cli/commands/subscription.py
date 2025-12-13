import click
import requests

from mosaic.utils.click import Group, Command

@click.group(name="subscription", cls=Group)
def subscription():
    """manage the mosaic subscriptions"""


@subscription.command(cls=Command)
def create():
    """create a new mosaic subscription"""
    pass


@subscription.command(cls=Command)
def delete():
    """delete a mosaic subscription"""
    pass