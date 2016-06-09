#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
nmrstarlib.bmrblex
~~~~~~~~~~~~~~~~~~

A lexical analyzer class for BMRB STAR syntax.

This module is based on python ``shlex`` module modified to address specifics of BMRB NMR-STAR format.
The ``shlex`` class makes it easy to write lexical analyzers for simple syntaxes resembling
that of the Unix shell. Documentation: https://docs.python.org/3/library/shlex.html


Parsing rules:
--------------
   * Each word or number separated by whitespace characters is a separate BMRB token.
   * Each single quoted (') string is a separate BMRB token, it should start with single quote (')
     and end with single quote *always* followed by whitespace characters.
   * Each double quoted (") string is a separate BMRB token, it should start with double quote (")
     and end with double quote *always* followed by whitespace characters.
   * Single quoted and double quoted strings have to be processed separately.
   * Single quoted and double quoted strings are processed one character at a time.
   * Multiline strings starts with semicolon *always* followed by new line character and
     end with semicolon *always* followed by new line character.
   * Multiline strings are processed one line at a time.
"""

import sys
from collections import deque
from io import StringIO

__all__ = ["bmrblex"]

class bmrblex:
    """A lexical analyzer class for BMRB STAR syntax."""

    def __init__(self, instream=None, infile=None):
        if isinstance(instream, str):
            instream = StringIO(instream)
        elif isinstance(instream, bytes):
            instream = StringIO(instream.decode("utf-8"))

        if instream is not None:
            self.instream = instream
            self.infile = infile
        else:
            self.instream = sys.stdin
            self.infile = None

        self.eof = ''
        self.commenters = '#'
        self.wordchars = ('abcdfeghijklmnopqrstuvwxyz'
                          'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_'
                          'ßàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ'
                          'ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞ'
                          '!@#$%^&*()_+:;?/>.<,~`|\{[}]-=')
        self.whitespace = ' \t\r\n'
        self.escapedquotes = '"'
        self.state = ' '
        self.pushback = deque()
        self.token = ''

        self.singlequote = "'"
        self.doublequote = '"'
        self.multilinequote = '\n;\n'
        self.prevchar = ''

        # stream position gets incremented by 1 each time instream.read(1) is called
        # since instream has 0-based numeration, the first emitted character
        # gets streamposition = 0, hence initial streamposition = -1
        self.streamposition = -1
        self.streamlength = len(self.instream.getvalue())
        # self.streamlength = len(self.instream)
 
    def get_token(self):
        """Get a token from the input stream (or from stack if it's nonempty).

        :return: current token
        :rtype: str
        """
        if self.pushback:
            token = self.pushback.popleft()
            return token
        # No pushback.  Get a token.
        raw = self.read_token()
        return raw

    def read_token(self):
        """Read token based on the parsing rules

        :return: current token
        :rtype: str
        """
        quoted = False

        # next streamposition, i.e. streamposition+1 should not exceed the number of
        # characters inside instream, streamlength-1 ==> stopping criteria for the while loop
        while self.streamposition+1 < self.streamlength-1:
            nextchar = self.instream.read(1)
            self.streamposition += 1

            nextnextchar = self.instream.read(1)       # look up 1 char ahead
            self.instream.seek(self.streamposition+1)  # return to current stream position

            # print("all 3 together:", repr(self.prevchar), repr(nextchar), repr(nextnextchar))
            if self.prevchar+nextchar+nextnextchar == '\n;\n': #self.multilinequote:
                self.state = self.multilinequote

            try:
                if self.state is None:
                    self.token = ''        # past end of file
                    break

                elif self.state == ' ':
                    if not nextchar:
                        self.state = None  # end of file
                        break
                    elif nextchar in self.whitespace:
                        if self.token:
                            break   # emit current token
                        else:
                            continue
                    elif nextchar in self.commenters:
                        line = self.instream.readline()
                        self.streamposition += len(line)
                    elif nextchar in self.wordchars:
                        self.token = nextchar
                        self.state = 'a'
                    elif nextchar in self.singlequote:
                        self.token = nextchar
                        self.state = nextchar
                    elif nextchar in self.doublequote:
                        self.token = nextchar
                        self.state = nextchar
                    # elif nextchar in self.multilinequote:
                    #     self.token = nextchar
                    #     self.state = nextchar
                    else:
                        self.token = nextchar
                        if self.token:
                            break   # emit current token
                        else:
                            continue

                # Process multiline-quoted text
                elif self.state == self.multilinequote:
                    quoted = True
                    if not nextchar:      # end of file
                        raise EOFError("No closing quotation")

                    line = self.instream.readline()
                    self.streamposition += len(line) # skip first line == ';\n'

                    line = self.instream.readline()
                    self.streamposition += len(line)

                    while True:
                        if line.startswith(';'): # end of multiline string
                            # self.token = " ".join(self.token.split()) # clean up multiline string - remove extra ' ' and '\n' characters
                            # self.token = ';' + self.token + ';'
                            self.prevchar = '\n'             # if line starts with ';' previous must be '\n'
                            self.streamposition -= len(line) # get back to the beginning of line
                            nextchar = self.instream.read(1) # emit nextchar after ';'
                            self.streamposition += 1
                            self.state = ' '
                            break   # emit current token
                        else:
                            self.token = self.token + line   # continue concatenating lines to token
                            line = self.instream.readline()
                            self.streamposition += len(line)

                # process token staring with single quote '
                elif self.state in self.singlequote:
                    quoted = True
                    if not nextchar:      # end of file
                        raise EOFError("No closing quotation")

                    if nextchar == self.state:
                        if nextnextchar not in self.whitespace:
                            self.token = self.token + nextchar
                            self.state = self.singlequote
                        elif nextnextchar in self.whitespace:
                            self.token = self.token + nextchar
                            self.state = ' '
                            break   # emit current token
                    else:
                        self.token = self.token + nextchar

                # process token staring with double quote "
                elif self.state in self.doublequote:
                    quoted = True
                    if not nextchar:      # end of file
                        raise EOFError("No closing quotation")
                    if nextchar == self.state:
                        if nextnextchar not in self.whitespace:
                            self.token = self.token + nextchar
                            self.state = self.doublequote
                        elif nextnextchar in self.whitespace:
                            self.token = self.token + nextchar
                            self.state = ' '
                            break
                    else:
                        self.token = self.token + nextchar

                elif self.state == 'a':
                    if not nextchar:
                        self.state = None   # end of file
                        break
                    elif nextchar in self.whitespace:
                        self.state = ' '
                        if self.token or quoted:
                            break   # emit current token
                        else:
                            continue
                    else:
                        self.token = self.token + nextchar

            finally:
                # always keep an eye on the previous character in order to process
                # multiline strings correctly: '\n' followed by ';' followed by '\n'
                self.prevchar = nextchar

        result = self.token
        self.token = ''
        return result

    def error_leader(self, infile=None, lineno=None):
        """Emit a C-compiler-like, Emacs-friendly error-message leader."""
        if infile is None:
            infile = self.infile
        # if lineno is None:
        #     lineno = self.lineno
        # return "\"%s\", line %d: " % (infile, lineno)
        return ''

    def __iter__(self):
        return self

    def __next__(self):
        token = self.get_token()
        if token == self.eof:
            raise StopIteration
        return token

if __name__ == '__main__':
    if len(sys.argv) == 1:
        lexer = bmrblex()
    else:
        file = sys.argv[1]
        lexer = bmrblex(open(file), file)
    while 1:
        tt = lexer.get_token()
        if tt:
            print("Token: " + repr(tt))
        else:
            break