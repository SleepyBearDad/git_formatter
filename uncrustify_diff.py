#!  /usr/bin/python3

import configparser
import os
import sys
import tempfile


new_file_prefix_a = "--- a/"
new_file_prefix_b = "+++ b/"
diff_prefix = "@@"
diff_suffix = "@@"


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
        gitconfig = configparser.ConfigParser()
        gitconfig.read_file(open(os.environ["HOME"] + "/.gitconfig"))

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


def find_overlaps(a1, a2):
    _a1 = sum([list(range(start, start + end + 1)) for (start, end) in a1], [])
    _a2 = sum([list(range(start, start + end + 1)) for (start, end) in a2], [])

    overlap = set(_a1)
    return list(overlap.intersection(_a2))


def print_uncrustify_diff(filename, diff_file, git_overlap_lines):
    diff_file.seek(0)
    git_overlap_lines_set = set(git_overlap_lines)
    lines = []
    collect = False
    for line in diff_file.readlines():
        if line.startswith(diff_prefix):
            add_start, add_len, _, _ = parse_diff_prefix(line)
            r = set(range(add_start, add_start + add_len + 1))
            collect = git_overlap_lines_set.intersection(r) != set()

        if collect:
            lines.append(line)

    print(Color.BOLD + filename + Color.END)
    for line in lines:
        if line.startswith(diff_prefix):
            elements = line.split(diff_prefix)
            # This can allow to check for exceptions in struct contexts for example!
            # print(elements[2].split(" ")[1] == "struct")
            formated_line = (
                Color.BLUE + diff_prefix + elements[1] + diff_prefix + Color.END
            )
            formated_line += " ".join(elements[2:])
            print(formated_line)
        else:
            # if line.strip()[-1] == "|": print("Possible exception for multi-line or")
            print(line.strip())


def uncrustify_diff(git_diff):
    for f in git_diff.keys():
        with UncrustifyDiffFile(f) as diff_file:
            uncrustify_diff = diff_parser(diff_file)
            overlaps = find_overlaps(uncrustify_diff[f]["adds"], git_diff[f]["adds"])
            if not overlaps:
                continue

            print_uncrustify_diff(f, diff_file, overlaps)


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
        uncrustify_diff(diff_map)


if __name__ == "__main__":
    main(sys.argv)
