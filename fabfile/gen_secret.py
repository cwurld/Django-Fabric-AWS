__author__ = 'Chuck Martin'

from random import choice


def gen_secret(length=50):
    choices = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*(-_=+)'
    secret_key = ''.join([choice(choices) for n in xrange(length)])
    return secret_key
