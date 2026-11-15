#!/usr/bin/env python3
"""Prepare the native PJSIP WebSocket default during an owned fresh bootstrap."""


def factory_rows():
    # Public sipsettings/install.php seed, including its two default RTP rows.
    codecs = [('ulaw', '1'), ('alaw', '2'), ('slin', ''), ('g726', ''),
              ('gsm', '3'), ('g729', '5'), ('ilbc', ''), ('g723', ''),
              ('g726aal2', ''), ('adpcm', ''), ('lpc10', ''), ('speex', ''),
              ('g722', ''), ('opus', '4')]
    return sorted([[key, value, str(index), '1']
                   for index, (key, value) in enumerate(codecs)] +
                  [['callevents', 'yes', '0', '0'],
                   ['rtpstart', '10000', '0', '0'], ['rtpend', '20000', '1', '0']])


def plan_rows(rows):
    return None
