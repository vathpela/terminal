#!/usr/bin/python3
#
# Copyright 2017 Peter Jones <Peter Jones@random>
#
# Distributed under terms of the GPLv3 license.

"""
This module provides abstractions for talking to a terminal.
"""

import os
import time

from .serial import SerialPort

class Terminal(SerialPort):
    """ This provides a terminal we can write to """

    def __init__(self, settings, name):
        print("[Terminal %s].__init__(settings=%s)" % (name, settings))
        SerialPort.__init__(self, settings, name)

        self.count = 0

        self.cur_x = 1
        self.cur_y = 1
        self.saved_x = 1
        self.saved_y = 1
        self.max_x = 80
        self.max_y = 25
        self.cursor_saved = False

        #self.RIS()
        # self.set_ansi_mode()

        # SM
        # [5h = SRTM - Status Report Transfer Mode, report after DCS
        # self.escape("[5h")

        # RM
        # [3l = CRM - Control characters are not displayable characters
        self.escape("[3l")
        # [5l = SRTM - Report only on command (DSR)
        self.escape("[5l")

        # set the wyse into DEC mode
        #print("~;")
        #self.escape("~;")
        #time.sleep(0.5)

        self.clear()
        self.gohome()

        print("checking position")
        self.set_position(1, 1)

        self.set_attribute(hidden=True)
        self.scroll_enable(Pt=1, Pb=18)
        self.gotoxy(1, self.Pb)
        self.cursor_save_with_attrs()
        self.cursor_restore_with_attrs()

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

        tries = 0
        delay = 0.15
        for x in range(10):
            tries += 1
            x, y = self.getpos()
            if x == self.cur_x and y == self.cur_y:
                if tries != 1:
                    print("waited %f seconds to converge on position" % (delay * tries))
                return
            time.sleep(delay)

        x, y = self.getpos()
        if x != self.cur_x or y != self.cur_y:
            print("waited %f seconds to converge on position" % (delay * tries))
            raise ValueError("position is (%d,%d), expected (%d,%d)" % \
                             (x, y, self.cur_x, self.cur_y))

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

    def decrement_line(self, n: int=1):
        """ Move our internal representation of position up one row """
        self.cur_y -= n
        if self.cur_y < 1:
            self.cur_y = 1

    def decrement_row(self, n: int=1):
        """ Move our internal representation of position up one row """
        self.decrement_line(n)

    def increment_line(self, n: int=1):
        """ Move our internal representation of position down one row """
        self.cur_y += n
        if self.cur_y > self.max_y:
            self.cur_y = self.max_y

    def increment_row(self, n: int=1):
        """ Move our internal representation of position down one row """
        self.increment_line(n)

    def decrement_col(self, n: int=1):
        """ Move our internal representation of position left one col """
        self.cur_x -= n
        if self.cur_x < 1:
            self.cur_x = 1

    def increment_col(self, n: int=1):
        """ Move our internal representation of position right one col """
        self.cur_x += n
        if self.cur_x > self.max_x:
            self.cur_x = self.max_x

    def write(self, s, limit=None):
        """ Write text to the screen """

        #print("doing write")
        if limit is None:
            limit = self.max_x - self.x
        l = min(len(s), limit)
        ns = s[:l]
        # we are clearing by writing spaces, which really sucks, but we
        # don't have partial line clears.
        # probably we should determine if this is the left or right and use
        # one of the partial line clears instead?  But that won't help for
        # the middle.
        sl = (limit - min(len(s), limit))
        ns += " " * sl
        self.increment_col(sl)

        print("len(%s): %s" % (ns, len(ns)))
        os.write(self.filedes, bytes(ns, "UTF-8"))
        self.increment_col(l)
        nsl = len(ns)
        nls = 0
        while ns:
            try:
                nl = ns.index('\n')
                self.increment_row()
                ns = ns[nl+1:]
                nls += 1
            except ValueError:
                break

        print("write() %d characters, %d newlines: " % (nsl, nls))
        print("\"%s\"" % (ns.strip()))
        self.check_position()

    def escape(self, s=""):
        """ Write an escaped character """
        print("s: \"%s\"" % (s,))
        s = "\x1b%s" % (s,)
        if s[-1] in ('2', '3', '4', '5'):
            raise ValueError(s)

        os.write(self.filedes, bytes(s, "UTF-8"))
        if s[-1] == 'H':
            time.sleep(0.5)
        time.sleep(0.05)

    def _CPR(self):
        """ Cursor Position Report - vt100 to host """

        c = os.read(self.filedes, 1).decode('utf8')
        if c != "\x1b":
            raise ValueError("\\x%02x should be \\x1b (ESC)" % (ord(c[0]),))

        c = os.read(self.filedes, 1).decode('utf8')
        if c != '[':
            raise ValueError("\\x%02x should be [" % (ord(c[0]),))

        n = 2
        y = 0
        while c != ';':
            if n > 9:
                raise ValueError("CPR should be 8 bytes or fewer")
            c = os.read(self.filedes, 1).decode('utf8')
            if not c in "0123456789;":
                raise ValueError("\\x%02x should be 0-9 or ;" % (ord(c[0]),))
            if c != ';':
                y *= 10
                y += int(c)
            n += 1

        c = 'x'
        x = 0
        while c != 'R':
            if n > 9:
                raise ValueError("CPR should be 8 bytes or fewer")
            c = os.read(self.filedes, 1).decode('utf8')
            if not c in "0123456789R":
                raise ValueError("\\x%02x should be 0-9 or R" % (ord(c[0]),))
            if c != 'R':
                x *= 10
                x += int(c)
            n += 1

        return (x, y)

    def CPR(self):
        """ Cursor Position Report - vt100 to host """
        try:
            return self._CPR()
        except ValueError as e:
            print("ValueError: %s" % (e,))
            # self.drain()
            # time.sleep(0.1)
            return (self.cur_x, self.cur_y)

    def CUU(self, n: int=1):
        """ CUU - Cursor Up - move cursor up (y-=n) - DEC is terrible """
        n = int(n)
        print("CUU(%d)" % (n,))
        self.escape("%dA" % (n,))
        self.decrement_row(n)

    def CUD(self, n: int=1):
        """ Cursor Down - move cursor down (y+=n) """
        n = int(n)
        print("CUD(%d)" % (n,))
        self.escape("%dB" % (n,))
        self.decrement_row(n)

    def CUF(self, n: int=1):
        """ Cursor Foward - move the cursor right (x+=n) """
        n = int(n)
        print("CUF(%d)" % (n,))
        self.escape("%dC" % (n,))
        self.increment_col(n)

    def CUB(self, n=1):
        """ Cursor Backward - move the cursor left (x-=n) """
        n = int(n)
        print("CUB(%d)" % (n,))
        self.escape("%dD" % (n,))
        self.decrement_col(n)

    def _CUP_and_HVP(self, cmd, x: int=1, y: int=1):
        """ implement CUP and HVP """
        # This is awesomely backwards - first param is which line, second is
        # which column.

        if x == 1 and y == 1:
            self.escape("[%c" % (cmd,))
            self.set_position(1, 1)
            return

        x = int(x)
        y = int(y)
        if x < 1:
            raise ValueError(x)
        if x > self.max_x:
            raise ValueError(x)
        if y < 1:
            raise ValueError(y)
        if y > self.max_y:
            raise ValueError(y)
        if x == self.x and y == self.y:
            self.count += 1
            if self.count > 5:
                raise RuntimeError
            return
        self.count = 0

        print("CUP(%d,%d)" % (x, y))
        self.escape("[%d;%d%c" % (y, x, cmd))
        #time.sleep(0.1)

    def CUP(self, x: int=1, y: int=1):
        """ CUP - Cursor Position - move the cursor to (x, y) """
        self._CUP_and_HVP('H', x, y)
        try:
            self.set_position(x, y)
        except ValueError:
            self._CUP_and_HVP('f', x, y)

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

    def DSR(self, n: int=0):
        """ Device Status Report """
        self.escape("[%dn" % (n,))
        time.sleep(0.2)
        if n == 5:
            dsr = os.read(self.filedes, 4).decode('utf8')
            if dsr[0:2] != "\x1b[" or dsr[3] != 'n':
                raise ValueError("\"%s\" should be \"\\x1b[Pn\"" % (dsr,))
            return int(dsr[2])
        elif n == 6:
            return self.CPR()

    def ED(self, erase_from_start=False, erase_to_end=False):
        """ Erase In Display """

        if (erase_from_start and erase_to_end) or \
                (not erase_from_start and not erase_to_end):
            print("ED(2)")
            self.escape("[%dJ" % (2,))
        elif erase_from_start:
            print("ED(1)")
            self.escape("[%dJ" % (1,))
        elif erase_to_end:
            print("ED(0)")
            self.escape("[%dJ" % (0,))
        #time.sleep(0.2)

    def EL(self, erase_from_start=False, erase_to_end=False):
        """ Erase In Line """

        if (erase_from_start and erase_to_end) or \
                (not erase_from_start and not erase_to_end):
            print("EL(2)")
            self.escape("[%dK" % (2,))
        elif erase_from_start:
            print("EL(1)")
            self.escape("[%dK" % (1,))
        elif erase_to_end:
            print("EL(0)")
            self.escape("[%dK" % (0,))
        #time.sleep(0.2)

    def HTS(self):
        """ Horizontal Tab Set (at current position) """
        self.escape("H")

    def HVP(self, x: int=1, y: int=1):
        """ Horizontal and Vertical Position - aka CUP """
        self._CUP_and_HVP('f', x, y)
        self.set_position(x, y)

    def IND(self):
        """ Index - move active position one line down, scroll if bottom """
        print("IND")
        self.escape("D")
        self.increment_line()

        self.check_position()

    def NEL(self):
        """ Next Line - move the active position to the first character of the
        next line, scrolling if needed """
        print("NEL")
        self.escape("E")
        self.increment_line()
        self.cur_x = 1

        self.check_position()

    def RI(self):
        """ Reverse Index - move active position up one line, scroll if needed
        """
        print("RI")
        self.escape("M")
        self.decrement_line()

        self.check_position()

    def RIS(self):
        """ Reset To Initial State """
        print("RIS")
        # reset the terminal the proper DEC way
        self.escape("c")
        time.sleep(10)

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
        for key, val in kwargs.items():
            if not key in attributes:
                raise TypeError(
                    "%s() got an unexpected keyword argument '%s'" %
                    (__name__, key))
            params += "%s;" % (val,)

        if params.endswith(";"):
            params = params[:-1]
        else:
            params = "0"

        self.escape("[%sm" % (params,))

    def TBC(self, Ps=0):
        """ Tabular Clear -- 0 clears current position, 3 clears all """
        self.escape("[%dg" % (Ps,))

    # skipping...
    #def SM(self):
    #    """ Reset Mode - ESC [ Ps;Ps;...;Ps h """
    #

    def cursor_save(self):
        """ save the current cursor position """
        #print("doing cursor_save")
        if self.cursor_saved:
            #print("doing cursor_save_with_attrs")
            return
        self.saved_x = self.cur_x
        self.saved_y = self.cur_y
        self.cursor_saved = True
        print("save(%d,%d)" % (self.cur_x, self.cur_y))
        self.escape("[s")
        time.sleep(0.01)

    def cursor_restore(self):
        """ restore the cursor position from previously saved """
        #print("doing cursor_restore")
        self.cur_x = self.saved_x
        self.cur_y = self.saved_y
        print("restore(%d,%d)" % (self.cur_x, self.cur_y))
        self.escape("[u")
        time.sleep(0.01)
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
        print("save(%d,%d)" % (self.cur_x, self.cur_y))
        self.escape("7")
        time.sleep(0.01)

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
        print("restore(%d,%d)" % (self.cur_x, self.cur_y))
        self.escape("8")
        time.sleep(0.01)
        self.check_position()

    def set_ansi_mode(self):
        """ Put the terminal in ANSI mode """
        print("SET ANSI MODE")
        self.escape('<')

    def set_alt_keypad_mode(self, enabled=True):
        """ numlock """
        if enabled:
            self.escape('=')
        else:
            self.escape('>')

    def gotoxy(self, x, y):
        """ Go to (x, y) """
        self.CUP(x, y)

    def getpos(self):
        """ get current (x, y) """
        time.sleep(0.1)
        return self.DSR(6)

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
        self.Pt = Pt
        self.Pb = Pb
        if Pt != None and Pb != None:
            Pt = int(Pt)
            Pb = int(Pb)
            if Pb < 1:
                Pb = 1
            if Pb > self.max_y:
                Pb = self.max_y
            if Pt < 1:
                Pt = 1
            if Pt > self.max_y:
                Pt = self.max_y
            if Pb <= Pt:
                raise ValueError("Pt(%d) must be less than Pb(%d)" % (Pt, Pb))
            self.escape("[%d;%dr" % (Pt, Pb))
        else:
            self.escape("[r")

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

        import selectors
        selector = selectors.PollSelector()
        count = 0
        for em in selector.select(0.05):
            mask = em[1]
            if mask & selectors.EVENT_READ:
                os.read(self.filedes, 1)
                count = 0
            else:
                count += 1
            # if we got 0.2 seconds without any input, it's done...
            if count == 4:
                break

__all__ = [
    "Terminal",
]

# -*- coding: utf-8 -*-
# vim:fenc=utf-8:tw=75
