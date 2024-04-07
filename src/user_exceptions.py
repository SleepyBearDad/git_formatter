#!  /usr/bin/python3

import re

from consts import diff_prefix


# A user can then add his own types of exceptions to the formatter based on:
# - context: add/remove lines, and diff context (e.g. function/struct/enum name)
# - adds: a list of lines added by the formatter
# - removes: a list of lines removed by the formatter
class UserException(object):
    _config_key = ""

    @classmethod
    def action(cls, context_line, adds, removes):
        return False

    @classmethod
    def get_exception(cls):
        return (cls.action, cls._config_key)


class WhitespaceRemoveException(UserException):
    with_whitespaces = "(\w+)\s+(\*?\&?\w+)"
    without_whitespaces = "(\w+) (\*?\&?\w+)"

    with_whitespaces_re = None
    without_whitespaces_re = None

    @staticmethod
    def parse_context(context_line):
        if len(context_line.split(diff_prefix)[2].split(" ")) < 2:
            return None
        return context_line.split(diff_prefix)[2].split(" ")[1]

    @classmethod
    def parse_with_whitespaces(cls, s):
        if not cls.with_whitespaces_re:
            cls.with_whitespaces_re = re.compile(cls.with_whitespaces)
        res = cls.with_whitespaces_re.search(s)
        if res == None:
            return []
        return res.groups()

    @classmethod
    def parse_without_whitespaces(cls, s):
        if not cls.without_whitespaces_re:
            cls.without_whitespaces_re = re.compile(cls.without_whitespaces)
        res = cls.without_whitespaces_re.search(s)
        if res == None:
            return []
        return res.groups()

    @classmethod
    def remove_align_whitespaces(cls, adds, removes):
        if len(adds) != len(removes):
            return False

        for i in range(0, len(adds)):
            rm_words = cls.parse_with_whitespaces(removes[i])
            add_words = cls.parse_without_whitespaces(adds[i])
            if rm_words == [] or add_words == []:
                return False
            if rm_words != add_words:
                return False
        return True

    @classmethod
    def action(cls, context_line, adds, removes):
        return cls.remove_align_whitespaces(adds, removes)


# diff removes whitespace/tab aligned words
#
# removes:
#     struct foo           *foo;
#     struct bar           &bar;
#
# adds:
#     struct foo *foo;
#     struct bar *bar;
class WhitespaceInStructContext(WhitespaceRemoveException):
    _config_key = "remove-whitespaces-in-struct-ctx"
    with_whitespaces = "(\w+)\s+([\*\&]?\w+)"
    without_whitespaces = "(\w+)\s(\*?\&?\w+)"

    @classmethod
    def action(cls, context_line, adds, removes):
        context = cls.parse_context(context_line)
        if context == "struct" and cls.remove_align_whitespaces(adds, removes):
            return True

# diff removes mnixed whitespaces and tabs when aligning assignments
#
# removes:
#    very_long_variable_name = 0;
#    short_name              = 0;  // Mixed tabs and spaces for alignment
#
# adds:
#    very_long_variable_name = 0;
#    short_name              = 0;  // All the tabse are replaced by spaces...
class MixedWhiteSpaceInAssignAlignment(WhitespaceRemoveException):
    _config_key = "remove-whitespaces-in-assign-alignment"
    with_whitespaces = "(\w+)[\]\)]?\s+= [\(]?(\*?\&?\w+)"
    without_whitespaces = "(\w+)[\]\)]?[ ]+ = [\(]?(\*?\&?\w+)"

class ExceptionOnRegexMatch(UserException):
    _re = None

    @classmethod
    def action(cls, context_line, adds, removes):
        for line in removes:
            if not cls._re:
                cls._re = re.compile(cls._re_str)
            if cls._re.match(line):
                return True
        return False


# diff breaks multi-line shift alignment
#
# removes:
#    bitmask = htobe32(
#    (FOO    << SHIFT_FOO)     |
#    (FOOFOO << SHIFT_FOO_FOO));
#
# adds:
#    btimaks = htobe32(
#                      (FOO << SHIFT_FOO)       |
#                      (FOOFOO << SHIFT_FOOFOO));
class BreakMultiLineShift(ExceptionOnRegexMatch):
    _config_key = "break-multi-line-shift"
    _re_str = "-\s+\(\w+\s+(<<|>>)\s+\w+\)\s+[|&]"


# diff indents multi-line or
#
# removes:
#    bitmask = htobe32(
#    BIT_1_DESCRIPTION |
#    BIT_2_DESCRIPTION |
#    BIT_3_DESCRIPTION);
#
# adds:
#    bitmask = htobe32(
#        BIT_1_DESCRIPTION |
#        BIT_2_DESCRIPTION |
#        BIT_3_DESCRIPTION);
class BreakMultiLineOr(ExceptionOnRegexMatch):
    _config_key = "break-multi-line-or"
    _re_str = "-\s+\(?\w+.*\|$"


# exception on DEVX_ macros
#
# project defines this type of alignment only for the devx macros:
#
# DEVX(foo      , var_foo  )
# DEVX(foobar   , var_bar  )
# DEVX(foobarbaz, varbarbaz)
#
# In order not to complicate, we simply fix the macro calls altogether.
class DevxMacroException(ExceptionOnRegexMatch):
    _config_key = "devx-macro-exception"
    _re_str = "[+-]\t+DEVX_SET_[A-Z0-9_]+\(.*\);$"


def get_user_exceptions():
    exceptions = [WhitespaceInStructContext,
                  MixedWhiteSpaceInAssignAlignment,
                  BreakMultiLineShift,
                  BreakMultiLineOr,
                  DevxMacroException,
                 ]
    return [e.get_exception() for e in exceptions]
