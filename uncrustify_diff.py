#!  /usr/bin/python3

import configparser
import os
import re
import sys
import tempfile


new_file_prefix_a = "--- a/"
new_file_prefix_b = "+++ b/"
diff_prefix = "@@"
diff_suffix = "@@"
remove_prefix = "-"
add_prefix = "+"


class Color:
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    DARKCYAN = "\033[36m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    END = "\033[0m"


class Config(object):
    _default = {"colors": True, "uncrustify": False, "clang": False}
    _config = None

    @classmethod
    def config_from_git(cls):
        gitconfig = configparser.ConfigParser(strict=False)
        gitconfig.read([os.environ["HOME"] + "/.gitconfig", ".git/config"])

        def get_from_config(key):
            val = gitconfig.get("formatter", key, fallback=cls._default[key])
            if isinstance(val, str) and val.lower() in ["true", "false"]:
                val = True if val.lower() == "true" else False
            return val

        def set_from_config(key):
            setattr(cls, key, get_from_config(key))

        for key in cls._default.keys():
            set_from_config(key)

        if not getattr(cls, "colors"):
            Color.PURPLE = Color.CYAN = Color.DARKCYAN = Color.BLUE = Color.GREEN = ""
            Color.YELLOW = Color.RED = Color.BOLD = Color.UNDERLINE = Color.END = ""

    @classmethod
    def initialize(cls):
        if cls._config == None:
            cls.config_from_git()

        return cls._config


def parse_diff_element(e):
    words = e[1:].split(",")
    return int(words[0]), 0 if len(words) == 1 else int(words[1])


def parse_diff_prefix(line):
    elements = line[len(diff_prefix) :].split(" ")
    add_start = None
    add_len = 0
    remove_start = None
    remove_len = 0

    for e in elements[1:]:
        if e[0] == "-":
            remove_start, remove_len = parse_diff_element(e)
        if e[0] == "+":
            add_start, add_len = parse_diff_element(e)

    return add_start, add_len, remove_start, remove_len


def diff_parser(open_file):
    files = {}
    current_file = ""
    new_file = ""
    file_summary = None

    for line in open_file.readlines():
        if line.startswith(new_file_prefix_a):
            new_file = line[len(new_file_prefix_a) :].split(" ")[0].strip()
        if line.startswith(new_file_prefix_b):
            new_file = line[len(new_file_prefix_b) :].split(" ")[0].strip()

        if new_file != "" and new_file != current_file:
            if current_file != "":
                files[current_file] = file_summary
            current_file = new_file.strip()
            file_summary = {"adds": [], "removes": []}

        if line.startswith(diff_prefix):
            add_start, add_len, remove_start, remove_len = parse_diff_prefix(line)

            if add_start:
                file_summary["adds"].append((add_start, add_len))
            if remove_start:
                file_summary["removes"].append((remove_start, remove_len))

    if file_summary:
        files[current_file] = file_summary

    return files


def find_overlaps(a1, a2):
    _a1 = sum([list(range(start, start + end + 1)) for (start, end) in a1], [])
    _a2 = sum([list(range(start, start + end + 1)) for (start, end) in a2], [])

    overlap = set(_a1)
    return list(overlap.intersection(_a2))


def overlap_hunks(diff_file, diff1, diff2):
    overlaps = find_overlaps(diff1, diff2)
    if not overlaps:
        return []

    diff_file.seek(0)
    git_overlap_lines_set = set(overlaps)
    hunks = []
    collect = False

    for line in diff_file.readlines():
        if line.startswith(diff_prefix):
            add_start, add_len, _, _ = parse_diff_prefix(line)
            r = set(range(add_start, add_start + add_len + 1))
            collect = git_overlap_lines_set.intersection(r) != set()

            if collect:
                hunk = Hunk()
                hunks.append(hunk)

        if collect:
            hunk.swallow(line)

    return hunks


class Hunk(object):
    def __init__(self):
        self.context = None
        self.adds = []
        self.removes = []

    def swallow(self, line):
        if line.startswith(diff_prefix):
            self.context = line
        elif line.startswith(remove_prefix):
            self.removes.append(line)
        elif line.startswith(add_prefix):
            self.adds.append(line)

    def __str__(self):
        elements = self.context.split(diff_prefix)
        formated_line = Color.BLUE + diff_prefix + elements[1] + diff_prefix + Color.END
        formated_line += " ".join(elements[2:])
        s = formated_line

        for line in self.removes + self.adds:
            s += line

        # A little ugly, we strip the last "\n"
        return s[:-1]


class DiffFile(object):
    def __init__(self, delete=True):
        self.delete = delete

    def diff_cmd(self):
        return "echo ''"

    def __enter__(self):
        self.tempfile = tempfile.NamedTemporaryFile(prefix="/tmp/difftool.")
        cmd = self.diff_cmd() + " > " + self.tempfile.name
        os.system(cmd)
        self.open_file = open(self.tempfile.name)
        return self.open_file

    def __exit__(self, *exc_details):
        # TODO: handle exceptions
        self.open_file.close()


class GitDiffFile(DiffFile):
    def __init__(self, base, diff, delete=True):
        super().__init__(delete)
        self.base = base
        self.diff = diff

    def diff_cmd(self):
        return f"git diff -U0 {self.base} {self.diff}"


class UncrustifyDiffFile(DiffFile):
    def __init__(self, src, delete=True):
        super().__init__(delete)
        self.src = src

    def diff_cmd(self):
        return (
            f"diff --show-c-function -U0 {self.src} {self.uncrustify_out.name} | "
            + f"sed -e 's#^+++ /tmp/difftool.*#+++ b/{self.src}#'"
        )

    def __enter__(self):
        prefix = f"/tmp/difftool.{self.src.replace('/','.')}."
        self.uncrustify_out = tempfile.NamedTemporaryFile(prefix=prefix)
        cmd = f"uncrustify -q -l C -c .uncrustify.cfg -f {self.src} -o {self.uncrustify_out.name}"
        os.system(cmd + " > " + self.uncrustify_out.name)
        return super().__enter__()


def git_diff_map(base, diff):
    with GitDiffFile(base=base, diff=diff, delete=False) as f:
        return diff_parser(f)
    return {}


def check_exceptions(hunk):
    # Example of exception using struct context (need to add regex check for alignment)
    #
    # elements = hunk["context"].split(diff_prefix)
    # if elements[2].split(" ")[1] == "struct":
    #     return True

    return False


def print_diff(filename, hunks):
    if hunks == []:
        return

    print(Color.BOLD + filename + Color.END)
    for hunk in hunks:
        if check_exceptions(hunk):
            continue
        print(hunk)


def print_formatter_dif(formatter, git_diff):
    for f in git_diff.keys():
        with formatter(f) as diff_file:
            diff = diff_parser(diff_file)
            overlaps = overlap_hunks(diff_file, diff[f]["adds"], git_diff[f]["adds"])
            print_diff(f, overlaps)


def get_base_and_diff(args):
    if len(args) in [2, 3]:
        if len(args) == 2:
            base = args[1]
            diff = "HEAD"
        else:
            base = args[1]
            diff = args[2]
    else:
        base = "origin/main"  # use configuration to get default base!
        diff = "HEAD"
    return base, diff


def main(args):
    Config().initialize()
    base, diff = get_base_and_diff(args)
    diff_map = git_diff_map(base, diff)
    if Config.uncrustify:
        print_formatter_dif(UncrustifyDiffFile, diff_map)


if __name__ == "__main__":
    main(sys.argv)
