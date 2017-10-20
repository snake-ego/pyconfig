import os
from os import path as op

try:
    import ujson as json
except ImportError:
    import json

from inspect import ismethod

__all__ = ['Config']

DEFAULT_NAME = "configuration"
CONFIG_ENV = "APP_CONFIGFILE"


class Config(object):
    extension = 'json'

    def __new__(cls, uppercase=None, section=None):
        config = cls.find_config()
        uppercase = uppercase if isinstance(uppercase, bool) else False
        properties = {
            '_baseclass': property(lambda self: cls),
            'section': property(lambda self: section),
            'uppercase': property(lambda self: uppercase),
            'config': property(lambda self: config),
            'extension': property(lambda self: cls.extension)
        }
        properties.update({'_exclude_attr': property(lambda self: tuple(properties.keys()))})
        Config = type("Config", (cls, ), properties)
        obj = super(cls, Config).__new__(Config)
        obj.reload()
        return obj

    def reload(self):
        if self.config.find('\n') == -1:
            with open(self.config, 'r') as f:
                cfg = json.load(f)
        else:
            cfg = json.load(self.config)

        if self.section is not None:
            for subsection in self.section.split('.'):
                cfg = cfg.get(subsection, dict())
            if not cfg:
                raise ConfigError("Can't find section '{}' in file".format(self.section))

        if isinstance(cfg, dict):
            [setattr(self, self.case(k), v) for k, v in cfg.items()]

    def get(self, key, default=None):
        return getattr(self, self.case(key), default)

    def all(self, prefix=None):
        return {item: getattr(self, item) for item in dir(self) if self._is_allowed(item, prefix)}

    def _is_allowed(self, item, allow_prefix=None):
        allow_prefix = '' if allow_prefix is None else allow_prefix

        if ismethod(getattr(self, item)):
            return False
        if item in self._exclude_attr:
            return False
        if item.find('_', 0) == 0:
            return False
        if self.case(allow_prefix) == item:
            return True
        if item.find(self.case(allow_prefix), 0) == 0:
            return True
        return False

    def case(self, key):
        if self.uppercase:
            return key.upper()
        return key

    def extract(self, section, uppercase=None):
        if not isinstance(section, str):
            return self

        if self.section is not None:
            section = ".".join([self.section, section])

        uppercase = uppercase if isinstance(uppercase, bool) else self.uppercase

        return self._baseclass(section=section, uppercase=uppercase)

    @classmethod
    def find_config(cls):
        rules = (
            '{{}}',
            '{{}}.{}'.format(cls.extension),
            '{}.{}'.format(DEFAULT_NAME, cls.extension),

            '../data/{{}}',
            '../data/{{}}.{}'.format(cls.extension),
            '../data/{}.{}'.format(DEFAULT_NAME, cls.extension)
        )
        for rule in rules:
            configpath = rule.format(os.environ.get('MBA_CONFIGFILE', ''))
            if op.exists(configpath):
                return configpath

        raise ConfigError("Can't find config")


class ConfigError(Exception):
    pass
