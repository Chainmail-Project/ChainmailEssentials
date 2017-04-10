import traceback
# noinspection PyPackageRequirements
import requests
from typing import TypeVar, List

from Chainmail.Events import CommandSentEvent, PlayerConnectedEvent, Events
from Chainmail.MessageBuilder import MessageBuilder, Colours
from Chainmail.Plugin import ChainmailPlugin


t = TypeVar("t")


class ChainmailEssentials(ChainmailPlugin):
    def __init__(self, manifest: dict, wrapper: "Wrapper.Wrapper") -> None:
        super().__init__(manifest, wrapper)

        self.remote_manifest_path = "https://raw.githubusercontent.com/Chainmail-Project/ChainmailEssentials/master/plugin.json"
        self.needs_update = False
        self.new_version = ""
        self.check_for_update()
        self.update_message = MessageBuilder()
        self.update_message.add_field("A new version of ", Colours.gold)
        self.update_message.add_field("Chainmail Essentials ", Colours.blue)
        self.update_message.add_field("is available.\nYou are running version ", Colours.gold)
        self.update_message.add_field(f"{self.manifest['version']}. ", Colours.blue)
        self.update_message.add_field("Newest version is ", Colours.gold)
        self.update_message.add_field(f"{self.new_version}.", Colours.blue)

        self.commands = self.wrapper.CommandRegistry.register_command("!commands", "^!commands$", "Lists commands accessible to a user.", self.command_commands)
        self.plugins = self.wrapper.CommandRegistry.register_command("!plugins", "^!plugins$", "Lists all loaded plugins.", self.command_plugins)

        self.eval_usage_message = MessageBuilder()
        self.eval_usage_message.add_field("Usage: ", colour=Colours.red, bold=True)
        self.eval_usage_message.add_field("!exec <code>", colour=Colours.gold)

        self.eval = self.wrapper.CommandRegistry.register_command("!eval", "^!eval (.+)$", "Evaluates Python expressions.", self.command_eval, True)
        self.eval_usage = self.wrapper.CommandRegistry.register_command("!eval", "^!eval$", "Displays the usage message.", self.command_eval_usage, True)

        self.reload = self.wrapper.CommandRegistry.register_command("!reload", "^!reload$", "Reloads all plugins.", self.command_reload, True)

        self.wrapper.EventManager.register_handler(Events.PLAYER_CONNECTED, self.handle_connection)

    @staticmethod
    def get_item_from_list(parent_list: List[t], item_index: int, default: t) -> t:
        try:
            return parent_list[item_index]
        except KeyError:
            return default

    def check_for_update(self):
        self.logger.info("Checking for update...")
        try:
            manifest = requests.get(self.remote_manifest_path).json()
            version_remote = manifest["version"].split(".")
            version_local = self.manifest["version"].split(".")
            for i in range(len(version_local)):
                if int(version_local[i]) < int(self.get_item_from_list(version_remote, i, "0")):
                    self.needs_update = True
                    self.logger.info(f"An update is available. Current version is v{self.manifest['version']}, updated version is v{manifest['version']}.")
                    self.new_version = manifest["version"]
                    return
            self.logger.info("No update required.")
        except requests.HTTPError:
            self.logger.warning("Failed to check for update.")

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

    def handle_connection(self, event: PlayerConnectedEvent):
        if event.player.is_op and self.needs_update:
            event.player.send_message(self.update_message)
