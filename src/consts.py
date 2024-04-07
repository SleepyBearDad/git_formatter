new_file_prefix_a = "--- a/"
new_file_prefix_b = "+++ b/"
diff_prefix = "@@"
diff_suffix = "@@"
remove_prefix = "-"
add_prefix = "+"


class Color:
    _default = {
        "PURPLE": "\033[95m",
        "CYAN": "\033[96m",
        "DARKCYAN": "\033[36m",
        "BLUE": "\033[94m",
        "GREEN": "\033[92m",
        "YELLOW": "\033[93m",
        "RED": "\033[91m",
        "BOLD": "\033[1m",
        "UNDERLINE": "\033[4m",
        "END": "\033[0m"
    }

    @classmethod
    def initialize(cls, colors=True):
        for key in cls._default:
            if colors:
                setattr(cls, key, cls._default[key])
            else:
                setattr(cls, key, "")


