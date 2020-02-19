"""
This is a test module for the IRC protocol.
The main class must be called `IRCModule`, otherwise it won't work.
You can define as much classes as you wish, and use them in this module.

I wrote a simple timer example that loops every 60 seconds.
Like all other modules, it has a reference to your current `session` so you can interact with it.
"""

import threading
import time

class IRCModule:
    def __init__(self, session):
        self.session = session
        self.active = 1

        #SomeTimer(self, self.session).start()

    def run(self, event, recv):
        """
        :param event:   tuple containting the event object and additional data
        :param recv:    list holding incoming IRC data
        :return:        None

        You can access all objects from your session with self.session

        Exampple:
        self.session.event_user_obj     - User object triggering this event
        self.session.event_target_obj   - Target object where the event happens

        That's basically all you need. If for some reason you require more data,
        you can do some hocus-pocus with `recv`

        """
        event, data = event

        if event == self.session.protocol.IRCEvent.PRIVMSG:

            if data[0] == "!sup":
                self.session.say(f"Sup {self.session.event_user_obj.nickname}!")

            elif data[0] == "!users":
                for user in self.session.event_target_obj.users:
                    self.session.say(user)


        if event == self.session.protocol.IRCEvent.JOIN:
            if self.session.event_user_obj.nickname != self.session.nickname:
                self.session.say(f'Welcome to {self.session.event_target_obj}, {self.session.event_user_obj.nickname}!')


        if event == self.session.protocol.IRCEvent.MODE:
            if str(self.session.event_target_obj)[0] in self.session.protocol.support['CHANTYPES']:
                # Ensure channel mode.
                pass
                #self.session.say(f'You changed the channel mode to: {data}')


        if event == self.session.protocol.IRCEvent.KICK:
            """
            IRCEvent.KICK data is a tuple. At index 0 is the user object being kicked.
            At index 1 is the reason for the kick.
            """
            kicked_user = data[0]
            reason = data[1]
            self.session.say(f"Why did you kick {kicked_user}?!")
            self.session.say(f"'{reason}' is not a good reason! :(")

    def stop(self):
        print('stop module')
        self.active = 0



class SomeTimer(threading.Thread):
    def __init__(self, module, session):
        self.session = session
        self.module = module
        self.kill = threading.Event()
        threading.Thread.__init__(self)

    def run(self):
        while self.module.active:
            print('This will run forever every 55675 seconds,\nas long as the module is running, or the loop breaks.')
            time.sleep(5)
        print('BYE!')
