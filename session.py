"""
A very basic multi-service framework.
It only supports IRC as of now, but I plan on supporting more protocols in the future.


How it works:

Create a new session instance.
A session requires a protocol, which you can import from the utils dir:

from utils.protocol.irc import irc


You can define a session as follows:

new_session = Session(protocol=irc.IRC)


Now, `new_session` is a session instance with IRC protocol support.
We need to set certain IRC attributes before starting the session.

Required:
new_session.nickname = <string>     You can put question marks ("?") in the nickname for a random number.
new_session.server = <string>       Server hostname or IP to connect to.
new_session.port = <int>            Port of the server, must be an integer.

Optional:
new_session.tls = <bool>            Set to a true boolean to use TLS.
new_session.cert = <string>         Path to your *.pem file.
new_session.channel = <string       Channel to join upon connect.
new_session.alt_nick <string>       Alternative nickname, in case the given nickname is already in use.
                                    If it happens with this option disabled, it will append some random
                                    numbers at the end of your nick.



We have completed our IRC session instance, we can start it now:

new_session.start()


Your new_session object will connect to the server,
and if you specified a channel, it will join it once connected.
An example can be found at the bottom of this file.

In the Session object, you can interact with your session by making it respond to events.
The handle_event() method is where all the events are being processed.
You can use this to write your own methods and modules.
I already wrote a few examples the Session class below.
However, it is recommended to code all your functionality into modules.

At the time of writing, the IRC protocol only supports the following events:

irc.IRCEvent.PING
irc.IRCEvent.PRIVMSG
irc.IRCEvent.JOIN
irc.IRCEvent.PART
irc.IRCEvent.KICK
irc.IRCEvent.MODE
irc.IRCEvent.NICK
irc.IRCEvent.QUIT


You can open utils/protocol/irc/irc.py to add new event support in IRC.get_events() method if you wish.

An example IRC module can be found in the utils/protocol/irc/modules directory.
"""

import threading

from utils.classes import AbstractClass
from utils.logger import logging

# Import your protocol.
from utils.protocol.irc import irc


class Session(AbstractClass, threading.Thread):
    def __init__(self, protocol):
        threading.Thread.__init__(self)
        self.active = 0
        self.events = []
        self.protocol = protocol(self)
        logging.debug(f'Protocol for this session set: {self.protocol}')

    def run(self):
        self.protocol.run()

    def handle_event(self, event_queue):
        """
        We can search for predefined event hooks and interact with them based on the received events.
        """
        for got_events in event_queue:
            event, argument = got_events
            if str(self.protocol) == "IRC":
                """
                Methods inherited from the IRC protocol:
                
                self.protocol.join(channel)             Join a channel.
                self.protocol.part(channel)             Leave a channel.
                self.protocol.nick(newnick)             Change your nickname.


                Methods inherited from AbstractClass:
                
                self.say(text, target=None)             Delivers a message on IRC. If target is omitted (default),
                                                        current event_target_obj will be used. This is what you
                                                        want in most situations.
                                                        This method is called from the AbstractClass instead of the
                                                        Protocol class, because different protocols use different
                                                        ways to communicate.
                                                        
                self.quit()                             Disconnects from IRC and closes the session.
                """
                IRCEvent = irc.IRCEvent

                if event == IRCEvent.PRIVMSG:
                    if str(self.event_target_obj) == self.nickname:
                        logging.debug(f'I got a private message from: {self.event_user_obj}')
                        logging.debug(f'All users: {self.users}')
                        logging.debug(f'All channels: {self.channels}')

                    if argument[0] == '!whoareyou':
                        self.say(self.nickname)

                    if argument[0] == '!sessions':
                        self.say(self.sessions)

                    if argument[0] == '!bye':
                        self.quit('Byebye!')

                    if argument[0] == '!listusers':
                        for u in self.users:
                            self.say(u)
                        for c in self.channels:
                            self.say(c)
                            for u in c.users:
                                self.say(f"> {u}")

                    if argument[0] == '!reload':
                        self.say('Reloading all modules...')
                        for module in list(self.modules):
                            self.protocol.reload_module(module)
                        self.say('Done!')

                    if argument[0] == '!modules':
                        for m in self.modules:
                            self.say(m)

                    if argument[0] == '!raw':
                        self.sendline(' '.join(argument[1:]))

    def __repr__(self):
        if hasattr(self, 'protocol'):
            return f'<Session "{repr(self.protocol)}">'
        return '<Session>'



server = "irc.provisionweb.org"
port = 6697


new_session = Session(protocol=irc.IRC)

new_session.nickname = "sif-???"
#new_session.alt_nick = "alternative_nickname"
new_session.server = server
new_session.port = port
new_session.tls = 1
#new_session.cert = "/path/to/cert.pem"
new_session.channel = "#bla"

new_session.start()

