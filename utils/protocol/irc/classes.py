"""
Protocol related classes.
"""

from utils.logger import logging

class User:
    def __init__(self, session, nickname):
        self.session = session
        self.nickname = nickname
        self.ident = ''
        self.cloakhost = ''
        self.realhost = ''
        self.session.users.append(self)
        logging.debug(f'Created user object for {self.nickname}')

    def quit(self):
        logging.debug(f'[QUIT] User {self} quit. Removed all user references.')
        self.session.users.remove(self)
        for chan in [chan for chan in self.session.channels if self in chan.users]:
            del chan.usermodes[self]
            chan.users.remove(self)
        del self

    def __repr__(self):
        return f'<User {self.nickname}>'

    def __str__(self):
        return f'{self.nickname}'


class Channel:
    def __init__(self, session, name):
        self.session = session
        self.name = name
        self.users = []
        self.topic = ''
        self.modes = ''
        self.usermodes = {}
        self.session.channels.append(self)
        logging.debug(f'Created channel object for {self.name}')

    def add_user(self, user_obj):
        if user_obj not in self.users:
            self.users.append(user_obj)
            logging.debug(f'Added {user_obj} to {self} users list.')
            self.usermodes[user_obj] = ''

    def remove_user(self, user_obj):
        logging.debug(f'Removing user {user_obj} from channel {self}')
        self.users.remove(user_obj)
        logging.debug('Removing usermodes')
        del self.usermodes[user_obj]
        if user_obj.nickname == self.session.nickname:
            self.session.channels.remove(self)
            logging.debug('self remove, destroying channel.')
            del self

        else:
            shared_channels = [c for c in self.session.channels if user_obj in c.users]
            if not shared_channels:
                logging.debug(f'I do not share any channels with {user_obj} anymore.')
                logging.debug(f'Removing all known user data.')
                user_obj.quit()

    def __repr__(self):
        return f'<Channel {self.name}>'

    def __str__(self):
        return f'{self.name}'
