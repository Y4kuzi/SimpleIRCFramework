import logging
import logging.handlers
import time
import datetime
import os

W = '\033[0m'  # white (normal)
R = '\033[31m'  # red
R2 = '\033[91m'  # bright red
Y = '\033[33m'  # yellow


class EnhancedRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    def __init__(self, filename, when='midnight', interval=1, backupCount=0, encoding=None, delay=0, utc=0, maxBytes=0, backupExpire=0):
        """ This is just a combination of TimedRotatingFileHandler and RotatingFileHandler (adds maxBytes to TimedRotatingFileHandler) """
        logging.handlers.TimedRotatingFileHandler.__init__(self, filename, when, interval, backupCount, encoding, delay, utc)

        self.maxBytes = maxBytes if maxBytes <= 1000 * 100000 else 1000 * 100000  # Limit single file to max. 100MB
        self.suffix = '%Y-%m-%d'
        self.filename = filename
        self.backupExpire = backupExpire if backupExpire <= 315569260 else 315569260  # Limit expire to max. 10 years.
        self.backupCount = backupCount if backupCount <= 999 else 999

    def shouldRollover(self, record):
        """
        Determine if rollover should occur.

        Basically, see if the supplied record would cause the file to exceed
        the size limit we have.

        we are also comparing times
        """

        if self.stream is None:  # Delay was set...
            self.stream = self._open()
        if self.maxBytes > 0:  # Are we rolling over?
            msg = "%s\n" % self.format(record)
            self.stream.seek(0, 2)  # Due to non-posix-compliant Windows feature
            if self.stream.tell() + len(msg) >= self.maxBytes:
                return 1
        if int(time.time()) >= self.rolloverAt:
            return 1
        return 0

    def doRollover(self):
        """
        Do a rollover, as described in __init__().
        """
        if self.stream:
            self.stream.close()
            self.stream = None
        if self.backupCount > 0:
            d = datetime.datetime.today().strftime(self.suffix)
            for i in range(self.backupCount - 1, 0, -1):
                n = "%03d" % (i)
                sfn = self.rotation_filename("%s.%s.%03d" % (self.baseFilename, d, int(n)))
                dfn = self.rotation_filename("%s.%s.%03d" % (self.baseFilename, d, int(n) + 1))
                if os.path.exists(sfn):
                    if os.path.exists(dfn):
                        os.remove(dfn)
                    os.rename(sfn, dfn)
            dfn = self.rotation_filename(self.baseFilename + "." + d + ".001")
            if os.path.exists(dfn):
                os.remove(dfn)
            self.rotate(self.baseFilename, dfn)
            self.deleteOldFiles()
        if not self.delay:
            self.stream = self._open()

        currentTime = int(time.time())
        dstNow = time.localtime(currentTime)[-1]
        newRolloverAt = self.computeRollover(currentTime)

        t = self.rolloverAt - self.interval
        if self.utc:
            timeTuple = time.gmtime(t)
        else:
            timeTuple = time.localtime(t)
            dstThen = timeTuple[-1]
            if dstNow != dstThen:
                if dstNow:
                    addend = 3600
                else:
                    addend = -3600
                timeTuple = time.localtime(t + addend)

        while newRolloverAt <= currentTime:
            newRolloverAt = newRolloverAt + self.interval

        if (self.when == 'MIDNIGHT' or self.when.startswith('W')) and not self.utc:
            dstAtRollover = time.localtime(newRolloverAt)[-1]
            if dstNow != dstAtRollover:
                if not dstNow:  # DST kicks in before next rollover, so we need to deduct an hour
                    addend = -3600
                else:  # DST bows out before next rollover, so we need to add an hour
                    addend = 3600
                newRolloverAt += addend
        self.rolloverAt = newRolloverAt

    def deleteOldFiles(self):
        dirName, baseName = os.path.split(self.baseFilename)
        files = os.listdir(dirName)
        for file in [file for file in files if os.path.join(dirName, file) != self.baseFilename]:
            fn = os.path.join(dirName, file)
            if not os.path.isfile(fn):
                continue
            logtimestamp = int(os.path.getmtime(fn))  # Based on last modify.
            diff = int(time.time()) - logtimestamp
            if self.backupExpire and diff > self.backupExpire:
                os.remove(fn)
                continue

            oldest = [os.path.join(dirName, f) for f in files if os.path.isfile(os.path.join(dirName, f))]
            oldest.sort(key=lambda f: int(os.path.getmtime(f) * 1000))

            exceed = len(oldest) - self.backupCount
            if exceed > 0:
                remove_files = oldest[:exceed]
                for f in remove_files:
                    os.remove(f)


def initlogging():
    if not os.path.exists('logs'):
        os.mkdir('logs')
    filename = 'logs/session.log'

    # Removing files >backupCount OR >backupExpire (in seconds)
    loghandlers = [EnhancedRotatingFileHandler(filename, when='midnight', maxBytes=1000 * 1000, backupCount=30, backupExpire=2629744)]  # 2629744 = 1 month
    stream = logging.StreamHandler()
    # stream.setLevel(logging.DEBUG)
    stream.terminator = '\n' + W
    loghandlers.append(stream)

    formatter = '%(asctime)s %(levelname)s [%(module)s]: %(message)s'  # +W
    logging.basicConfig(level=logging.DEBUG, format=formatter, datefmt='%Y/%m/%d %H:%M:%S', handlers=loghandlers)
    logging.addLevelName(logging.WARNING, Y + "%s" % logging.getLevelName(logging.WARNING))
    logging.addLevelName(logging.ERROR, R2 + "%s" % logging.getLevelName(logging.ERROR))
    logging.addLevelName(logging.INFO, "%s" % logging.getLevelName(logging.INFO))
    logging.addLevelName(logging.DEBUG, "%s" % logging.getLevelName(logging.DEBUG))
    l = loghandlers[0]
    logging.debug('Logger initialised with settings:')

    mb_file = l.maxBytes * l.backupCount
    mb_file = mb_file / l.backupCount
    mb_file = float(mb_file) / 1000 / 1000
    mb_file = "%.2f" % mb_file
    logging.debug('maxBytes: {} ({} MB per file)'.format(l.maxBytes, mb_file))

    logging.debug('backupCount: {}'.format(l.backupCount))

    sec = datetime.timedelta(seconds=l.backupExpire)
    d = datetime.datetime(1, 1, 1) + sec
    logging.debug('backupExpire: {} ({} years, {} months, {} days)'.format(l.backupExpire, d.year - 1, d.month - 1, d.day - 1))

    max_size = l.maxBytes * (l.backupCount + 1)  # Include base file.
    mb_size = float(max_size) / 1000 / 1000
    mb_size = "%.2f" % mb_size
    logging.debug('Max possible total logs size: {} bytes ({} MB)'.format(max_size, mb_size))

    logging.debug('Logs will rotate log files with interval: {}'.format(l.when))

    if max_size > 1000000000:
        gb_size = float(mb_size) / 1000
        gb_size = "%.2f" % gb_size
        print('{}WARNING: Total log size limit exceeds 1GB: {} GB{}'.format(R, gb_size, W))
        print('Pausing for 5 seconds for visibility...')
        time.sleep(5)


if __name__ == "utils.logger":
    initlogging()
