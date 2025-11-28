import click
from typing import Dict

class CustomGroup(click.Group):
    def get_help_option(self, ctx):
        help_option = super().get_help_option(ctx)
        if help_option:
            help_option.help = 'Show help for this command'
        return help_option

class CustomCommand(click.Command):
    def get_help_option(self, ctx):
        help_option = super().get_help_option(ctx)
        if help_option:
            help_option.help = 'Show help for this command'
        return help_option

def parse_config(ctx, param, value) -> Dict[str, str]:
    config = {}
    for item in value:
        key, value = item.split("=", 1)
        config[key] = value
    return config