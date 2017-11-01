import os
from os import path as op
from Crypto.Cipher import AES

try:
    import ujson as json
except ImportError:
    import json

from inspect import ismethod

__all__ = ['Config']

DEFAULT_NAME = "unknown"


class JSONType(type):
    context = dict()

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


class Config(metaclass=JSONType):
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
            [setattr(self, self.case(k), v) for k, v in cfg.items()]

    def get(self, key, default=None):
        return getattr(self, self.case(key), default)

    def all(self, prefix=None):
        return {item: getattr(self, item) for item in dir(self) if self._is_allowed(item, prefix)}

    def _is_allowed(self, item, allow_prefix=None):
        allow_prefix = '' if allow_prefix is None else allow_prefix

        if ismethod(getattr(self, item)):
            return False
        if item in self._properties:
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

        uppercase = uppercase if isinstance(uppercase, bool) else self.uppercase
        return type(self).__new__(type(self), section=section, uppercase=uppercase)


class CryptoContainer(metaclass=JSONType):
    CONTAINER = "APP_CRYPTO_FILE"
    FILENAME = "vault"

    key = None

    def __new__(cls, key=None):
        key = key if isinstance(key, str) else cls.key

        if not isinstance(key, str):
            raise ValueError(f'Bad key value: {key}')

        try:
            cryptofile = cls.container
        except FileNotFoundError:
            ctx = cls.context[cls.__name__]
            if ctx.get('path'):
                cryptofile = ctx.get('path')
            else:
                cryptofile = op.join('.', f"{ctx.get('filename')}.{cls.extension}")

        obj = object.__new__(cls.set_properties(cryptofile=cryptofile))
        obj.key = property(lambda self: key)
        return obj

    def create(self):
        if op.isfile(self.cryptofile):
            return

        folder = op.dirname(op.abspath(self.cryptofile))
        if not op.isdir(folder):
            os.makedirs(folder)

        return open(self.cryptofile, 'w').close()
