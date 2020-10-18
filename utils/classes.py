"""
Main classes.
"""

import threading
import select
import enum
import ssl
import socket

from utils import protocol
from utils.logger import logging


class AbstractClass(threading.Thread):
    sessions = []

    def activate_session(self):
        """
        Main method of activating sessions with different protocols.
        """
        logging.debug(f'Session activated for {self}')
        self.sessions.append(self)
        self.active = 1
        self.protocol.conn_established() # Call conn_established() method on protocol object to trigger events.
        self._get_new_events()
        logging.info('Stopped listening for events.')

    def _get_new_events(self):
        while self.active:
            try:
                read, write, error = select.select([s for s in self.sessions if s.active and s.sock.fileno() != -1], [], [], 10.0)
            except Exception as ex:
                logging.exception(ex)
                break  # Kill connection..

            for session in read:
                if session.logging:
                    logging.enable()
                else:
                    logging.disable()
                try:
                    recv = session.sock.recv(4096).decode('utf-8')
                except UnicodeDecodeError:
                    recv = session.sock.recv(4096).decode('latin-1')
                except (OSError, ConnectionResetError) as ex:
                    logging.exception(ex)
                    session.quit()
                    continue

                if not recv:
                    session.quit()
                    continue

                session.protocol.get_events(recv)

    def sendline(self, data):
        if not self.active:
            return
        try:
            self.sock.send(bytes(data + '\r\n', 'utf-8'))
            logging.info(f'<< {data}')
        except Exception as ex:
            logging.exception(ex)
            self.quit()

    def say(self, text, target=None):
        """
        Base say(). We place it here, and not in Session(), because different protocols use different
        ways to send a message to the other end.
        """
        if str(self.protocol) == "IRC":
            self.protocol.say(text, target)

    def quit(self, reason=None):
        self.protocol.quit()
        if str(self.protocol) == "IRC" and self.connected:
            pass
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except:
            pass
        self.sock.close()
        self.active = 0
        self.connected = 0
        if self in self.sessions:
            self.sessions.remove(self)
        else:
            logging.info(f'{self} not found in sessions list: {self.sessions}')
        logging.info(f'Session {self} closed.')

    def fileno(self):
        return self.sock.fileno()
