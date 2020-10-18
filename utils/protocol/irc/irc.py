import enum
import importlib
import os
import re
import socket
import ssl
import random
from pathlib import Path

from utils.protocol.irc import classes
from utils.settings import irc
from utils.logger import logging


class RPL(enum.Enum):
    """
    RPL numerics for IRC protocol.
    """
    WELCOME = 1
    ISUPPORT = 5

    NAMEREPLY = 353


class ERR(enum.Enum):
    NICKNAMEINUSE = 433


class IRCEvent(enum.Enum):
    """
    Events for IRC protocol. The numbers have no meaning.
    """
    ERROR = 0
    PING = 1
    JOIN = 2
    PART = 3
    PRIVMSG = 4
    NOTICE = 5
    KICK = 6
    MODE = 7
    NICK = 8
    QUIT = 9


class IRC:
    cert = None
    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS)
    IRCEvent = IRCEvent

    def __init__(self, session):
        self.session = session  # self.session.users = where all the User objects will be stored for this session.
        self.support = {}  # Store all ISUPPORT replies.
        self.session.sock = socket.socket()
        self.session.connected = 0

        # This protocol can contain users and channels.
        self.session.users = []
        self.session.channels = []

        self.session.modules = {}
        logging.info(f'Socket for this session: {self.session.sock}')

        self.session.protocol = self
        logging.debug(f'Protocol for this session set: {self.session.protocol}')

        self.mod_dir = Path(os.path.dirname(os.path.abspath(__file__)) + '/modules/')
        logging.debug(f"Module dir for this protocol set: {self.mod_dir}")
        self.cmdprefix = "!"
        self.load_all_modules()

    def list_mods(self):
        mods = []
        for file in [file for file in os.listdir(self.mod_dir) if not file.startswith('__')]:
            file = file.split('.py')[:1][0][:-3]
            mods.append(file)
        return mods

    def load_module(self, name, reload=False):
        """
        :param name:    name of the module, i.e: tensorflow_ai
        :param reload:  boolean indicating if a reload is in order
        :return:        None
        """
        for d in os.listdir(self.mod_dir):
            mod_dir = str(Path(str(self.mod_dir) + '/' + d))
            if not os.path.isdir(mod_dir) or mod_dir.startswith("__"):
                continue
            for file in [file for file in os.listdir(mod_dir) if not file.startswith('__') \
                                                                 and file.endswith('.py') and file == name]:
                base_dir_name = os.path.basename(mod_dir)
                logging.debug(f"Looking for callables in {file}...")
                file = file.split('.py')[:1][0]
                og_relpath = os.path.relpath(os.path.dirname(__file__)).replace('\\', '/')
                relpath = os.path.relpath(os.path.dirname(__file__)).replace('\\', '.').replace('/', '.')
                package_path = relpath + '.modules.' + base_dir_name + '.' + file
                logging.debug(f"Importing package: {package_path}")
                module = importlib.import_module(package_path)  # If already exists, reload.
                if reload:
                    logging.debug(f"Calling importlib.reload()")
                    module = importlib.reload(module)
                logging.debug(f"Imported: {module}")

                itervalues = dict.values
                for i in itervalues(vars(module)):
                    if callable(i) and i.__name__ == "IRCModule":
                        self.session.modules[module] = []  # Store callables here.
                        mod_data_dir = Path(str(self.mod_dir) + f'/{base_dir_name}/data/')
                        i.mod_data_dir = str(mod_data_dir)
                        mod_obj = i(self.session)
                        self.session.modules[module].append(mod_obj)
                        logging.info(f'Module {mod_obj} loaded.')
                        logging.info(f'Callable: {i}')
                        if not os.path.exists(mod_data_dir):
                            logging.info(f"Creating: {mod_data_dir}")
                            os.makedirs(mod_data_dir)

    def unload_module(self, module):
        """
        Callable objects are stored in the session.modules dictionary:
        session.modules[module] where `module` is a module object.
        """
        for callable in [callable for callable in self.session.modules[module] if hasattr(callable, 'stop')]:
            callable.active = 0  # You can never be too sure.
            callable.stop()
        del self.session.modules[module]

    def reload_module(self, module):
        """
        Reload <module>. It should be a module object.
        """
        name = os.path.basename(module.__file__)
        name = os.path.relpath(name)
        self.unload_module(module)
        self.load_module(name, reload=True)

    def load_all_modules(self):
        # logging.debug(f"Looking for directories in {os.listdir(self.mod_dir)}")
        for d in os.listdir(self.mod_dir):
            mod_dir = str(Path(str(self.mod_dir) + '/' + d))
            if not os.path.isdir(mod_dir) or mod_dir.startswith("__"):
                continue
            for file in [file for file in os.listdir(mod_dir) if not file.startswith('__') and file.endswith('.py')]:
                self.load_module(file)

    def run(self):
        """
        Check IRC attributes and attempt to connect to the server.
        """
        irc.check_settings(self.session)
        server = f'{self.session.server}:{self.session.port}'
        logging.debug(f'Connecting to {server} on IRC...')
        if self.session.tls:
            if hasattr(self.session, 'cert'):
                self.ssl_ctx.load_cert_chain(self.session.cert, self.session.cert)
            logging.info('Wrapping socket in TLS.')
            self.session.sock = self.ssl_ctx.wrap_socket(self.session.sock)
            try:
                self.session.sock = self.ssl_ctx.wrap_socket(self.session.sock)
            except ssl.SSLError as ex:
                logging.info(f'Error: {ex}')
                logging.info('Check your port and make sure the server accepts TLS connections:')
                logging.info(f'Attempted to connect to {server} over TLS.')
                self.session.quit()
                return
            except OSError as ex:
                logging.exception(ex)
                logging.info(f'Failed to connect to {server}: TLS flag: {self.session.tls}')
        self.session.sock.connect((self.session.server, self.session.port))
        logging.info(f'Connected: {self.session.sock}')
        self.session.activate_session()

    def conn_established(self):
        nickname = ''
        for idx, char in enumerate(self.session.nickname):
            if char == "?":
                nickname += str(random.randint(0, 9))
            else:
                nickname += char
        self.session.nickname = nickname
        self.session.sendline(f'NICK {self.session.nickname}')
        self.session.sendline(f'USER {self.session.nickname} 0 0 :{self.session.nickname}')

    def connect_success(self):
        """"
        Triggered on RPL.WELCOME (001)
        """
        self.session.connected = 1
        logging.info('Successfully connected to IRC.')
        # Read session.config to perform on-connect shit. For now let's hardcode shit.
        if hasattr(self.session, 'channel'):
            self.join(self.session.channel)

    def get_event_objects(self, recv, event=None):
        """
        Retrieves the current user and target objects for this event.
        This should only be called if recv>3
        Creates object if not found.
        """
        user, target = None, None
        if recv[0].startswith(':') and '!' in recv[0] and '@' in recv[0]:  # User event.
            nick = recv[0][1:].split('!')[0]
            user = next((u for u in self.session.users if u.nickname == nick), None)
            if not user:
                user = classes.User(self.session, nick)

        if 'CHANTYPES' not in self.session.protocol.support:  # Don't know CHANTYPES yet.
            return user, target

        if recv[2][0] in self.session.protocol.support['CHANTYPES']:  # Target is a channel.
            target = next((c for c in self.session.channels if c.name == recv[2]), None)
            if not target:
                target = classes.Channel(self.session, recv[2])
        else:
            target = next((c for c in self.session.users if c.nickname == recv[2]), None)
            if not target and event != "NICK":  # Don't create new objects on nickchange.
                target = classes.User(self.session, recv[2])

        return user, target

    def quit(self, reason=None):
        self.session.sendline(f'QUIT{" " + reason if reason else ""}')

    def get_object(self, value):
        """
        Returns either User or Channel object.
        """
        obj = next((c for c in self.session.users if c.nickname == value), None)
        if obj:
            return obj
        return next((c for c in self.session.channels if c.name == value), None)

    def get_events(self, recv):
        """
        Read events for the IRC protocol for the session object to handle.
        :param self: current `IRC object`
        :param recv: list holding incoming IRC data
        :return: None
        """
        logging.debug(f'Handling get_events() for session {self.session}')
        logging.debug(f'Event buffer for {self.session}: {self.session.events}')
        for line in recv.split('\n'):
            if self.session.events:
                self.session.handle_event(self.session.events)
                self.session.events = []
                logging.debug(f'Events for {self.session} flushed.')
            args = line.split()
            if not args:
                continue

            if args[0] == 'PING':
                self.pong(args[1])

            # Check for numeric raws.
            if len(args) > 1 and args[1].isdigit():
                self.session.protocol.handle_raw(int(args[1]), args[3:])

            if len(args) <= 2:
                continue

            # These events most likely require objects.
            # Let's fetch the target of the event.
            event = args[1].upper()
            self.session.event_user_obj, self.session.event_target_obj = \
                self.get_event_objects(args, event)

            if not self.session.event_target_obj:  ### NICK AND QUIT DO NOT RETURN ANYTHING HERE
                if event == 'ERROR':
                    self.session.events.append((IRCEvent.ERROR, args[2:]))
                    # User might not have an object yet.
                    if self.session.event_user_obj:
                        self.session.event_user_obj.quit()

                if event == 'QUIT':
                    self.session.events.append((IRCEvent.QUIT, args[2:]))
                    self.session.event_user_obj.quit()

                elif event == 'NICK':
                    # :user NICK newnick
                    oldnick = self.session.event_user_obj.nickname
                    newnick = args[2] if args[2][0] != ':' else args[2][1:]
                    logging.info(f'[{event}] User {self.session.event_user_obj} changed its nickname to {newnick}')
                    self.session.event_user_obj.nickname = newnick
                    self.session.events.append((IRCEvent.NICK, oldnick))
                continue

            # self.event_target_obj is now either a User or a Channel.

            if type(self.session.event_target_obj).__name__ == 'Channel':
                logging.info(f'[{event}] Channel on which the event occurs: {self.session.event_target_obj}')

            elif self.session.event_user_obj:
                # Bot received a private message.
                pass

            if event == 'JOIN':
                self.session.events.append((IRCEvent.JOIN, None))
                self.session.event_target_obj.add_user(self.session.event_user_obj)

            elif event == 'PART':
                self.session.events.append((IRCEvent.PART, None))
                self.session.event_target_obj.remove_user(self.session.event_user_obj)

            if len(args) > 3:
                stripped_data = args[3:]
                if stripped_data[0].startswith(':'):
                    stripped_data[0] = stripped_data[0][1:]

                if event == 'KICK':
                    kick_target_obj = self.get_object(args[3])
                    reason = args[4:]
                    if reason[0].startswith(':'):
                        reason[0] = reason[0][1:]
                    self.session.events.append((IRCEvent.KICK, (kick_target_obj, reason)))
                    self.session.event_target_obj.remove_user(kick_target_obj)

                elif event == 'MODE':
                    self.session.events.append((IRCEvent.MODE, stripped_data))

                elif event == 'PRIVMSG':
                    """
                    Returns a tuple containing the IRCEvent.PRIVMSG object and text,
                    where `text` is a list.
                    """
                    self.session.events.append((IRCEvent.PRIVMSG, stripped_data))

                elif event == 'NOTICE':
                    """
                    Returns a tuple containing the IRCEvent.PRIVMSG object and text,
                    where `text` is a list.
                    """
                    self.session.events.append((IRCEvent.NOTICE, stripped_data))

            for m in self.session.modules:
                for callable in self.session.modules[m]:
                    for event in self.session.events:
                        logging.info(f'Calling {callable} with event: {event}')
                        callable.run(event, args)

    def handle_raw(self, num, data):
        if num == ERR.NICKNAMEINUSE.value:
            if hasattr(self.session, 'alt_nick'):
                newnick = self.session.alt_nick
            else:
                newnick = self.session.nickname + '-' + ''.join(random.choice('1234567890') for _ in range(3))
            logging.info(f'[{ERR(num).name}] Nickname {self.session.nickname} is already in use. Trying {newnick}...')
            self.nick(newnick)

        if num == RPL.WELCOME.value:
            self.session.nickname = data[::-1][0].split('!')[0]
            classes.User(self.session, self.session.nickname)
            self.connect_success()

        elif num == RPL.ISUPPORT.value:
            for entry in data:
                if entry.startswith(':'):
                    break
                support, value = entry, None
                if len(entry.split('=')) > 1:
                    support = entry.split('=')[0]
                    value = entry.split('=')[1]
                self.support[support] = value

        elif num == RPL.NAMEREPLY.value:
            channel = data[1]
            channel_obj = next((c for c in self.session.channels if c.name == channel), None)
            if not channel_obj:
                channel_obj = classes.Channel(self.session, channel)

            names = data[2:]
            if names[0][0] == ':':
                names[0] = names[0][1:]
                for nick in names:
                    raw_nick = nick
                    nick = re.sub('[:*!~&@%+]', '', nick)
                    user_obj = next((u for u in self.session.users if u.nickname == nick), None)
                    if not user_obj:
                        user_obj = classes.User(self.session, nick)
                    if user_obj not in channel_obj.users:
                        channel_obj.add_user(user_obj)

                    if '~' in raw_nick:
                        channel_obj.usermodes[user_obj] += 'q'
                    if '&' in raw_nick:
                        channel_obj.usermodes[user_obj] += 'a'
                    if '@' in raw_nick:
                        channel_obj.usermodes[user_obj] += 'o'
                    if '%' in raw_nick:
                        channel_obj.usermodes[user_obj] += 'h'
                    if '+' in raw_nick:
                        channel_obj.usermodes[user_obj] += 'v'

    def pong(self, arg):
        self.session.sendline('PONG ' + arg)

    def say(self, msg, target):
        if not target:
            target = str(self.session.event_target_obj)
        self.session.sendline(f'PRIVMSG {target} :{msg}')

    def join(self, channel):
        self.session.sendline('JOIN ' + channel)

    def part(self, channel):
        self.session.sendline('PART ' + channel)

    def nick(self, newnick):
        self.session.sendline('NICK ' + newnick)

    def __repr__(self):
        if hasattr(self, 'session'):
            return f'<IRC ({self.session.nickname})>'
        return "<IRC *>"

    def __str__(self):
        return "IRC"
