import os
from utils.logger import logging


class IRCSettingsError(Exception):
    pass


def check_settings(session):
    """
    Settings checker for IRC protocol.
    """
    req_attributes = {"nickname": str, "server": str, "port": int}
    missing_attributes = []
    for item in [item for item in req_attributes if not hasattr(session, item)]:
        missing_attributes.append(item)

    if missing_attributes:
        missing_attributes_string = ', '.join(missing_attributes)
        error = f"Your session is missing the following required attributes: {missing_attributes_string}"
        raise IRCSettingsError(error)

    for attr in [attr for attr in session.__dict__.keys() if attr in req_attributes]:
        is_type = type(getattr(session, attr))
        req_type = req_attributes[str(attr)]
        if is_type != req_type:
            error = f"Wrong type for required attribute {attr}: {is_type} != {req_type}"
            raise IRCSettingsError(error)


    # Checking optional attributes.
    optional_attributes = {"channel": str, "alt_nick": str, "cert": str}
    for attr in [attr for attr in session.__dict__.keys() if attr in optional_attributes]:
        is_type = type(getattr(session, attr))
        req_type = optional_attributes[str(attr)]
        if is_type != req_type:
            error = f"Wrong type for optional attribute {attr}: {is_type} != {req_type}"
            raise IRCSettingsError(error)

    if hasattr(session, 'cert'):
        if not os.path.isfile(session.cert):
            error = f"You provied a TLS cert, but the file could not be found: {session.cert}"
            raise IRCSettingsError(error)
        if not hasattr(session, 'tls') or not session.tls:
            logging.warning("You provided a TLS cert, but you have not enabled the TLS flag.")
