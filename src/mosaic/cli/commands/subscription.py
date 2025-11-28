import click
from mosaic.cli.base import CustomGroup

@click.group(name="subscription", cls=CustomGroup)
def subscription():
    """Manage the Mosaic Mesh Subscriptions"""