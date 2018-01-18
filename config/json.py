import os
from os import path as op
from Crypto import Random
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
        obj.uppercase = uppercase
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


class CryptoContainer(Attributes, metaclass=JSONType):
    CONTAINER = "APP_CRYPTO_FILE"
    FILENAME = "vault"

    key = None
    splitter = b";"

    def __new__(cls, key=None):
        key = key if isinstance(key, str) else cls.key

        if not isinstance(key, str):
            raise ValueError(f'Bad key value: {key}')

        if len(key) != 32:
            raise ValueError(f'Key must have 32 symbols')

        try:
            cryptofile = cls.container
        except FileNotFoundError:
            ctx = cls.context[cls.__name__]
            if ctx.get('path'):
                cryptofile = ctx.get('path')
            else:
                cryptofile = op.join('.', f"{ctx.get('filename')}.{cls.extension}")

        obj = object.__new__(cls.set_properties(key=key, splitter=cls.splitter, cryptofile=cryptofile))
        return obj

    def create(self):
        if op.isfile(self.cryptofile):
            return

        folder = op.dirname(op.abspath(self.cryptofile))
        if not op.isdir(folder):
            os.makedirs(folder)

        return open(self.cryptofile, 'w').close()

    def reload(self):
        if not op.isfile(self.cryptofile):
            raise FileNotFoundError(f"Can't find file: {self.cryptofile}. Need to call create first")

        with open(self.cryptofile, 'rb') as f:
            *_, iv = f.readline().strip().split(self.splitter)
            aes = AES.new(self.key, AES.MODE_CFB, iv)
            data = str(aes.decrypt(f.read()), 'utf-8')

        [setattr(self, *i) for i in json.loads(data).items()]

    def save(self):
        data = json.dumps(self.all())

        crypt = b"AES256"
        iv = Random.new().read(AES.block_size)

        aes = AES.new(self.key, AES.MODE_CFB, iv)
        with open(self.cryptofile, 'wb') as f:
            f.write(self.splitter.join([crypt, iv]) + b'\n')
            f.write(aes.encrypt(data))
