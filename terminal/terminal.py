#!/usr/bin/python3
#
# Copyright 2017 Peter Jones <Peter Jones@random>
#
# Distributed under terms of the GPLv3 license.
#

"""
This module provides abstractions for talking to a terminal.
"""

import os
import time
import selectors

from .serial import SerialPort

class Terminal(SerialPort):
    """ This provides a terminal we can write to """
    # pylint: disable=too-many-public-methods

    def __init__(self, name, use_pty=False):
        SerialPort.__init__(self, name, use_pty)
        print("[Terminal %s].__init__(name=\"%s\")" % (self.name, self.name))

        self.count = 0

        self.cur_x = 1
        self.cur_y = 1
        self.saved_x = 1
        self.saved_y = 1
        self.min_x = 1
        self.min_y = 1
        self.max_x = 80
        self.max_y = 24

        self.seen_valid_ps = False

        self.Pt = self.min_y
        self.Pb = self.max_y
        self.scroll_enabled = False

        self.cursor_saved = False

        self.autowrap = True
        self.autoscroll = True

        selector = selectors.PollSelector()
        selector.register(self.filedes,
                          selectors.EVENT_READ|selectors.EVENT_WRITE)
        self.selector = selector

    def _get_timeout(self, timeout=None):
        if timeout is None:
            return self.timeout
        return timeout


    def SM(self, modes, group=1):
        """ Set Mode
        mode: the mode number
        group: 1 means no ?, 2 means ?
        """
        modestr = "".join(("%d;" % (mode,) for mode in modes))[:-1]
        if group == 1:
            self.escape("[%sh" % (modestr,))
        elif group == 2:
            self.escape("[?%sh" % (modestr,))
        else:
            raise ValueError("SM: no such group %s" % (group,))

    def RM(self, modes, group=1):
        """ Reset Mode
        mode: the mode number
        group: 1 means no ?, 2 means ?
        """
        modestr = "".join(("%d;" % (mode,) for mode in modes))[:-1]
        if group == 1:
            self.escape("[%sl" % (modestr,))
        elif group == 2:
            self.escape("[?%sl" % (modestr,))
        else:
            raise ValueError("SM: no such group %s" % (group,))

    def mode(self, mode, enable, group=1):
        """ Set or Reset mode
        mode: the mode number
        enable: True = Set False = Reset
        group: 1 means no ?, 2 means ?
        """
        if enable:
            self.SM((mode,), group)
        else:
            self.RM((mode,), group)

    def DECANM(self, enable: bool):
        """ Put the terminal in ANSI mode """
        #print("DECANM(%s) (ansi mode)" % (enable,))

        # WYSE 60 manual says this works:
        #self.escape('<')
        self.mode(2, enable, group=2)
        self.fill(2)

    def DECSCLM(self, enable: bool):
        """ DECSCLM - Select scroll mode
        True: smooth scroll
        False: sane scroll (jumpy)
        """

        #print("DECSCLM(%s) (scroll mode)" % (enable,))
        self.mode(4, enable, group=2)
        self.fill(2)

    def DECOM(self, enable: bool):
        """ DECOM - Set origin mode
        True - cursor is confined to scroll region
        False: CUP() and HVP() work
        """

        #print("DECOM(%s) (origin mode)" % (enable,))
        self.mode(6, enable, group=2)
        self.fill(2)

    def CRM(self, enable: bool):
        """ RM [3h/[3l - CRM: Are control characters displayable
        True - display control characters somehow
        False - do the reasonable thing
        """

        #print("CRM(%s) (display control chars)" % (enable,))
        self.mode(3, enable)
        self.fill(self.speed / 20)

    def SRTM(self, enable: bool):
        """ SM [5h/[5l - SRTM - Status Report Transfer Mode
        True - report whenever?
        False - report only after DCS
        """
        #print("SRTM(%s) (status report transfer mode)" % (enable,))
        self.mode(5, enable)
        self.fill(self.speed / 20)

    def SVT100(self):
        """ (wyse) Select VT100 personality """
        #self.escape("~;")
        #print("Select VT100 mode")
        self.mode(44, True)
        self.fill(self.speed / 20)

    def StatusLine(self, enable: bool):
        """ (wyse) Status Line enable
        True: show that thing
        False: gimme that screen line
        """

        #if extended and enable:
        #    print("StatusLine(%s,%s)" % (enable, extended))
        #else:
        #    print("StatusLine(%s)" % (enable,))
        self.mode(31, enable)
        #if enable:
        #    if extended:
        #        self.escape("`a")
        #    else:
        #        self.escape("`b")
        #else:
        #    self.escape("`c")
        self.fill(self.speed)

    def setup(self):
        """ Actually set up the terminal for drawing to """
        self.RIS()

        #self.escape("<")
        #time.sleep(1.5)

        self.StatusLine(False)
        self.ED(True, True)
        self.SVT100()
        self.DECANM(True)
        self.DECSCLM(False)
        self.DECOM(False)
        self.CRM(False)
        self.SRTM(False)

        self.CUP(force=True)
        self.fill(self.speed / 10)
        x, y = self.getpos()
        self.fill(self.speed / 10)
        self.min_x = x
        self.CUP(x, x, force=True)
        self.fill(self.speed / 20)
        x, y = self.getpos()
        self.fill(self.speed / 20)
        self.min_y = y

        for x in range(0, 30):
            #print("%d " % (x,),)
            self.NEL()

        self.check_position()

        self.fill(self.speed / 20)
        x, y = self.getpos()
        self.fill(self.speed / 20)
        if y > self.max_y:
            self.max_y = y

        self._write(" " * 999)
        self.fill(self.speed / 20)
        x, y = self.getpos()
        self.fill(self.speed / 20)
        if x > self.max_x:
            self.max_x = x

        self.fill(self.speed / 20)
        if not self.scroll_enabled:
            self.Pt = self.min_y
            self.Pb = self.max_y

        #print("min xy is (%d, %d) max xy is (%d, %d)" % (self.min_x,
        #                                                 self.min_y,
        #                                                 self.max_x,
        #                                                 self.max_y))

        self.fill(self.speed / 20)
        self.clear()
        self.fill(self.speed / 20)
        self.gohome()

        # print("checking position")
        self.set_position(self.min_x, self.min_y)

    @property
    def x(self):
        """ current x position """
        return self.cur_x

    @property
    def y(self):
        """ current y position """
        return self.cur_y

    def check_position(self):
        """ Get the position from the terminal and ensure that we're at the
        right place."""

        x, y = self.getpos()
        if x != self.cur_x or y != self.cur_y:
            print("Current position is (%d,%d), expected (%d,%d).  Moving."
                  % (x, y, self.cur_x, self.cur_y))
            self.gotoxy(self.cur_x, self.cur_y, force=True)

    def set_position(self, x, y):
        """ Set our internal idea of the current position """
        self.cur_x = x
        if x > self.max_x:
            self.cur_x = self.max_x

        self.cur_y = y
        if y > self.max_y:
            self.cur_y = self.max_y

        self.check_position()
        #try:
        #    self.check_position()
        #except ValueError:
        #    self.drain()
        #    self.set_position(x, y)

    def decrement_line(self, n: int = 1):
        """ Move our internal representation of position up one row """
        self.cur_y -= n
        if self.cur_y < self.min_y:
            self.cur_y = self.min_y
        if self.scroll_enabled and self.cur_y == self.Pt - 1:
            self.cur_y = self.Pt

    def decrement_row(self, n: int = 1):
        """ Move our internal representation of position up one row """
        self.decrement_line(n)

    def increment_line(self, n: int = 1):
        """ Move our internal representation of position down one row """
        self.cur_y += n
        if self.cur_y > self.max_y:
            self.cur_y = self.max_y
        if self.scroll_enabled and self.cur_y == self.Pb + 1:
            self.cur_y = self.Pb

    def increment_row(self, n: int = 1):
        """ Move our internal representation of position down one row """
        self.increment_line(n)

    def decrement_col(self, n: int = 1):
        """ Move our internal representation of position left one col """
        self.cur_x -= n
        if self.cur_x < self.min_x:
            self.cur_x = self.min_x

    def increment_col(self, n: int = 1):
        """ Move our internal representation of position right one col """
        self.cur_x += n
        if self.cur_x > self.max_x:
            self.cur_x = self.max_x

    def _write(self, buf, timeout=None):
        """ A proxy for SerialPort.write() """

        return SerialPort.write(self, buf, timeout)

    def write(self, buf, timeout=None, limit=None):
        """ Write text to the screen """
        # pylint: disable=arguments-differ

        #print("doing write")
        if limit is None:
            limit = self.max_x - self.x
        l = min(len(buf), limit)
        buf = buf[:l]
        # we are clearing by writing spaces, which really sucks, but we
        # don't have explicitly bounded line clears.
        # probably we should determine if this is the left or right and use
        # one of the partial line clears (from start, to end) instead?  But
        # that won't help for the middle.
        if l < limit:
            sl = limit - l
        else:
            sl = 0
        buf += " " * sl
        self.increment_col(sl)

        # print("len(%s): %s" % (ns, len(ns)))
        self._write(buf)
        self.increment_col(l)
        sl = len(buf)
        ls = 0
        while buf:
            try:
                nl = buf.index('\n')
                self.increment_row()
                buf = buf[nl+1:]
                ls += 1
            except ValueError:
                break

        # print("write() %d characters, %d newlines: " % (nsl, nls))
        # print("\"%s\"" % (ns.strip()))
        self.check_position()

    def escape(self, s=""):
        """ Write an escaped character """
        # print("s: \"%s\"" % (s,))
        s = "\x1b%s" % (s,)
        self._write(s)

    def fill(self, n, obey_our_dec_masters=False):
        """ Write n NUL chararacters to the terminal to delay it... """
        if self.pty:
            return
        if obey_our_dec_masters:
            # DEC says to write NUL a bunch.  Results do not seem to be good.
            self._write("\x00" * n)
        else:
            speed = self.get_speed()
            # nerf it up /just a little/
            t = (n * 1.2) / speed
            # print("sleeping %d/19200 = %f" % (n * 1.2, t))
            time.sleep(t)

    def read_Ps_response(self, terminator: chr, starter: chr = '[',
                         timeout=None):
        """ read a series of integer values of the flavor:
        ESC terminator
        ESC starter terminator
        ESC starter Ps terminator
        ESC starter Ps ; terminator
        ESC starter Ps ; Ps terminator
        ESC starter Ps ; Ps ; ... terminator
        """
        # pylint: disable=too-many-nested-blocks,too-many-branches

        timeout = self._get_timeout(timeout)
        states = [
            "\x1b",
            "%c" % (starter,),
            "0123456789;%c" % (terminator,),
        ]
        count = 0
        val = 0
        returns = []
        seen_val = False
        terminated = False

        selector = selectors.PollSelector()
        selector.register(self.filedes, selectors.EVENT_READ)

        while not terminated:
            events = selector.select(timeout=self._get_timeout())
            if not events:
                # print("read_Ps_response(): events: %s" % (events,))
                count += 1
                if count == 4:
                    raise TimeoutError(timeout * count)
                continue

            # print("states: %s" % (states,))
            for key, mask in events:
                if mask & selectors.EVENT_READ:
                    c = os.read(key.fd, 1).decode('utf8')
                    # print("read_Ps_response: read '%c'" % (c,))
                    count = 0
                    if c in states[0]:
                        if len(states) > 1:
                            states.pop(0)
                            continue
                        elif c == ';':
                            if seen_val:
                                returns.append(val)
                                val = 0
                                seen_val = False
                            continue
                        elif c == terminator:
                            if seen_val:
                                returns.append(val)
                            terminated = True
                            break
                        if len(states) == 1:
                            seen_val = True
                            val *= 10
                            val += int(c)
                    else:
                        if self.seen_valid_ps:
                            print("unexpected character '\\x%02x'" % (ord(c),))
                        else:
                            time.sleep(0.2)
                        continue
        selector.close()
        if returns:
            self.seen_valid_ps = True
        return returns

    def _CPR(self):
        """ Cursor Position Report - vt100 to host """

        y = 1
        x = 1
        values = self.read_Ps_response(terminator='R')
        if values:
            y = values.pop(0)
        if values:
            x = values.pop(0)

        while values:
            val = values.pop(0)
            print("CPR: unexpected value %d\n" % (val,))
        return (x, y)

    def CPR(self):
        """ Cursor Position Report - vt100 to host """
        try:
            #print("CPR()",)
            x, y = self._CPR()
            #print("(x, y) = (%d, %d)" % (x, y))
            return x, y
        except ValueError as e:
            print("ValueError: %s" % (e,))
            # self.drain()
            # time.sleep(0.1)

    def CUU(self, n: int = 1):
        """ CUU - Cursor Up - move cursor up (y-=n) - DEC is terrible """
        n = int(n)
        #print("CUU(%d)" % (n,))
        self.escape("%dA" % (n,))
        self.decrement_row(n)

    def CUD(self, n: int = 1):
        """ Cursor Down - move cursor down (y+=n) """
        n = int(n)
        #print("CUD(%d)" % (n,))
        self.escape("%dB" % (n,))
        self.decrement_row(n)

    def CUF(self, n: int = 1):
        """ Cursor Foward - move the cursor right (x+=n) """
        n = int(n)
        #print("CUF(%d)" % (n,))
        self.escape("%dC" % (n,))
        self.increment_col(n)

    def CUB(self, n=1):
        """ Cursor Backward - move the cursor left (x-=n) """
        n = int(n)
        #print("CUB(%d)" % (n,))
        self.escape("%dD" % (n,))
        self.decrement_col(n)

    def _CUP_and_HVP(self, cmd, x: int = None, y: int = None, force=False):
        """ implement CUP and HVP """
        # This is awesomely backwards - first param is which line, second is
        # which column.

        if x is None and y is None:
            self.escape("[%c" % (cmd,))
            self.fill(4)
            self.set_position(1, 1)
            return

        x = int(x)
        y = int(y)
        if not force:
            if x < self.min_x:
                raise ValueError("x %d < min %d" % (x, self.min_x))
            if x > self.max_x:
                raise ValueError("x %d > max %d" % (x, self.max_x))
            if y < self.min_y:
                raise ValueError("y %d < min %d" % (y, self.min_y))
            if y > self.max_y:
                raise ValueError("y %d > max %d" % (y, self.max_y))

            if x == self.x and y == self.y:
                self.count += 1
                if self.count > 5:
                    raise RuntimeError
                return
        self.count = 0

        self.escape("[%d;%d%c" % (y, x, cmd))
        self.fill(self.speed / 5)
        #time.sleep(0.1)

    def CUP(self, x: int = None, y: int = None, force=False):
        """ CUP - Cursor Position - move the cursor to (x, y) """
        #print("CUP(%s,%s,%s)" % (x, y, force))
        self._CUP_and_HVP('H', x, y, force)
        if not force and x is not None and y is not None:
            self.set_position(x, y)

    def DA(self):
        """ Query device attributes """
        self.escape("0c")

        c = os.read(self.filedes, 5).decode('utf8')
        if c != "\x1b[?1;":
            raise ValueError("\"%s\" should be \"\\x1b[?1;\"" % (c,))

        c = os.read(self.filedes, 2).decode('utf8')
        if c[1] != 'c':
            raise ValueError("\\x%02x should be [" % (c[1],))

        answers = [
            "No options",
            "Processor Option (STP)",
            "Advanced video option (AVO)",
            "AVO and STP",
            "Graphics option (GPO)",
            "GPO and STP",
            "GPO and AVO",
            "GPO, STP, and AVO",
            ]

        c = int(c[0])
        if c > 7:
            raise ValueError("%d should be 0..7" % (c,))

        return answers[c]

    # skipping all the dec private codes...
    # DECALN - Screen Alignment display  - ESC # 8 - print a bunch of E's
    # DECANM Ps for SM/RM to enable/disable VT52 vs ANSI
    # DECARM Ps for SM/RM to enable/disable key-repeat
    # DECAWM Ps for SM/RM to enable/disable autowrap
    # DECCKM Ps for SM/RM to toggle between ANSI (0) and app function (1)
    #        for cusror keys in DECKPAM or DECANM modes
    # DECCOLM Ps for SM/RM  to toggle between 80 (0) and 132 (1) cols
    # DECDHL Double Heigh Line
    #        top - ESC # 3
    #        bottom ESC # 4
    # DECDWL - Double Width Line - ESC # 6
    # DECID - ESC Z - Use DA instead
    # DECINLM - Interlace Mode - Ps for SM/RM toggles 240 vs 480 scan lines
    # DECKPAM - ESC = - keypad application mode
    # DECKPNM - ESC > - keypad numeric mode
    # DECLL - ESC [ Ps q -- Load LEDs - 0 - clear, 1-4 - enable LED Ps.
    # DECOM - origin mode Ps for SM/RM - makes margins effect cursor origin
    # DECRC - ESC 8 - Restore Cursor
    # DECREPTPARM - ESC[<sol>;<par>;<nbits>;<xspeed>;<rspeed>;<clkmul>;<flags>x
    # DECREQTPARM - ESC [ <sol> x
    # DECSC - ESC 7 - save cursor
    # DECSCLM - scrolling mode - Ps for SM/RM 0=jump, 1=smooth
    # DESCSCNM - screen mode - Ps for SM/RM 0=white on black, 1=BonW
    # DECSTBM - ESC [ Pn ; Pn r - set top and bottom margins (scroll region)
    # DECSWL - ESC # 5 - single width line

    # DECTST - ESC [ 2 ; Ps y - invoke confidence test

    def _DSR(self, n: int = 0):
        """ Device Status Report """
        self.escape("[%dn" % (n,))
        self.fill(2000)
        if n == 5:
            dsr = os.read(self.filedes, 4).decode('utf8')
            if dsr[0:2] != "\x1b[" or dsr[3] != 'n':
                raise ValueError("\"%s\" should be \"\\x1b[Pn\"" % (dsr,))
            return int(dsr[2])
        elif n == 6:
            try:
                return self.CPR()
            except TimeoutError:
                print("CPR timed out; re-issuing DSR")
                self.drain()
                return self._DSR(n)

    def DSR(self, n: int = 0):
        """ Device Status Report """
        #print("DSR(%d)" % (n,))
        return self._DSR(n)

    def ED(self, erase_from_start=False, erase_to_end=False):
        """ Erase In Display """

        if (erase_from_start and erase_to_end) or \
                (not erase_from_start and not erase_to_end):
            #print("ED(2)")
            self.escape("[%dJ" % (2,))
        elif erase_from_start:
            #print("ED(1)")
            self.escape("[%dJ" % (1,))
        elif erase_to_end:
            #print("ED(0)")
            self.escape("[%dJ" % (0,))
        self.fill(104)
        self.fill(19200 / 5)

    def EL(self, erase_from_start=False, erase_to_end=False):
        """ Erase In Line """

        if (erase_from_start and erase_to_end) or \
                (not erase_from_start and not erase_to_end):
            #print("EL(2)")
            self.escape("[%dK" % (2,))
        elif erase_from_start:
            #print("EL(1)")
            self.escape("[%dK" % (1,))
        elif erase_to_end:
            #print("EL(0)")
            self.escape("[%dK" % (0,))
        self.fill(80)

    def HTS(self):
        """ Horizontal Tab Set (at current position) """
        self.escape("H")

    def HVP(self, x: int = None, y: int = None, force=False):
        """ Horizontal and Vertical Position - aka CUP """
        self._CUP_and_HVP('f', x, y, force)
        self.set_position(x, y)

    def IND(self):
        """ Index - move active position one line down, scroll if bottom """
        #print("IND")
        self.escape("D")
        self.fill(32)
        self.increment_line()

        self.check_position()

    def NEL(self):
        """ Next Line - move the active position to the first character of the
        next line, scrolling if needed """
        #print("NEL")
        self.escape("E")
        fill = 32
        if self.scroll_enabled:
            if self.cur_y == self.Pb:
                fill *= (self.Pb - self.Pt + 1)
        elif self.cur_y == self.max_y:
            fill *= self.max_y

        fill *= 2

        self.fill(fill)
        self.increment_line()
        self.cur_x = self.min_x

    def RI(self):
        """ Reverse Index - move active position up one line, scroll if needed
        """
        #print("RI")
        self.escape("M")
        self.fill(32)
        self.decrement_line()

        self.check_position()

    def RIS(self):
        """ Reset To Initial State """
        #print("RIS")
        # reset the terminal the proper DEC way
        self.escape("c")
        self.escape("c")
        self.escape("c")
        self.fill(19200*8)

    # skipping...
    #def RM(self):
    #    """ Reset Mode - ESC [ Ps;Ps;...;Ps / """
    #
    #def SCS(self):
    #    """ Select Character Set """
    #

    def SGR(self, **kwargs):
        """ SGR - Select Graphic Rendition - Set a character attribute """
        attributes = {
            "attributes_off": "0",  # vt100 vt102 w60
            "bold": "1",            # vt100 vt102 w60
            "dim": "2",             #             w60
            "underline": "4",       # vt100 vt102 w60
            "blink": "5",           # vt100 vt102 w60
            "reverse": "7",         # vt100 vt102 w60
            "invisible": "8",       #             w60
            "normal": "22",         #             w60
            "underline_off": "24",  #             w60
            "blink_off": "25",      #             w60
            "reverse_off": "27",    #             w60
        }

        keys = set(kwargs.keys())
        if keys.issuperset(set(["bold", "dim"])) or \
                keys.issuperset(set(["bold", "invisible"])) or \
                keys.issuperset(set(["dim", "invisible"])):
            raise ValueError("bold, dim, and invisible cannot be combined")

        params = ""
        for key in kwargs:
            if not key in attributes:
                raise TypeError(
                    "%s() got an unexpected keyword argument '%s'" %
                    (__name__, key))
            params += "%s;" % (attributes[key],)

        if params.endswith(";"):
            params = params[:-1]
        else:
            params = "0"

        self.escape("[%sm" % (params,))

    def TBC(self, Ps=0):
        """ Tabular Clear -- 0 clears current position, 3 clears all """
        self.escape("[%dg" % (Ps,))

    def set_autowrap(self, enable=True):
        """ autowrap
        True: do wrap
        False: don't wrap
        """
        self.autowrap = enable
        self.mode(7, enable, group=2)
        self.fill(2)

    def cursor_save(self):
        """ save the current cursor position """
        #print("doing cursor_save")
        if self.cursor_saved:
            #print("doing cursor_save_with_attrs")
            return
        self.saved_x = self.cur_x
        self.saved_y = self.cur_y
        self.cursor_saved = True
        #print("save(%d,%d)" % (self.cur_x, self.cur_y))
        self.escape("[s")
        self.fill(2)

    def cursor_restore(self):
        """ restore the cursor position from previously saved """
        #print("doing cursor_restore")
        self.cur_x = self.saved_x
        self.cur_y = self.saved_y
        #print("restore(%d,%d)" % (self.cur_x, self.cur_y))
        self.escape("[u")
        self.fill(2)
        self.check_position()

    def cursor_save_with_attrs(self):
        """ save the current cursor position and attrs """
        if self.cursor_saved:
            #print("doing cursor_save_with_attrs")
            return
        #print("doing cursor_save_with_attrs")
        self.saved_x = self.cur_x
        self.saved_y = self.cur_y
        self.cursor_saved = True
        #print("save(%d,%d)" % (self.cur_x, self.cur_y))
        self.escape("7")
        self.fill(self.speed * 0.01)

    def cursor_restore_with_attrs(self):
        """ restore the cursor position and attrs from previously saved """
        if self.cursor_saved:
            #print("doing cursor_restore_with_attrs")
            pass
        else:
            #print("doing cursor_restore_with_attrs but not saved before")
            pass
        self.cur_x = self.saved_x
        self.cur_y = self.saved_y
        #print("restore(%d,%d)" % (self.cur_x, self.cur_y))
        self.escape("8")
        self.fill(self.speed * 0.01)
        self.check_position()

    def set_alt_keypad_mode(self, enabled=True):
        """ numlock """
        if enabled:
            self.escape('=')
        else:
            self.escape('>')

    def gotoxy(self, x=None, y=None, force=False):
        """ Go to (x, y) """
        self.CUP(x, y, force)
        self.fill(2)

    def getpos(self):
        """ get current (x, y) """
        ret = self.DSR(6)
        if ret[0] > self.max_x:
            self.max_x = ret[0]
        if ret[1] > self.max_y:
            self.max_y = ret[1]
        return ret

    def gohome(self):
        """ move the cursor to the origin at (1,1) """
        self.CUP()

    def reset(self):
        """ Send reset """
        self.RIS()

    def query_cursor_position(self):
        """ query the cursor position """

        return self.x, self.y

    def scroll_up(self):
        """ scroll the scroll region up one line. """
        # "reverse index" in DEC manuals
        self.escape("M")

    def scroll_down(self, n=1):
        """ scroll the scroll region down one line. """
        # "index" in DEC manuals
        if self.Pb:
            self.cursor_save_with_attrs()
            (x, y) = self.getxy()
            n = int(n)
            while n > 0:
                n -= 1
                self.gotoxy(80, self.Pb)
                self.escape("E")
                #self.write("\r\n")
            self.gotoxy(x, y)
            self.cursor_restore_with_attrs()
        self.check_position()

        #self.write("\r\n")
        #self.escape("D%d" % (n,))
        #self.gotoxy(19, 1)

    def enq(self):
        """ Send ENQ to request the answerback message """
        self.escape("\x05")
        # do more here?

    def scroll_enable(self, Pt=None, Pb=None):
        """ Enable the scroll region from line Pt to line Pb """
        if Pt is None and Pb is None:
            self.Pt = self.min_y
            self.Pb = self.max_y
            self.scroll_enabled = False
            self.escape("[r")
            return

        if Pt is None:
            Pt = self.min_y

        if Pb is None:
            Pb = self.max_y

        Pt = int(Pt)
        Pb = int(Pb)
        if Pb < self.min_y:
            Pb = self.min_y
        if Pb > self.max_y:
            Pb = self.max_y
        if Pt < self.min_y:
            Pt = self.min_y
        if Pt > self.max_y:
            Pt = self.max_y
        if Pb <= Pt:
            raise ValueError("Pt(%d) must be less than Pb(%d)" % (Pt, Pb))

        self.Pt = Pt
        self.Pb = Pb
        self.scroll_enabled = True
        self.escape("[%d;%dr" % (Pt, Pb))

    def next_line(self):
        """ Next Line - move the active position to the first character of the
        next line, scrolling if needed """
        self.NEL()

    def wrap(self, enable=True):
        """ Enable or disable line line wrapping mode """
        if enable:
            self.escape("[?7h")
        else:
            # The DEC manual tries to fight its typography to become more
            # clear here, and makes it completely less clear. It has a
            # whole column of:
            # <name> <set meaning> <set code> <reset meaning> <reset code>
            # where <set code> is ESC[?7H and <reset code> is ESC[?7* ,
            # and at the bottom of the page it says:
            # * The last character of the sequence is a lowercase L (154[8])
            self.escape("[?7l")

    def set_attribute(self, *args, **kwargs):
        """ set character attribute (bright, underscore, etc) """
        self.SGR(*args, **kwargs)

    def getxy(self):
        " get the current cursor position - note that this is entirely faked"

        # return self.getpos()
        return self.query_cursor_position()

    def clear(self):
        """ clear the screen """
        self.ED(True, True)

    def drain(self):
        """ drain the file descriptor of its output, we've lost track """

        selector = selectors.PollSelector()
        selector.register(self.filedes, selectors.EVENT_READ)
        count = 0

        while True:
            events = selector.select(timeout=self._get_timeout())
            if not events:
                count += 1
                if count == 4:
                    break
            for key, mask in events:
                if mask & selectors.EVENT_READ:
                    os.read(key.fd, 1)
                    count = 0
        selector.close()

__all__ = [
    "Terminal",
]

# -*- coding: utf-8 -*-
# vim:fenc=utf-8:tw=75
