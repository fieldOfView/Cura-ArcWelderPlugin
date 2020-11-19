# Copyright (c) 2020 Aldo Hoeben / fieldOfView
# The ArcWelderPlugin for Cura is released under the terms of the AGPLv3 or higher.

from . import ArcWelderPlugin


def getMetaData():
    return {}

def register(app):
    return {"extension": ArcWelderPlugin.ArcWelderPlugin()}
