import typing as t
import os
from os import path as op

try:
    import ujson as json
except ImportError:
    import json      # type: ignore

from inspect import ismethod

__all__ = ['Config']

DEFAULT_NAME = "unknown"


class JSONType(type):
    context: t.Dict[str, t.Any] = dict()

    def __new__(cls, name, bases, attrs):
        cls.context[name] = {
            'path': os.environ.get(attrs.pop('CONTAINER', ''), ''),
            'filename': attrs.pop('FILENAME', DEFAULT_NAME),
        }
        target = super(JSONType, cls).__new__(cls, name, bases, attrs)
        return target

    def set_properties(cls, **kwargs):
        [setattr(cls, k, v) for k, v in kwargs.items()]
        cls._properties = property(lambda self: tuple(kwargs.keys()))
        return cls

    @property
    def extension(cls):
        return 'json'

    @property
    def container(cls):
        env = cls.context.get(cls.__name__, dict())
        rules = (
            '{}',
            '{{}}.{}'.format(cls.extension),
            '{}.{}'.format(env.get('filename', DEFAULT_NAME), cls.extension),

            '../data/{{}}',
            '../data/{{}}.{}'.format(cls.extension),
            '../data/{}.{}'.format(env.get('filename', DEFAULT_NAME), cls.extension)
        )

        for rule in rules:
            configpath = rule.format(env.get('path', ''))
            if op.isfile(op.abspath(configpath)):
                return configpath

        raise FileNotFoundError("Can't find container file")


class Attributes(object):
    def get(self, key, default=None):
        return getattr(self, key, default)

    def all(self, prefix=None):
        return {item: getattr(self, item) for item in dir(self) if not self._skipped(item, prefix)}

    def _skipped(self, item, prefix=None):
        prefix = '' if prefix is None else prefix
        if ismethod(getattr(self, item)) or item in self._properties or item.find('_', 0) == 0:
            return True

        return prefix != item and item.find(prefix, 0) != 0


class Config(Attributes, metaclass=JSONType):
    CONTAINER = "APP_CONFIG_FILE"
    FILENAME = "configuration"

    def __new__(cls, uppercase=None, section=None):
        uppercase = uppercase if isinstance(uppercase, bool) else False
        obj = object.__new__(cls.set_properties(uppercase=uppercase, section=section, configfile=cls.container))
        obj.reload()
        return obj

    def reload(self):
        with open(self.configfile, 'r') as f:
            cfg = json.load(f)

        if self.section:
            for subsection in self.section.split('.'):
                cfg = cfg.get(subsection, dict())
            if not cfg:
                raise ValueError("Can't find section '{}' in file".format(self.section))

        if isinstance(cfg, dict):
            [setattr(self, self.convert_case(k), v) for k, v in cfg.items()]

    def extract(self, section, uppercase=None):
        if not isinstance(section, str):
            return self

        uppercase = uppercase if isinstance(uppercase, bool) else self.uppercase
        return type(self).__new__(type(self), section=section, uppercase=uppercase)

    def get(self, key, default=None):
        return super(type(self), self).get(self.convert_case(key), default)

    def convert_case(self, key):
        return key.upper() if self.uppercase else key

    def _skipped(self, item, prefix=None):
        prefix = '' if prefix is None else self.convert_case(prefix)
        return super(type(self), self)._skipped(item, prefix)
