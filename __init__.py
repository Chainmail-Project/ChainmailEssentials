import builtins
import threading
import time
import traceback
from typing import TypeVar, List, Optional, Match

from Chainmail import Wrapper
from Chainmail.Events import CommandSentEvent, PlayerConnectedEvent, Events
from Chainmail.MessageBuilder import MessageBuilder, Colours
from Chainmail.Player import Player
from Chainmail.Plugin import ChainmailPlugin
from plugins.ChainmailRCON import ChainmailRCON, RCONClientHandler

t = TypeVar("t")


class PendingTPA(object):

    def __init__(self, creator: Player, recipient: Player):
        self.created_at = time.time()
        self.creator = creator  # type: Player
        self.recipient = recipient  # type: Player
        self.responded = False
        self.notify_creation()

    def notify_creation(self):
        message = MessageBuilder()
        message.add_field("You have been sent a teleport request by ", Colours.gold)
        message.add_field(f"{self.creator.username}.\n", Colours.blue)
        message.add_field("Use ", Colours.gold)
        message.add_field("!tpaccept ", Colours.blue)
        message.add_field("to accept the request, or ", Colours.gold)
        message.add_field("!tpdeny ", Colours.blue)
        message.add_field("to decline it.", Colours.gold)
        self.recipient.send_message(message)

        message = MessageBuilder()
        message.add_field("Your request to ", Colours.gold)
        message.add_field(f"{self.recipient.username} ", Colours.blue)
        message.add_field("has been sent.", Colours.gold)
        self.creator.send_message(message)

    def do_teleport(self):
        message = MessageBuilder()
        message.add_field("Teleporting you to ", Colours.gold)
        message.add_field(f"{self.recipient.username}.", Colours.blue)
        self.creator.send_message(message)

        message = MessageBuilder()
        message.add_field("You are being teleported to by ", Colours.gold)
        message.add_field(f"{self.creator.username}.", Colours.blue)
        self.recipient.send_message(message)

        self.creator.teleport_to(self.recipient)

    def notify_expired(self):
        if not self.responded:
            message = MessageBuilder()
            message.add_field("Your TPA to ", Colours.gold)
            message.add_field(f"{self.recipient.username} ", Colours.blue)
            message.add_field("has expired.", Colours.gold)
            self.creator.send_message(message)

            message = MessageBuilder()
            message.add_field("Your TPA from ", Colours.gold)
            message.add_field(f"{self.creator.username} ", Colours.blue)
            message.add_field("has expired.", Colours.gold)
            self.recipient.send_message(message)

    def notify_denied(self):
        message = MessageBuilder()
        message.add_field(f"{self.recipient.username} ", Colours.blue)
        message.add_field("has declined your teleport request.", Colours.gold)
        self.creator.send_message(message)

        message = MessageBuilder()
        message.add_field("Request denied.", Colours.red)
        self.recipient.send_message(message)

    @property
    def expired(self) -> bool:
        return (time.time() - self.created_at) >= 60 or self.responded


class ChainmailEssentials(ChainmailPlugin):
    def __init__(self, manifest: dict, wrapper: "Wrapper.Wrapper") -> None:
        super().__init__(manifest, wrapper)

        self.rcon = getattr(builtins, "RCON")  # type: ChainmailRCON

        self.needs_update = self.new_version_available

        self.pending_tpas = []  # type: List[PendingTPA]

        self.eval_usage_message = MessageBuilder()
        self.eval_usage_message.add_field("Usage: ", colour=Colours.red, bold=True)
        self.eval_usage_message.add_field("!exec <code>", colour=Colours.gold)

        self.update_message = MessageBuilder()
        self.update_message.add_field("A new version of ", Colours.gold)
        self.update_message.add_field("Chainmail Essentials ", Colours.blue)
        self.update_message.add_field("is available.", Colours.gold)

        self.eval = self.wrapper.CommandRegistry.register_command("!eval", "^!eval (.+)$", "Evaluates Python expressions.", self.command_eval, True)
        self.eval_usage = self.wrapper.CommandRegistry.register_command("!eval", "^!eval$", "Displays the usage message.", self.command_eval_usage, True)
        self.commands = self.wrapper.CommandRegistry.register_command("!commands", "^!commands$", "Lists commands accessible to a user.", self.command_commands)
        self.plugins = self.wrapper.CommandRegistry.register_command("!plugins", "^!plugins$", "Lists all loaded plugins.", self.command_plugins)
        self.reload = self.wrapper.CommandRegistry.register_command("!reload", "^!reload$", "Reloads all plugins.", self.command_reload, True)
        self.tpa = self.wrapper.CommandRegistry.register_command("!tpa", "^!tpa ([\\w\\d_]+)$", "Requests to teleport to another user.", self.command_tpa)
        self.tpaccept = self.wrapper.CommandRegistry.register_command("!tpaccept", "^!tpaccept$", "Accepts a teleport request.", self.command_tpaccept)
        self.tpdeny = self.wrapper.CommandRegistry.register_command("!tpdeny", "^!tpdeny$", "Denies a teleport request.", self.command_tpdeny)
        self.info = self.wrapper.CommandRegistry.register_command("!info", "^!info$", "Gets various info about the server.", self.command_info, True)

        self.rcon.register_command("/commands", "^/commands$", "Lists the commands you have access to.", self.rconcommand_commands)

        self.wrapper.EventManager.register_handler(Events.PLAYER_CONNECTED, self.handle_connection)

    def remove_expired_tpas_thread(self):
        while self.wrapper.wrapper_running and self.enabled:
            for tpa in self.pending_tpas:
                if tpa.expired:
                    tpa.notify_expired()
                    self.pending_tpas.remove(tpa)
            time.sleep(5)

    def get_tpa(self, creator: Player=None, recipient: Player=None) -> Optional[PendingTPA]:
        """
        Gets a pending tpa for a specified creator or recipient
        :param creator: The creator of the tpa
        :param recipient: The recipient of the tpa
        :return: The tpa
        """
        if creator is not None:
            for tpa in self.pending_tpas:
                if tpa.creator == creator:
                    return tpa
        if recipient is not None:
            for tpa in self.pending_tpas:
                if tpa.recipient == recipient:
                    return tpa
        return None

    # noinspection PyMethodMayBeStatic
    def command_eval(self, event: CommandSentEvent):
        code = event.args[0]
        # noinspection PyBroadException
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

    def rconcommand_commands(self, matches: List[Match[str]], client: RCONClientHandler):
        components = []
        seen = []
        for command in self.rcon.commands:
            if command["name"] not in seen and (client.authed or not command["requires_auth"]):
                seen.append(command["name"])
                components.append(f"{command['name']}: {command['description']}")
        client.writeline("\n".join(components))

    def command_plugins(self, event: CommandSentEvent):
        plugins = self.wrapper.PluginManager.get_all_plugins()
        builder = MessageBuilder()

        for plugin in plugins:
            if self.wrapper.PluginManager.get_plugin_loaded(plugin["manifest"]["name"]):
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

    def command_tpa(self, event: CommandSentEvent):
        recipient = self.wrapper.PlayerManager.get_player(event.args[0])
        if recipient is None:
            builder = MessageBuilder()
            builder.add_field("A player with that username was not found.", Colours.red)
            event.player.send_message(builder)
            return
        if self.get_tpa(creator=event.player) is not None:
            builder = MessageBuilder()
            builder.add_field("You already have an active outgoing TPA request.", Colours.red)
            event.player.send_message(builder)
            return
        if self.get_tpa(recipient=recipient) is not None:
            builder = MessageBuilder()
            builder.add_field("The other player already has a pending TPA request.", Colours.red)
            event.player.send_message(builder)
            return
        self.pending_tpas.append(PendingTPA(event.player, recipient))

    def command_tpaccept(self, event: CommandSentEvent):
        tpa = self.get_tpa(recipient=event.player)
        if tpa is None:
            builder = MessageBuilder()
            builder.add_field("You do not have a pending TPA.", Colours.red)
            event.player.send_message(builder)
            return
        tpa.responded = True
        tpa.do_teleport()

    def command_tpdeny(self, event: CommandSentEvent):
        tpa = self.get_tpa(recipient=event.player)
        if tpa is None:
            builder = MessageBuilder()
            builder.add_field("You do not have a pending TPA.", Colours.red)
            event.player.send_message(builder)
            return
        tpa.responded = True
        tpa.notify_denied()

    def command_info(self, event: CommandSentEvent):
        builder = MessageBuilder()
        builder.add_field("Server version: ", Colours.gold)
        builder.add_field(f"{self.wrapper.version}\n", Colours.blue)
        builder.add_field("OPs: ", Colours.gold)
        builder.add_field(f"{len(self.wrapper.ops)}", Colours.blue)
        event.player.send_message(builder)

    def handle_connection(self, event: PlayerConnectedEvent):
        if event.player.is_op and self.needs_update:
            event.player.send_message(self.update_message)

    def enable(self) -> None:
        super().enable()
        threading.Thread(target=self.remove_expired_tpas_thread).start()
