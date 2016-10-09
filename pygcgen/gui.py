# -*- coding: utf-8 -*-

import wx


class MainFrame(wx.Frame):
    def __init__(self, *args, **kwargs):
        super(MainFrame, self).__init__(*args, **kwargs)
        self.BuildGui()

    def BuildGui(self):
        pass


class GeneratorApp(wx.App):
    pass
