#!/usr/bin/python3
#
# Copyright 2017 Peter Jones <Peter Jones@random>
#
# Distributed under terms of the GPLv3 license.

"""
This module provides abstractions for talking to serial ports.
"""
import array
from ctypes import c_uint, c_ubyte, Structure
import fcntl
import os
import pty
import tty
import termios

TCGETS2 = 0x802C542A
TCSETS2 = 0x402C542B

BOTHER = 0o010000
IBSHIFT = 16

class Termios2(Structure):
    """ This is a wrapper for struct termios2, because life is very sad """

    #
    # typedef unsigned char   cc_t;
    # typedef unsigned int    speed_t;
    # typedef unsigned int    tcflag_t;
    #
    # #define NCCS 19
    #
    # struct termios2 {
    #         tcflag_t c_iflag;               /* input mode flags */
    #         tcflag_t c_oflag;               /* output mode flags */
    #         tcflag_t c_cflag;               /* control mode flags */
    #         tcflag_t c_lflag;               /* local mode flags */
    #         cc_t c_line;                    /* line discipline */
    #         cc_t c_cc[NCCS];                /* control characters */
    #         speed_t c_ispeed;               /* input speed */
    #         speed_t c_ospeed;               /* output speed */
    # };

    _fields_ = [('c_iflag', c_uint),
                ('c_oflag', c_uint),
                ('c_cflag', c_uint),
                ('c_lflag', c_uint),
                ('c_line', c_ubyte),
                ('c_cc', c_ubyte * 19),
                ('c_ispeed', c_uint),
                ('c_ospeed', c_uint),
               ]

    def __init__(self):
        self.c_iflag = 0
        self.c_oflag = 0
        self.c_cflag = 0
        self.c_lflag = 0
        self.c_line = 0
        self.c_ispeed = 0
        self.c_ospeed = 0
        #self.c_cc = c_ubyte * 19
        Structure.__init__(self)

    def asbuf(self):
        """ This gives the structure as a buffer type """

        buf = array.array('I', [0] * int(self.__sizeof__() / 4))
        buf[0] = self.c_iflag
        buf[1] = self.c_oflag
        buf[2] = self.c_cflag
        buf[3] = self.c_lflag

        buf[4] = self.c_line         \
                |(self.c_cc[0] << 8) \
                |(self.c_cc[1] << 16)\
                |(self.c_cc[2] << 24)

        buf[5] = (self.c_cc[3])      \
                |(self.c_cc[4] << 8) \
                |(self.c_cc[5] << 16)\
                |(self.c_cc[6] << 24)

        buf[6] = (self.c_cc[7])      \
                |(self.c_cc[8] << 8) \
                |(self.c_cc[9] << 16)\
                |(self.c_cc[10] << 24)

        buf[7] = (self.c_cc[11])      \
                |(self.c_cc[12] << 8) \
                |(self.c_cc[13] << 16)\
                |(self.c_cc[14] << 24)

        buf[8] = (self.c_cc[15])      \
                |(self.c_cc[16] << 8) \
                |(self.c_cc[17] << 16)\
                |(self.c_cc[18] << 24)

        buf[9] = self.c_ispeed
        buf[10] = self.c_ospeed
        return buf

    def frombuf(self, buf):
        """ This reads the structure from a buffer type. """

        self.c_iflag = buf[0]
        self.c_oflag = buf[1]
        self.c_cflag = buf[2]
        self.c_lflag = buf[3]

        self.c_line = buf[4] & 0xff

        self.c_cc[0] = (buf[4] & 0xff00) >> 8
        self.c_cc[1] = (buf[4] & 0xff0000) >> 16
        self.c_cc[2] = (buf[4] & 0xff000000) >> 24
        self.c_cc[3] = (buf[5] & 0xff)

        self.c_cc[4] = (buf[5] & 0xff00) >> 8
        self.c_cc[5] = (buf[5] & 0xff0000) >> 16
        self.c_cc[6] = (buf[5] & 0xff000000) >> 24
        self.c_cc[7] = (buf[6] & 0xff)

        self.c_cc[8] = (buf[6] & 0xff00) >> 8
        self.c_cc[9] = (buf[6] & 0xff0000) >> 16
        self.c_cc[10] = (buf[6] & 0xff000000) >> 24
        self.c_cc[11] = (buf[7] & 0xff)

        self.c_cc[12] = (buf[7] & 0xff00) >> 8
        self.c_cc[13] = (buf[7] & 0xff0000) >> 16
        self.c_cc[14] = (buf[7] & 0xff000000) >> 24
        self.c_cc[15] = (buf[8] & 0xff)

        self.c_cc[16] = (buf[8] & 0xff00) >> 8
        self.c_cc[17] = (buf[8] & 0xff0000) >> 16
        self.c_cc[18] = (buf[8] & 0xff000000) >> 24

        self.c_ispeed = buf[9]
        self.c_ospeed = buf[10]

    def get(self, filedes):
        """ read our termios2 data from the file descriptor """

        buf = self.asbuf()
        fcntl.ioctl(filedes, TCGETS2, buf)
        self.frombuf(buf)

    def set(self, filedes):
        """ set the file descriptor's attributes from our termios2 data """
        buf = self.asbuf()
        fcntl.ioctl(filedes, TCSETS2, buf)

class SerialPort():
    """ This describes a serial port """

    baud_table = {
        0:termios.B0,
        50:termios.B50,
        75:termios.B75,
        110:termios.B110,
        134:termios.B134,
        150:termios.B150,
        200:termios.B200,
        300:termios.B300,
        600:termios.B600,
        1200:termios.B1200,
        1800:termios.B1800,
        2400:termios.B2400,
        4800:termios.B4800,
        9600:termios.B9600,
        19200:termios.B19200,
        38400:termios.B38400,
        57600:termios.B57600,
        115200:termios.B115200,
        230400:termios.B230400,
        460800:termios.B460800,
        500000:termios.B500000,
        576000:termios.B576000,
        921600:termios.B921600,
        1000000:termios.B1000000,
        1152000:termios.B1152000,
        1500000:termios.B1500000,
        2000000:termios.B2000000,
        2500000:termios.B2500000,
        3000000:termios.B3000000,
        3500000:termios.B3500000,
        4000000:termios.B4000000,
        }

    def __init__(self, name, use_pty=False):
        if name == "-":
            self.name = "/dev/stdin"
        else:
            self.name = name
        self.filedes = None
        self.device = None
        self.termios = Termios2()
        self._master_tty_path = None
        self._master_pty = None
        self._slave_tty_path = None
        self._slave_pty = None
        self.pty = use_pty

        self._open()

    @property
    def filedes(self):
        """ the file descriptor we should be doing i/o to """
        return self._master_pty

    def _open(self):
        """ Open our terminal and set it up as self.device / self.filedes """
        #print("tty_path: %s tty_speed: %s" % (self.tty_path, self.tty_speed))
        if self._master_tty_path is None:
            if self.pty:
                master, slave = pty.openpty()
                self._master_pty = master
                self._slave_pty = slave
                self._master_tty_path = os.readlink("/proc/self/fd/%d" %
                                                    (master,))
                self._slave_tty_path = os.readlink("/proc/self/fd/%d" %
                                                   (slave,))
            else:
                self._master_tty_path = self.name
                self._master_pty = os.open(self.name, os.O_RDWR)

        self.device = os.fdopen(self.filedes, "w+b", buffering=0)

    @property
    def tty_path(self):
        """ get the path for the tty device node """

        return self._master_tty_path

    @property
    def pty_path(self):
        """ Return the slave pty path if this is a pty """
        return self._slave_tty_path

    def set_speed(self, speed):
        """ Set the speed """

        if self.pty:
            return

        ifound = False
        ofound = False
        iclose = speed/50
        oclose = speed/50
        ibinput = False

        self.termios.get(self.filedes)

        self.termios.c_ispeed = self.termios.c_ospeed = speed

        if (self.termios.c_cflag & termios.CBAUD) == BOTHER:
            oclose = 0
        if ((self.termios.c_cflag >> IBSHIFT) & termios.CBAUD) == BOTHER:
            iclose = 0
        if (self.termios.c_cflag >> IBSHIFT) & termios.CBAUD:
            ibinput = True

        self.termios.c_cflag &= ~termios.CBAUD

        bauds = list(SerialPort.baud_table.keys())
        bauds.sort()
        for i in range(0, len(SerialPort.baud_table)):
            baud = bauds[i]
            bits = SerialPort.baud_table[baud]

            if speed - oclose <= baud and speed + oclose >= baud:
                self.termios.c_cflag |= bits
                ofound = i
            if speed - iclose <= baud and speed + iclose >= baud:
                if ofound == i and not ibinput:
                    ifound = i
                else:
                    ifound = i
                    self.termios.c_cflag |= bits << IBSHIFT
        if ofound is False:
            self.termios.c_cflag = BOTHER

        if ifound is False and ibinput:
            self.termios.c_cflag |= BOTHER << IBSHIFT

        self.termios.set(self.filedes)

    def getattr(self):
        """ Get our tty's attributes """
        attrs = tty.tcgetattr(self.filedes)
        return {'iflag':attrs[0],
                'oflag':attrs[1],
                'cflag':attrs[2],
                'lflag':attrs[3],
                'ispeed':attrs[4],
                'ospeed':attrs[5],
                'cc':attrs[6]}

__all__ = [
    "SerialPort",
]
