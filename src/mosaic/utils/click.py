import click

class Group(click.Group):
    def get_help_option(self, ctx):
        help_option = super().get_help_option(ctx)
        if help_option:
            help_option.help = 'show help for this command'
        return help_option


class Command(click.Command):
    def get_help_option(self, ctx):
        help_option = super().get_help_option(ctx)
        if help_option:
            help_option.help = 'show help for this command'
        return help_option