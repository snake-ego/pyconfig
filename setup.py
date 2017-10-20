#!/usr/bin/env python
import os
import re
from setuptools import setup, find_packages


def get_version(fname):
    result = ''
    reg = re.compile(r'__version__ = [\'"]([^\'"]*)[\'"]')
    with open(fname, 'r') as fp:
        for line in fp:
            m = reg.match(line)
            if m:
                result = m.group(1)
                break
    if not result:
        raise RuntimeError('Cannot find version information')
    return result


__version__ = get_version("config/__init__.py")

setup(
    name='Config-Control',
    version=__version__,
    description="Библиотека для работы с конфигурацией",
    packages=find_packages(exclude=['tests']),
    install_requires=open('requirements.txt').read() if os.path.exists('requirements.txt') else ''
)
