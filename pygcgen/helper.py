# -*- coding: utf-8 -*-


from __future__ import print_function
import sys
import colorama


DEBUG = False
DEBUGLEVEL = 0

colorama.init(autoreset=True)
stream = colorama.AnsiToWin32(sys.stderr).stream


def PrintRed(text):
    print(colorama.Fore.RED + text, file=stream)


def PrintGreen(text):
    print(colorama.Fore.GREEN + text, file=stream)


def PrintBlue(text):
    print(colorama.Fore.BLUE + text, file=stream)


def PrintYellow(text):
    print(colorama.Fore.YELLOW + text, file=stream)

