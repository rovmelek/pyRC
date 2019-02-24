from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import argparse
import re
# import sys
import json
import socket
# import urllib2
import logging
# import threading
import ssl
from urllib.request import urlopen
# from time import sleep
# from datetime import datetime, time
from configparser import ConfigParser, ExtendedInterpolation

# global variable
logger = logging.getLogger()
config = ConfigParser(interpolation=ExtendedInterpolation())


class stockService:
    """stock service"""
    def __init__(self, symbol):
        self.symbol = symbol
        self.APIKey = config.get('stock', 'key')
        self.url = config.get('stock', 'url').format(self.APIKey, self.symbol)
        logger.debug("{} {} {}".format(self.symbol, self.APIKey, self.url))

    def querySymbol(self):
        content = json.loads(urlopen(self.url).read())
        logger.debug("{}".format(content))
        return content


class ircService:
    """IRC connection service"""
    def __init__(self, **kwargv):
        self.server = config.get('irc', 'server')
        self.port = config.getint('irc', 'port')
        self.secure = config.getboolean('irc', 'ssl')
        self.ssl_port = config.getint('irc', 'ssl_port')
        self.channel = config.get('irc', 'channel')
        self.nick = config.get('irc', 'nick')
        self.passreq = config.getboolean('irc', 'passreq')
        self.password = config.get('irc', 'password')

    def connect(self):
        """connect to irc server"""
        logger.debug("IRC server/port: {}/{}".format(self.server, self.port))
        logger.debug("IRC secure connection: {}".format(self.secure))
        if self.secure:
            self.sock = ssl.wrap_socket(socket.socket(socket.AF_INET,
                                                      socket.SOCK_STREAM))
        else:
            self.sock = socket.socket(socket.AF_INET,
                                      socket.SOCK_STREAM)

        self.sock.connect((self.server, self.port))

        if self.passreq:
            self.sock.send(bytes("PASS " + self.password + "\n", "UTF-8"))
        logger.debug("Setup nick.")
        self.sock.send(bytes("NICK " + self.nick + "\n", "UTF-8"))
        userString = "USER {} {} {} " \
                     ":Python IRC bot " \
                     "https://github.com/rovmelek/pyRC.\n".format(self.nick,
                                                                  self.nick,
                                                                  self.nick)
        logger.debug("Setup user: {}".format(userString))
        self.sock.send(bytes(userString, "UTF-8"))

    def joinChannel(self):
        logger.debug("Try to join channel: {}".format(self.channel))
        self.sock.send(bytes("JOIN " + self.channel + "\n", "UTF-8"))

    def msgRecv(self):
        ircmsg = ""
        ircmsg = self.sock.recv(2048).decode()
        ircmsg = ircmsg.strip('\n\r')
        logger.debug("Received IRC message:\n{}".format(ircmsg))
        return ircmsg

    def msgSend(self, msg):
        self.sock.send(bytes(msg, "UTF-8"))
        logger.debug("Message sent: {}".format(msg))

    def parseMsg(self, msg):
        pattern = re.compile(r'^:(.*!.*@.*) PRIVMSG (.*) :(.*)$', re.I)
        matchObj = pattern.match(msg)

        if not matchObj:
            logger.debug("Ignore unknown message")
            return None, None, None

        return matchObj[1], matchObj[2], matchObj[3]


def run_stock(symbol):
    mystock = stockService(symbol)
    return mystock.querySymbol()


cmd_list = {
    "stock": run_stock,
}


def is_cmd(msgBody):
    pattern = re.compile(r'^!([a-zA-Z]+)(\s.*)?$', re.I)
    cmd_option = pattern.search(msgBody)
    if not cmd_option:
        logger.debug("{} is not a command".format(msgBody))
        return None, None

    cmd = cmd_option[1]
    option = cmd_option[2]

    if option:
        option = option.lstrip()

    logger.debug("Channel cmd: {} | "
                 "Channel option: {}".format(cmd, option))

    return cmd, option


def validate_cmd(cmd):
    if cmd in cmd_list.keys():
        logger.debug("{} is a valid cmd".format(cmd))
        return True
    else:
        logger.debug("{} is NOT a valid cmd".format(cmd))
        return False


def run_cmd(cmd, opt):
    func = cmd_list.get(cmd, lambda x: "Unknown command".format(cmd))
    return func(opt)


def setupLogger(args):
    """setup logger"""
    logFormatter = logging.Formatter("%(asctime)s - "
                                     "%(levelname)s - "
                                     "%(message)s")

    try:
        logFile = config.get('common', 'log_file')
    except BaseException:
        logFile = 'log/pyRC.log'
    fileHandler = logging.FileHandler(logFile)
    fileHandler.setFormatter(logFormatter)
    logger.addHandler(fileHandler)

    consoleHandler = logging.StreamHandler()
    consoleHandler.setFormatter(logFormatter)
    logger.addHandler(consoleHandler)

    if not args.verbose:
        logger.setLevel(logging.ERROR)
    elif args.verbose == 1:
        logger.setLevel(logging.WARNING)
    elif args.verbose == 2:
        logger.setLevel(logging.INFO)
    elif args.verbose >= 3:
        logger.setLevel(logging.DEBUG)
    else:
        logger.critical("Logging level is negative: {}".format(args.verbose))


def setupConfig(args):
    """read config file"""
    if args.cfgFile:
        cfgFile = args.cfgFile
    else:
        cfgFile = "pyRC.conf"

    config.read(cfgFile)


def main():
    """main loop"""
    myirc = ircService()
    myirc.connect()
    myirc.joinChannel()
    while True:
        msg = myirc.msgRecv()

        logger.debug("Parsing received message:\n==> {}".format(msg))

        if msg.startswith("PING :"):
            logger.debug("Server ping received. Replying pong...")
            myirc.msgSend("PONG :ping ping pong pong ping ping ping\r\n")
            # return to the message receive loop
            continue

        msgFrom, msgTo, msgBody = myirc.parseMsg(msg)

        logger.debug("\n==> msgFrom: {}"
                     "\n==> msgTo: {}"
                     "\n==> msgBody: {}".format(msgFrom, msgTo, msgBody))

        if msgBody:
            cmd, option = is_cmd(msgBody)

            if not cmd:
                continue

            # validate the command against cmd_list
            if not validate_cmd(cmd):
                returnTextTemplate = "PRIVMSG {} :Invalid command\r\n"
                if msgTo == myirc.channel:
                    returnText = returnTextTemplate.format(myirc.channel)
                else:
                    returnText = returnTextTemplate.format(msgFrom)
                logger.debug("\nSending returnText: {}".format(returnText))
                myirc.msgSend(returnText)
                continue

            if cmd and option:
                logger.debug("Processing cmd/option: {}/{}".format(cmd,
                                                                   option))
                # run function based on the cmd name
                output = run_cmd(cmd, option)
                returnTextTemplate = "PRIVMSG {} :{}\r\n"
                if msgTo == myirc.channel:
                    returnText = returnTextTemplate.format(myirc.channel,
                                                           output)
                else:
                    returnText = returnTextTemplate.format(msgFrom,
                                                           output)

                logger.debug("\nSending returnText: {}".format(returnText))

                myirc.msgSend(returnText)


if __name__ == "__main__":
    argParser = argparse.ArgumentParser()
    argParser.add_argument('-v', '--verbose',
                           action='count',
                           default=0,
                           help='Increase output verbosity.')
    argParser.add_argument('-c', '--cfgFile',
                           action='store',
                           dest='cfgFile',
                           default='pyRC.conf',
                           help='pyRC configuration file name.')
    args = argParser.parse_args()

    setupConfig(args)
    setupLogger(args)

    main()
