import traceback

from Chainmail.Events import CommandSentEvent
from Chainmail.MessageBuilder import MessageBuilder, Colours
from Chainmail.Plugin import ChainmailPlugin


class ChainmailEssentials(ChainmailPlugin):
    def __init__(self, manifest: dict, wrapper: "Wrapper.Wrapper") -> None:
        super().__init__(manifest, wrapper)

        self.commands = self.wrapper.CommandRegistry.register_command("!commands", "^!commands$", "Lists commands accessible to a user.", self.command_commands)
        self.plugins = self.wrapper.CommandRegistry.register_command("!plugins", "^!plugins$", "Lists all loaded plugins.", self.command_plugins)

        self.eval_usage_message = MessageBuilder()
        self.eval_usage_message.add_field("Usage: ", colour=Colours.red, bold=True)
        self.eval_usage_message.add_field("!exec <code>", colour=Colours.gold)

        self.eval = self.wrapper.CommandRegistry.register_command("!eval", "^!eval (.+)$", "Evaluates Python expressions.", self.command_eval, True)
        self.eval_usage = self.wrapper.CommandRegistry.register_command("!eval", "^!eval$", "Displays the usage message.", self.command_eval_usage, True)

        self.reload = self.wrapper.CommandRegistry.register_command("!reload", "^!reload$", "Reloads all plugins.", self.command_reload, True)

    def command_eval(self, event: CommandSentEvent):
        code = event.args[0]
        try:
            result = str(eval(code))
            error = False
        except:
            result = traceback.format_exc(1)
            error = True

        builder = MessageBuilder()
        colour = Colours.green if not error else Colours.red
        builder.add_field("Result: ", colour=Colours.gold)
        builder.add_field(result, colour=colour)
        event.player.send_message(builder)

    def command_eval_usage(self, event: CommandSentEvent):
        event.player.send_message(self.eval_usage_message)

    def command_commands(self, event: CommandSentEvent):
        commands = self.wrapper.CommandRegistry.get_accessible_commands(event.player)
        builder = MessageBuilder()
        seen_commands = []
        for command in commands:
            if command.name not in seen_commands:
                seen_commands.append(command.name)
                builder.add_field(f"{command.name}: ", Colours.red)
                suffix = "\n" if command != commands[-1] and command.name != commands[-1].name else ""
                builder.add_field(f"{command.description}{suffix}", Colours.gold)
        event.player.send_message(builder)

    def command_plugins(self, event: CommandSentEvent):
        plugins = self.wrapper.plugin_manager.get_all_plugins()
        builder = MessageBuilder()

        for plugin in plugins:
            if self.wrapper.plugin_manager.get_plugin_loaded(plugin["manifest"]["name"]):
                builder.add_field(f"{plugin['manifest']['name']}\n", Colours.blue)
                builder.add_field("    Developer: ", Colours.red)
                builder.add_field(f"{plugin['manifest']['developer']}\n", Colours.blue)
                suffix = "\n" if plugin != plugins[-1] else ""
                builder.add_field("    Version: ", Colours.red)
                builder.add_field(f"{plugin['manifest']['version']}{suffix}", Colours.blue)

        event.player.send_message(builder)

    def command_reload(self, event: CommandSentEvent):
        builder = MessageBuilder()
        builder.add_field("Reloading all plugins...", Colours.blue)
        event.player.send_message(builder)

        self.wrapper.reload()

        builder = MessageBuilder()
        builder.add_field("Plugins reloaded.", Colours.green)
        event.player.send_message(builder)
