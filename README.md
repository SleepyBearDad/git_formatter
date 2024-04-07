# git-formatter

The goal of this project is to allow easy intergation of formatting tools into
git for existing projects.

The main problem with intergration of formatters into existing projects is
finding a formatter that supports the "special" formatting requirements of the
projects, such as special alignments in MACROs, quircky alignment rules in
assignments etc.

The larger problem of the above rules, is that they may invoke religious wars
regarding how the code should look.

In order to avoid these wars, and quickly intergrate a formatter that does a
good-enough job, we introduce a format tool with user defined exceptions that
allow special formats that are otherwise corrected by the formatter.

## Example

The following examply shows aligned assignment, to the longest struct member,
only for the common sub-struct with a combination of tabs and spaces, but
always spaces after tabs, and not the other way around:

```
foo = malloc(sizeof(*foo)
foo->bar.a		       = a;
foo->bar.baz		       = baz;
foo->bar.very_long_member_name = l;
```

A formatter like clang or uncrustify will usually either align to tab or
convert the tabs into spaces to allow alignment not on tab border.

We can add the following exception to allow for such code snippets to happilly
co-exist with the formatter rules:

```
class MixedWhiteSpaceInAssignAlignment(WhitespaceRemoveException):
    _config_key = "remove-whitespaces-in-assign-alignment"
    with_whitespaces = "(\w+)[\]\)]?\s+= [\(]?(\*?\&?\w+)"
    without_whitespaces = "(\w+)[\]\)]?[ ]+ = [\(]?(\*?\&?\w+)"
```

The above exception uses a regular expression to describe the unwanted switch:
switch tabs into spaces before assignment.

In the git-config we use the key to enable the exception:

```
[formatter-exceptions]
  remove-whitespaces-in-assign-alignment = true
```

## Installation

### Requirements

install uncrustify >= 0.64_d

### Copy formatter files to a PATH location

Currently no installer is supported...

Copy git-formatter and uncrustify_diff.py to a location in the path, e.g.
```
mkdir -p ~/scripts/git-formatter/
cp git-formatter uncrustify_diff.py ~/scripts/git-formatter/
export PATH=$PATH:~/scripts/git-formatter/
```

### git pre-commit hook

In order to have git automatically check for formatting errors apply this to your pre-commit git hook:

```
# If you want to allow format set this variable to true in .git/config
formatter=$(git config --bool hooks.formatter)
txtred=$(echo "\e[1;31m")
reset=$(echo "\e[0m")

# Redirect output to stderr.
exec 1>&2

if [ "$formatter" == "true" ] &&
        test $(git formatter $against |
          LC_ALL=C tr -d '[ -~]\0' | wc -c) != 0
then
        echo -e "${txtred}formatter check failed on this commit!${reset}"
        cat <<\EOF

You can override this by applying --no-verify on the commit, but why not just fix it?!

Here is the formatter output:
EOF

        git formatter $against
        exit 1
fi

```

### Enable required options and exceptions in gitconfig

These are the currently provided exceptions:
```
[formatter]
  colors = true
  uncrustify = true
[formatter-exceptions]
  remove-whitespaces-in-struct-ctx = true
  remove-whitespaces-in-assign-alignment = true
  break-multi-line-shift = true
  break-multi-line-or = true
  devx-macro-exception = true
```
